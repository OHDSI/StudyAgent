from __future__ import annotations

import os
from collections import defaultdict
from typing import Any, Dict, Iterable, List, Sequence

import sqlalchemy as sa
from omop_alchemy import create_engine_with_dependencies

from study_agent_mcp.retrieval import get_default_index

from ._common import with_meta
from .keeper_concept_sets import _resolve_vocab_engine_name, _safe_identifier
from .phenotype_conversion_readiness import _SOURCE_VOCABULARIES

# This is a deliberately small, review-facing policy. It does not replace the
# OHDSI vocabulary: target concepts must still be standard, valid, and in the
# user-confirmed OMOP domain. The source of truth for semantics and releases is
# the OHDSI Vocabulary wiki and its release history.
MAPPING_POLICY_VERSION = "ohdsi_vocabulary_domain_policy_v1"
MAPPING_POLICY_REFERENCES = {
    "vocabulary_wiki": "https://github.com/OHDSI/Vocabulary-v5.0/wiki",
    "vocabulary_releases": "https://github.com/OHDSI/Vocabulary-v5.0/releases",
}
_ALLOWED_STANDARD_VOCABULARIES = {
    "Condition": {"SNOMED", "ICDO3"},
    "Drug": {"RxNorm", "RxNorm Extension", "CVX"},
    "Procedure": {"SNOMED", "CPT4", "HCPCS", "ICD10PCS", "ICD9Proc", "OPCS4"},
    "Measurement": {"LOINC", "SNOMED"},
    "Device": {"SNOMED"},
}


def _normalize_expected_domains(expected_domains: Sequence[str] | None) -> List[str]:
    values = [str(value).strip() for value in expected_domains or [] if str(value).strip()]
    return list(dict.fromkeys(values))


def _policy_status(candidate: Dict[str, Any], expected_domains: Sequence[str]) -> str:
    if not expected_domains:
        return "expected_domain_required"
    domain_id = str(candidate.get("domain_id") or "")
    vocabulary_id = str(candidate.get("vocabulary_id") or "")
    if domain_id not in expected_domains:
        return "wrong_domain"
    allowed = _ALLOWED_STANDARD_VOCABULARIES.get(domain_id)
    if allowed is None:
        return "policy_not_defined"
    if vocabulary_id not in allowed:
        return "unexpected_standard_vocabulary"
    return "eligible_for_review"


def _source_lanes(summary: Dict[str, Any], maximum_codes: int) -> List[Dict[str, Any]]:
    lanes: List[Dict[str, Any]] = []
    for item in summary.get("code_systems") or []:
        if not isinstance(item, dict):
            continue
        vocabulary_id = _SOURCE_VOCABULARIES.get(str(item.get("system_name") or ""))
        codes = list(dict.fromkeys(str(code).strip() for code in item.get("codes") or [] if str(code).strip()))
        if vocabulary_id and codes:
            lanes.append({"source_system": str(item.get("system_name") or ""), "vocabulary_id": vocabulary_id, "codes": codes[:maximum_codes], "source_code_count": len(codes), "truncated": len(codes) > maximum_codes})
    return lanes



def _atlas_concept(row: Dict[str, Any], prefix: str) -> Dict[str, Any]:
    """Return the fully hydrated WebAPI v2 concept object for an Atlas expression item."""
    field = lambda name, default=None: row.get(f"{prefix}_{name}", default)
    standard_concept = field("standard_concept") or ""
    invalid_reason = field("invalid_reason")
    return {
        "CONCEPT_CLASS_ID": str(field("concept_class_id") or ""),
        "CONCEPT_CODE": str(field("concept_code") or ""),
        "CONCEPT_ID": int(field("concept_id")),
        "CONCEPT_NAME": str(field("concept_name") or ""),
        "DOMAIN_ID": str(field("domain_id") or ""),
        "INVALID_REASON": invalid_reason,
        "INVALID_REASON_CAPTION": "Valid" if not invalid_reason else str(invalid_reason),
        "STANDARD_CONCEPT": str(standard_concept),
        "STANDARD_CONCEPT_CAPTION": "Standard" if standard_concept == "S" else "Classification" if standard_concept == "C" else "Non-standard",
        "VOCABULARY_ID": str(field("vocabulary_id") or ""),
        "VALID_START_DATE": str(field("valid_start_date") or ""),
        "VALID_END_DATE": str(field("valid_end_date") or ""),
    }


