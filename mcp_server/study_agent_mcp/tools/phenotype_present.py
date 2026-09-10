from __future__ import annotations

from typing import Any, Dict, List

from study_agent_mcp.retrieval import get_default_index

from ._common import with_meta


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _cipher_pattern(source: Dict[str, Any]) -> Dict[str, str]:
    algorithm = source.get("algorithm") if isinstance(source.get("algorithm"), dict) else {}
    return {
        "algorithm_description": _text(algorithm.get("algorithmDesc")),
        "population_description": _text(algorithm.get("populationDesc")),
        "validation_description": _text(algorithm.get("validationDescription")),
    }


def _circe_summary(source: Dict[str, Any]) -> str:
    primary = source.get("PrimaryCriteria") if isinstance(source.get("PrimaryCriteria"), dict) else {}
    criteria_list = primary.get("CriteriaList") if isinstance(primary.get("CriteriaList"), list) else []
    concept_sets = source.get("ConceptSets") if isinstance(source.get("ConceptSets"), list) else []
    names = [str(item.get("name") or "").strip() for item in concept_sets if isinstance(item, dict) and item.get("name")]
    criteria_count = len(criteria_list)
    if names:
        return f"Executable OHDSI cohort with {len(names)} concept set(s): {', '.join(names[:3])}. Primary entry contains {criteria_count} criterion/criteria."
    return f"Executable OHDSI cohort with {criteria_count} primary entry criterion/criteria."


def build_presentation(snapshot: Dict[str, Any], summary: Dict[str, Any]) -> Dict[str, Any]:
    source = snapshot.get("source_payload") if isinstance(snapshot.get("source_payload"), dict) else {}
    source_dataset = str(snapshot.get("source_dataset") or summary.get("source_dataset") or "")
    title = str(snapshot.get("title") or summary.get("name") or snapshot.get("phenotype_id") or "")
    code_systems = summary.get("code_systems") if isinstance(summary.get("code_systems"), list) else []
    has_codes = any(isinstance(item, dict) and item.get("codes") for item in code_systems)

    if source_dataset == "ohdsi_phenotype_library" and isinstance(source.get("PrimaryCriteria"), dict):
        return {
            "phenotype_id": snapshot.get("phenotype_id"),
            "title": title,
            "source": "OHDSI Phenotype Library",
            "use_mode": "direct",
            "plain_language_summary": _circe_summary(source),
            "source_evidence": {"circe_definition_available": True, "coded_evidence_available": True, "narrative_logic_available": True},
            "important_gaps": ["Clinical fit to the requested study intent still requires review."],
            "available_actions": ["use_directly", "inspect_circe_definition"],
            "provenance": {key: snapshot.get(key) for key in ("source_revision", "source_modified_at", "source_payload_sha256")},
        }

    pattern = _cipher_pattern(source)
    narrative = pattern["algorithm_description"] or _text(source.get("description")) or _text(summary.get("short_description"))
    gaps: List[str] = ["No executable OHDSI Circe definition is available from this source."]
    if not has_codes:
        gaps.append("The source does not provide a reviewable coded evidence set.")
    if not pattern["algorithm_description"]:
        gaps.append("The source does not provide detailed algorithm logic.")
    if any("Text" in str(item.get("system_name") or "") for item in code_systems if isinstance(item, dict)):
        gaps.append("Text snippets are narrative evidence, not an OMOP concept set.")
    return {
        "phenotype_id": snapshot.get("phenotype_id"),
        "title": title,
        "source": "VA CIPHER" if source_dataset == "va_cipher" else source_dataset or "Indexed phenotype source",
        "use_mode": "requires_readiness_assessment",
        "plain_language_summary": narrative or "Indexed phenotype source with no readable narrative summary.",
        "clinical_pattern": {key: value for key, value in pattern.items() if value},
        "source_evidence": {"circe_definition_available": False, "coded_evidence_available": has_codes, "narrative_logic_available": bool(pattern["algorithm_description"])},
        "important_gaps": gaps,
        "available_actions": ["assess_conversion_readiness", "inspect_source_snapshot"],
        "provenance": {key: snapshot.get(key) for key in ("source_revision", "source_modified_at", "source_payload_sha256")},
    }


def register(mcp: object) -> None:
    @mcp.tool(name="phenotype_present")
    def phenotype_present_tool(phenotype_id: str) -> Dict[str, Any]:
        index = get_default_index()
        snapshot = index.fetch_source_snapshot(str(phenotype_id))
        summary = index.fetch_summary(str(phenotype_id))
        if snapshot is None or summary is None:
            return with_meta({"error": f"phenotype_id {phenotype_id} not found or has no indexed source snapshot"}, "phenotype_present")
        return with_meta({"presentation": build_presentation(snapshot, summary)}, "phenotype_present")

    return None
