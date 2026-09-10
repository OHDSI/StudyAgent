import csv
import json
from pathlib import Path

from study_agent_mcp.tools.phenotype_make_computable_emit import emit_capr
from study_agent_mcp.tools.phenotype_make_computable_validate import validate_capr_source

_ROOT = Path("docs/evaluation/phenotype_make_computable/reference_set/training_cohorts")


CASES = {
    # The StudyAgent development variant intentionally adds 365 days continuous
    # observation; this structural comparison does not assert that semantic delta.
    "63": {"index_event": "Transverse myelitis", "entry_limit": "All", "prior_observation": 365, "exit_strategy": {"type": "fixed", "index": "startDate", "offset_days": 1}, "temporal_followup": {"index_concept_set": "Transverse Myelitis", "trigger_concept_set": "Symptoms for Transverse Myelitis", "followup_days": 30, "washout_days": 365}},
    "710": {"index_event": "Cirrhosis", "entry_limit": "First", "exit_strategy": "observation"},
    "794": {"index_event": "Digestive hemorrhage", "entry_limit": "All", "exit_strategy": {"type": "fixed", "offset_days": 14}},
    "743": {"index_event": "Diabetic ketoacidosis", "entry_limit": "All", "visit_overlap": True, "visit_overlap_mode": "entry", "exit_strategy": {"type": "fixed", "index": "startDate", "offset_days": 30}},
    "222": {"index_event": "SJS/TEN", "entry_limit": "All", "visit_overlap": True, "visit_overlap_mode": "attrition", "exit_strategy": {"type": "fixed", "offset_days": 1}},
    "858": {"index_event": "Rheumatoid arthritis", "entry_limit": "First", "exit_strategy": "observation", "multi_domain_entry_policy": "any_qualifying_domain"},
    "1340": {"index_event": "Anorexia nervosa", "entry_limit": "All", "exit_strategy": {"type": "fixed", "offset_days": 30}, "era_days": 365},
    "1341": {"index_event": "Eating disorders", "entry_limit": "All", "exit_strategy": {"type": "fixed", "offset_days": 30}, "era_days": 365},
    "1345": {"index_event": "Personality disorders", "entry_limit": "All", "exit_strategy": {"type": "fixed", "offset_days": 30}, "era_days": 365},
    "1346": {"index_event": "ADHD", "entry_limit": "All", "exit_strategy": {"type": "fixed", "offset_days": 30}, "era_days": 365},
    "1347": {"index_event": "PTSD", "entry_limit": "All", "exit_strategy": {"type": "fixed", "offset_days": 30}, "era_days": 365},
}


def _reviewed_concept_sets(case_id: str):
    grouped = {}
    with (_ROOT / case_id / "concept_roots.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            item = grouped.setdefault(row["concept_set_name"], {"name": row["concept_set_name"], "domain": row["domain_id"], "items": []})
            item["items"].append({"concept_id": int(row["concept_id"]), "domain": row["domain_id"], "include_descendants": row["include_descendants"].lower() == "true", "include_mapped": row["include_mapped"].lower() == "true", "is_excluded": row["is_excluded"].lower() == "true"})
    return list(grouped.values())


def _concept_policy_set(circe: dict):
    records = set()
    for concept_set in circe.get("ConceptSets", []):
        for item in concept_set.get("expression", {}).get("items", []):
            concept = item.get("concept", {})
            records.add((int(concept["CONCEPT_ID"]), bool(item.get("isExcluded")), bool(item.get("includeDescendants")), bool(item.get("includeMapped"))))
    return records


def _exit_offset(circe: dict):
    return (circe.get("EndStrategy") or {}).get("DateOffset")


def compare_case(case_id: str) -> list[str]:
    emitted = emit_capr(CASES[case_id], _reviewed_concept_sets(case_id))
    assert emitted["status"] == "passed", emitted
    generated = validate_capr_source(emitted["capr_code"])
    assert generated["status"] == "passed", generated
    actual = generated["circe_json"]
    reference = json.loads((_ROOT / case_id / "reference_circe.json").read_text(encoding="utf-8"))
    mismatches = []
    if _concept_policy_set(actual) != _concept_policy_set(reference):
        mismatches.append("concept_set_policy")
    if actual["PrimaryCriteria"]["PrimaryCriteriaLimit"] != reference["PrimaryCriteria"]["PrimaryCriteriaLimit"]:
        mismatches.append("primary_criteria_limit")
    if _exit_offset(actual) != _exit_offset(reference):
        mismatches.append("exit_strategy")
    if actual.get("CollapseSettings") != reference.get("CollapseSettings"):
        mismatches.append("collapse_settings")
    if len(actual.get("InclusionRules", [])) != len(reference.get("InclusionRules", [])):
        mismatches.append("inclusion_rule_count")
    return mismatches


def test_reference_structural_comparison_baseline():
    results = {case_id: compare_case(case_id) for case_id in CASES}
    assert results == {case_id: [] for case_id in CASES}