def summarize_mapping(
    lanes: Iterable[Dict[str, Any]], rows: Iterable[Dict[str, Any]], expected_domains: Sequence[str] | None = None
) -> Dict[str, Any]:
    """Summarize exact source-code rows and review-only standard targets."""
    targets: Dict[tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    found: set[tuple[str, str]] = set()
    for row in rows:
        vocabulary_id, code = str(row.get("vocabulary_id") or ""), str(row.get("concept_code") or "")
        key = (vocabulary_id, code)
        found.add(key)
        if str(row.get("source_standard_concept") or "") == "S":
            source_candidate = {"concept_id": int(row["source_concept_id"]), "concept_name": str(row.get("source_concept_name") or ""), "vocabulary_id": vocabulary_id, "domain_id": str(row.get("source_domain_id") or ""), "mapping_method": "source_standard"}
            source_candidate["atlas_concept"] = _atlas_concept(row, "source")
            targets[key].append(source_candidate)
        standard_id = row.get("standard_concept_id")
        if standard_id is not None:
            standard_candidate = {"concept_id": int(standard_id), "concept_name": str(row.get("standard_concept_name") or ""), "vocabulary_id": str(row.get("standard_vocabulary_id") or ""), "domain_id": str(row.get("standard_domain_id") or ""), "mapping_method": "Maps to"}
            standard_candidate["atlas_concept"] = _atlas_concept(row, "standard")
            targets[key].append(standard_candidate)
    domains = _normalize_expected_domains(expected_domains)
    code_results: List[Dict[str, Any]] = []
    for lane in lanes:
        vocabulary_id = str(lane["vocabulary_id"])
        for code in lane["codes"]:
            key = (vocabulary_id, str(code))
            candidates = list({item["concept_id"]: item for item in targets.get(key, [])}.values())
            for candidate in candidates:
                candidate["domain_policy_status"] = _policy_status(candidate, domains)
            status = "unmatched_source_code" if key not in found else "mapped" if len(candidates) == 1 else "ambiguous_mapping" if len(candidates) > 1 else "no_standard_mapping"
            code_results.append({"source_system": lane["source_system"], "source_vocabulary_id": vocabulary_id, "source_code": str(code), "status": status, "standard_candidates": candidates})
    counts: Dict[str, int] = defaultdict(int)
    policy_counts: Dict[str, int] = defaultdict(int)
    for item in code_results:
        counts[item["status"]] += 1
        for candidate in item["standard_candidates"]:
            policy_counts[candidate["domain_policy_status"]] += 1
    return {
        "code_results": code_results,
        "coverage": {"requested_code_count": len(code_results), "matched_source_code_count": len(code_results) - counts["unmatched_source_code"], "mapped_code_count": counts["mapped"], "ambiguous_mapping_count": counts["ambiguous_mapping"], "no_standard_mapping_count": counts["no_standard_mapping"], "unmatched_source_code_count": counts["unmatched_source_code"]},
        "domain_mapping_policy": {"policy_version": MAPPING_POLICY_VERSION, "references": MAPPING_POLICY_REFERENCES, "expected_domains": domains, "allowed_standard_vocabularies": {domain: sorted(_ALLOWED_STANDARD_VOCABULARIES.get(domain, set())) for domain in domains}, "candidate_status_counts": dict(policy_counts), "guardrail": "Eligibility is a bounded mapping-review signal; it does not approve concept policies or cohort logic."},
        "truncated_source_lanes": [{"source_system": lane["source_system"], "source_code_count": lane["source_code_count"], "checked_code_count": len(lane["codes"])} for lane in lanes if lane["truncated"]],
    }


def _query_rows(lanes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    schema = _safe_identifier(os.getenv("VOCAB_DATABASE_SCHEMA", "vocabulary"), "vocab_database_schema")
    concept_table = _safe_identifier(os.getenv("VOCAB_CONCEPT_TABLE", "concept"), "vocab_concept_table")
    pairs = [(str(lane["vocabulary_id"]), str(code)) for lane in lanes for code in lane["codes"]]
    if not pairs:
        return []
    engine = create_engine_with_dependencies(_resolve_vocab_engine_name(), future=True)
    values = ", ".join(f"(:v{i}, :c{i})" for i in range(len(pairs)))
    params = {key: value for i, pair in enumerate(pairs) for key, value in ((f"v{i}", pair[0]), (f"c{i}", pair[1]))}
    sql = sa.text(f"""
        WITH requested(vocabulary_id, concept_code) AS (VALUES {values})
        SELECT source.vocabulary_id, source.concept_code,
          source.concept_id AS source_concept_id, source.concept_name AS source_concept_name,
          source.vocabulary_id AS source_vocabulary_id, source.concept_code AS source_concept_code,
          source.domain_id AS source_domain_id, source.standard_concept AS source_standard_concept,
          source.concept_class_id AS source_concept_class_id, source.invalid_reason AS source_invalid_reason,
          source.valid_start_date AS source_valid_start_date, source.valid_end_date AS source_valid_end_date,
          standard.concept_id AS standard_concept_id, standard.concept_name AS standard_concept_name,
          standard.vocabulary_id AS standard_vocabulary_id, standard.domain_id AS standard_domain_id,
          standard.concept_code AS standard_concept_code, standard.concept_class_id AS standard_concept_class_id,
          standard.standard_concept AS standard_standard_concept, standard.invalid_reason AS standard_invalid_reason,
          standard.valid_start_date AS standard_valid_start_date, standard.valid_end_date AS standard_valid_end_date
        FROM requested
        JOIN {schema}.{concept_table} source
          ON source.vocabulary_id = requested.vocabulary_id
         AND source.concept_code = requested.concept_code
         AND source.invalid_reason IS NULL
        LEFT JOIN {schema}.concept_relationship rel
          ON rel.concept_id_1 = source.concept_id
         AND rel.relationship_id = 'Maps to'
         AND rel.invalid_reason IS NULL
        LEFT JOIN {schema}.{concept_table} standard
          ON standard.concept_id = rel.concept_id_2
         AND standard.standard_concept = 'S'
         AND standard.invalid_reason IS NULL
    """)
    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(sql, params).mappings()]



def build_vocabulary_release_provenance(vocabulary_ids: Iterable[str], rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    versions = {str(row.get("vocabulary_id") or ""): str(row.get("vocabulary_version") or "") for row in rows}
    requested = sorted({str(vocabulary_id) for vocabulary_id in vocabulary_ids if str(vocabulary_id)})
    return {
        "status": "checked",
        "release_notes": MAPPING_POLICY_REFERENCES["vocabulary_releases"],
        "vocabularies": [
            {"vocabulary_id": vocabulary_id, "vocabulary_version": versions.get(vocabulary_id) or "not_found"}
            for vocabulary_id in requested
        ],
    }


def _query_vocabulary_versions(vocabulary_ids: Iterable[str]) -> List[Dict[str, Any]]:
    ids = sorted({str(vocabulary_id) for vocabulary_id in vocabulary_ids if str(vocabulary_id)})
    if not ids:
        return []
    schema = _safe_identifier(os.getenv("VOCAB_DATABASE_SCHEMA", "vocabulary"), "vocab_database_schema")
    engine = create_engine_with_dependencies(_resolve_vocab_engine_name(), future=True)
    query = sa.text(f"SELECT vocabulary_id, vocabulary_version FROM {schema}.vocabulary WHERE vocabulary_id IN :ids").bindparams(sa.bindparam("ids", expanding=True))
    with engine.connect() as connection:
        return [dict(row) for row in connection.execute(query, {"ids": ids}).mappings()]
def register(mcp: object) -> None:
    @mcp.tool(name="phenotype_code_mapping_evidence")
    def phenotype_code_mapping_evidence_tool(phenotype_id: str, maximum_codes_per_system: int = 250, check_vocabulary_database: bool = True, expected_domains: List[str] | None = None) -> Dict[str, Any]:
        maximum_codes_per_system = max(1, min(int(maximum_codes_per_system), 500))
        summary = get_default_index().fetch_summary(str(phenotype_id))
        if summary is None:
            return with_meta({"error": f"phenotype_id {phenotype_id} not found"}, "phenotype_code_mapping_evidence")
        lanes = _source_lanes(summary, maximum_codes_per_system)
        if not lanes:
            return with_meta({"mapping_evidence": {"status": "not_applicable", "reason": "No recognized source-code terminology is available for exact OMOP vocabulary lookup.", "coverage": {"requested_code_count": 0}}}, "phenotype_code_mapping_evidence")
        if not check_vocabulary_database:
            evidence = {"status": "not_requested", "reason": "Vocabulary database mapping was disabled for this preparation request.", "coverage": {"requested_code_count": sum(len(lane["codes"]) for lane in lanes), "checked_code_count": 0}, "selection_guardrail": "No OMOP mapping lookup was performed; source codes remain review evidence only."}
            return with_meta({"mapping_evidence": evidence}, "phenotype_code_mapping_evidence")
        try:
            mapping_rows = _query_rows(lanes)
            evidence = summarize_mapping(lanes, mapping_rows, expected_domains=expected_domains)
            vocabulary_ids = [lane["vocabulary_id"] for lane in lanes] + [str(row.get("standard_vocabulary_id") or "") for row in mapping_rows]
            try:
                evidence["deployment_vocabulary_release"] = build_vocabulary_release_provenance(vocabulary_ids, _query_vocabulary_versions(vocabulary_ids))
            except Exception as exc:
                evidence["deployment_vocabulary_release"] = {"status": "unavailable", "reason": f"vocabulary_release_lookup_failed:{type(exc).__name__}", "release_notes": MAPPING_POLICY_REFERENCES["vocabulary_releases"]}
            evidence.update({"status": "ok", "mapping_relationship": {"relationship_id": "Maps to", "relationship_concept_id": 44818977}, "selection_guardrail": "Mapping results are evidence for human review only; they are not an approved concept set."})
        except Exception as exc:
            evidence = {"status": "unavailable", "reason": f"vocabulary_database_unavailable:{type(exc).__name__}", "coverage": {"requested_code_count": sum(len(lane["codes"]) for lane in lanes)}}
        return with_meta({"mapping_evidence": evidence}, "phenotype_code_mapping_evidence")
