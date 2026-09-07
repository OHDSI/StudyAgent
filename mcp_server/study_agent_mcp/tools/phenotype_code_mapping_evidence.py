from __future__ import annotations

import os
from collections import defaultdict
from typing import Any, Dict, Iterable, List

import sqlalchemy as sa
from omop_alchemy import create_engine_with_dependencies

from study_agent_mcp.retrieval import get_default_index

from ._common import with_meta
from .keeper_concept_sets import _resolve_vocab_engine_name, _safe_identifier
from .phenotype_conversion_readiness import _SOURCE_VOCABULARIES


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


def summarize_mapping(lanes: Iterable[Dict[str, Any]], rows: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
    """Summarize exact source-code rows and Maps to targets without selecting them."""
    targets: Dict[tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
    found: set[tuple[str, str]] = set()
    for row in rows:
        vocabulary_id, code = str(row.get("vocabulary_id") or ""), str(row.get("concept_code") or "")
        key = (vocabulary_id, code)
        found.add(key)
        standard_id = row.get("standard_concept_id")
        if standard_id is not None:
            targets[key].append({"concept_id": int(standard_id), "concept_name": str(row.get("standard_concept_name") or ""), "vocabulary_id": str(row.get("standard_vocabulary_id") or ""), "domain_id": str(row.get("standard_domain_id") or "")})
    code_results: List[Dict[str, Any]] = []
    for lane in lanes:
        vocabulary_id = str(lane["vocabulary_id"])
        for code in lane["codes"]:
            key = (vocabulary_id, str(code))
            candidates = list({item["concept_id"]: item for item in targets.get(key, [])}.values())
            status = "unmatched_source_code" if key not in found else "mapped" if len(candidates) == 1 else "ambiguous_mapping" if len(candidates) > 1 else "no_standard_mapping"
            code_results.append({"source_system": lane["source_system"], "source_vocabulary_id": vocabulary_id, "source_code": str(code), "status": status, "standard_candidates": candidates})
    counts: Dict[str, int] = defaultdict(int)
    for item in code_results:
        counts[item["status"]] += 1
    return {"code_results": code_results, "coverage": {"requested_code_count": len(code_results), "matched_source_code_count": len(code_results) - counts["unmatched_source_code"], "mapped_code_count": counts["mapped"], "ambiguous_mapping_count": counts["ambiguous_mapping"], "no_standard_mapping_count": counts["no_standard_mapping"], "unmatched_source_code_count": counts["unmatched_source_code"]}, "truncated_source_lanes": [{"source_system": lane["source_system"], "source_code_count": lane["source_code_count"], "checked_code_count": len(lane["codes"])} for lane in lanes if lane["truncated"]]}


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
          standard.concept_id AS standard_concept_id, standard.concept_name AS standard_concept_name,
          standard.vocabulary_id AS standard_vocabulary_id, standard.domain_id AS standard_domain_id
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


def register(mcp: object) -> None:
    @mcp.tool(name="phenotype_code_mapping_evidence")
    def phenotype_code_mapping_evidence_tool(phenotype_id: str, maximum_codes_per_system: int = 250) -> Dict[str, Any]:
        maximum_codes_per_system = max(1, min(int(maximum_codes_per_system), 500))
        summary = get_default_index().fetch_summary(str(phenotype_id))
        if summary is None:
            return with_meta({"error": f"phenotype_id {phenotype_id} not found"}, "phenotype_code_mapping_evidence")
        lanes = _source_lanes(summary, maximum_codes_per_system)
        if not lanes:
            return with_meta({"mapping_evidence": {"status": "not_applicable", "reason": "No recognized source-code terminology is available for exact OMOP vocabulary lookup.", "coverage": {"requested_code_count": 0}}}, "phenotype_code_mapping_evidence")
        try:
            evidence = summarize_mapping(lanes, _query_rows(lanes))
            evidence.update({"status": "ok", "mapping_relationship": {"relationship_id": "Maps to", "relationship_concept_id": 44818977}, "selection_guardrail": "Mapping results are evidence for human review only; they are not an approved concept set."})
        except Exception as exc:
            evidence = {"status": "unavailable", "reason": f"vocabulary_database_unavailable:{type(exc).__name__}", "coverage": {"requested_code_count": sum(len(lane["codes"]) for lane in lanes)}}
        return with_meta({"mapping_evidence": evidence}, "phenotype_code_mapping_evidence")
