from __future__ import annotations

import os
import re
from typing import Any, Dict, List, Set

import sqlalchemy as sa
from omop_alchemy import create_engine_with_dependencies

from study_agent_mcp.retrieval import get_default_index

from ._common import with_meta
from .keeper_concept_sets import _resolve_vocab_engine_name

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SOURCE_VOCABULARIES = {
    "ICD-9 Diagnostic Codes": "ICD9CM",
    "ICD-10 Diagnostic Codes": "ICD10CM",
    "Read Codes v2": "Read",
    "Read Code": "Read",
    "OXMIS Codes": "OXMIS",
}


def _identifier(value: str, label: str) -> str:
    if not _IDENTIFIER_RE.fullmatch(value):
        raise ValueError(f"invalid_{label}")
    return value


def _code_systems(summary: Dict[str, Any]) -> List[Dict[str, Any]]:
    value = summary.get("code_systems")
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def assess_readiness(snapshot: Dict[str, Any], summary: Dict[str, Any], available_vocabularies: Set[str] | None = None) -> Dict[str, Any]:
    source = snapshot.get("source_payload") if isinstance(snapshot.get("source_payload"), dict) else {}
    dataset = str(snapshot.get("source_dataset") or summary.get("source_dataset") or "")
    if dataset == "ohdsi_phenotype_library" and isinstance(source.get("PrimaryCriteria"), dict):
        return {"computability_status": "circe_available", "action_class": "direct", "reasons": ["Validated Circe source is indexed."], "code_systems": []}

    algorithm = source.get("algorithm") if isinstance(source.get("algorithm"), dict) else {}
    narrative_logic = bool(str(algorithm.get("algorithmDesc") or "").strip())
    evidence: List[Dict[str, Any]] = []
    supported = 0
    supported_and_available = 0
    for system in _code_systems(summary):
        name = str(system.get("system_name") or "")
        vocabulary_id = _SOURCE_VOCABULARIES.get(name)
        codes = [str(code) for code in system.get("codes") or [] if str(code).strip()]
        availability = "not_applicable" if not vocabulary_id else ("available" if available_vocabularies is not None and vocabulary_id in available_vocabularies else "not_checked" if available_vocabularies is None else "unavailable")
        if vocabulary_id:
            supported += 1
            if availability == "available":
                supported_and_available += 1
        evidence.append({"source_system": name or "unknown", "omop_vocabulary_id": vocabulary_id or "", "code_count": len(codes), "mapping_support": availability, "mapping_eligible": bool(vocabulary_id), "notes": "Text snippets and unrecognized systems are not automatically mappable." if not vocabulary_id else "Mappings remain review evidence only."})

    if not supported and not narrative_logic:
        action = "not_supported"
        reasons = ["The source has neither supported code terminology nor detailed algorithm logic."]
    elif not supported:
        action = "source_informed_review"
        reasons = ["Narrative logic can seed a reviewed design, but source codes are not deterministically mappable."]
    elif available_vocabularies is not None and not supported_and_available:
        action = "source_informed_review" if narrative_logic else "not_supported"
        reasons = ["Recognized source vocabularies are not installed in the configured OMOP vocabulary database."]
    elif narrative_logic:
        action = "conversion_candidate"
        reasons = ["Recognized coded evidence and detailed algorithm logic require human scope and concept-policy review."]
    else:
        action = "mapping_and_scope_review"
        reasons = ["Recognized coded evidence is available, but cohort logic must be supplied and confirmed by the user."]
    return {"computability_status": "conversion_required" if action != "not_supported" else "not_computable", "action_class": action, "reasons": reasons, "narrative_logic_available": narrative_logic, "code_systems": evidence, "mapping_relationship": {"relationship_id": "Maps to", "relationship_concept_id": 44818977, "note": "Runtime code coverage uses the CDM relationship_id; the concept id is retained as deployment provenance."}}


def _available_vocabularies(summary: Dict[str, Any]) -> Set[str]:
    requested = sorted({vocab for item in _code_systems(summary) if (vocab := _SOURCE_VOCABULARIES.get(str(item.get("system_name") or "")))})
    if not requested:
        return set()
    schema = _identifier(os.getenv("VOCAB_DATABASE_SCHEMA", "vocabulary"), "vocab_database_schema")
    engine = create_engine_with_dependencies(_resolve_vocab_engine_name(), future=True)
    query = sa.text(f"SELECT vocabulary_id FROM {schema}.vocabulary WHERE vocabulary_id IN :ids").bindparams(sa.bindparam("ids", expanding=True))
    with engine.connect() as connection:
        return {str(row[0]) for row in connection.execute(query, {"ids": requested})}


def register(mcp: object) -> None:
    @mcp.tool(name="phenotype_conversion_readiness")
    def phenotype_conversion_readiness_tool(phenotype_id: str, check_vocabulary_database: bool = True) -> Dict[str, Any]:
        index = get_default_index()
        snapshot = index.fetch_source_snapshot(str(phenotype_id))
        summary = index.fetch_summary(str(phenotype_id))
        if snapshot is None or summary is None:
            return with_meta({"error": f"phenotype_id {phenotype_id} not found or has no indexed source snapshot"}, "phenotype_conversion_readiness")
        database_status = "not_requested"
        available = None
        if check_vocabulary_database:
            try:
                available = _available_vocabularies(summary)
                database_status = "checked"
            except Exception as exc:
                database_status = f"unavailable:{type(exc).__name__}"
        readiness = assess_readiness(snapshot, summary, available)
        readiness["vocabulary_database_status"] = database_status
        readiness["available_vocabularies"] = sorted(available) if available is not None else []
        return with_meta({"readiness": readiness}, "phenotype_conversion_readiness")

    return None
