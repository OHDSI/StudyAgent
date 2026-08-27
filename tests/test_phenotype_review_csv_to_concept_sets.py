import csv
import importlib.util
import json
from pathlib import Path

import pytest

from study_agent_acp.agent import StudyAgent
from study_agent_mcp.tools.phenotype_make_computable_emit import emit_capr
from study_agent_mcp.tools.phenotype_make_computable_validate import validate_capr_source


SCRIPT_PATH = Path("scripts/phenotype_review_csv_to_concept_sets.py")
SPEC = importlib.util.spec_from_file_location("phenotype_review_csv_to_concept_sets", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _write_review_csv(path, rows):
    fields = [
        "concept_set_name", "concept_id", "concept_name", "domain", "standard_concept", "standard_concept_status", "assessment_status", "relationship_evidence",
        "review_include_concept", "review_include_descendants", "review_include_mapped",
        "review_exclude_concepts", "review_exclude_descendants", "review_exclude_mapped",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def test_review_csv_builds_policy_items_and_flags_unassessed_inclusions(tmp_path):
    csv_path = tmp_path / "review.csv"
    manifest_path = tmp_path / "review_manifest.json"
    manifest_path.write_text(json.dumps({"schema_version": 1, "scope": {"index_event": "Cystitis"}}), encoding="utf-8")
    _write_review_csv(csv_path, [
        {"concept_id": "194081", "concept_name": "Acute cystitis", "domain": "Condition", "standard_concept": "S", "standard_concept_status": "Standard", "assessment_status": "assessed", "review_include_concept": "x", "review_include_descendants": "x"},
        {"concept_id": "37018854", "concept_name": "Hematuria due to cystitis", "domain": "Condition", "standard_concept": "S", "standard_concept_status": "Standard", "assessment_status": "not_assessed_retrieval_context", "relationship_evidence": "Patient context", "review_include_concept": "X"},
        {"concept_id": "198809", "concept_name": "Acute cholecystitis", "domain": "Condition", "standard_concept": "S", "standard_concept_status": "Standard", "assessment_status": "assessed", "review_exclude_concepts": "x"},
    ])

    result = MODULE.parse_review_csv(csv_path, "Cystitis", manifest_path)

    assert result["manifest"]["scope"]["index_event"] == "Cystitis"
    assert result["concept_sets"][0]["items"] == [
        {"concept_id": 194081, "domain": "Condition", "include_descendants": True, "include_mapped": False, "is_excluded": False},
        {"concept_id": 37018854, "domain": "Condition", "include_descendants": False, "include_mapped": False, "is_excluded": False},
        {"concept_id": 198809, "domain": "Condition", "include_descendants": False, "include_mapped": False, "is_excluded": True},
    ]
    assert result["review_summary"]["unassessed_manually_included"][0]["concept_id"] == 37018854
    assert result["approval_preview"] == [
        {"concept_set_name": "Cystitis", "concept_id": 194081, "concept_name": "Acute cystitis", "domain": "Condition", "standard_concept": "S", "standard_concept_status": "Standard", "policy": "Include + descendants", "assessment_status": "assessed", "precision_eligible": "", "relationship_evidence": ""},
        {"concept_set_name": "Cystitis", "concept_id": 37018854, "concept_name": "Hematuria due to cystitis", "domain": "Condition", "standard_concept": "S", "standard_concept_status": "Standard", "policy": "Include", "assessment_status": "not_assessed_retrieval_context", "precision_eligible": "", "relationship_evidence": "Patient context"},
        {"concept_set_name": "Cystitis", "concept_id": 198809, "concept_name": "Acute cholecystitis", "domain": "Condition", "standard_concept": "S", "standard_concept_status": "Standard", "policy": "Exclude", "assessment_status": "assessed", "precision_eligible": "", "relationship_evidence": ""},
    ]


def test_review_csv_groups_explicit_lanes_into_two_concept_sets(tmp_path):
    csv_path = tmp_path / "review.csv"
    _write_review_csv(csv_path, [
        {"concept_set_name": "Stevens-Johnson syndrome or TEN", "concept_id": "35625857", "concept_name": "SJS/TEN", "domain": "Condition", "assessment_status": "assessed", "review_include_concept": "x", "review_include_descendants": "x"},
        {"concept_set_name": "Emergency room or Inpatient Visit", "concept_id": "262", "concept_name": "Emergency Room and Inpatient Visit", "domain": "Visit", "assessment_status": "assessed", "review_include_concept": "x", "review_include_descendants": "x"},
        {"concept_set_name": "Emergency room or Inpatient Visit", "concept_id": "9201", "concept_name": "Inpatient Visit", "domain": "Visit", "assessment_status": "assessed", "review_include_concept": "x", "review_include_descendants": "x"},
    ])

    reviewed = MODULE.parse_review_csv(csv_path)

    assert reviewed["review_summary"]["selected_concept_set_count"] == 2
    assert [(row["name"], row["domain"], len(row["items"])) for row in reviewed["concept_sets"]] == [
        ("Stevens-Johnson syndrome or TEN", "Condition", 1),
        ("Emergency room or Inpatient Visit", "Visit", 2),
    ]
    assert all(row["concept_set_name"] for row in reviewed["approval_preview"])
    emitted = emit_capr(
        {"index_event": "SJS/TEN", "entry_limit": "All", "visit_overlap": True, "visit_overlap_mode": "entry", "exit_strategy": {"type": "fixed", "offset_days": 1}},
        reviewed["concept_sets"],
    )
    assert emitted["status"] == "passed"
    assert validate_capr_source(emitted["capr_code"])["status"] == "passed"


def test_review_csv_writes_hashable_approval_artifacts(tmp_path):
    csv_path = tmp_path / "review.csv"
    _write_review_csv(csv_path, [
        {"concept_set_name": "Warfarin", "concept_id": "1310149", "concept_name": "warfarin", "domain": "Drug", "review_include_concept": "x", "review_include_descendants": "x"},
    ])
    result = MODULE.parse_review_csv(csv_path)
    metadata = MODULE.write_approval_artifacts(result, tmp_path / "approval.json", tmp_path / "approval.csv")
    assert metadata["selected_item_count"] == 1
    assert len(metadata["sha256"]) == 64
    assert json.loads((tmp_path / "approval.json").read_text()) == {"concept_sets": result["concept_sets"]}
    assert "warfarin" in (tmp_path / "approval.csv").read_text()


def test_review_csv_rejects_descendant_without_matching_root(tmp_path):
    csv_path = tmp_path / "review.csv"
    _write_review_csv(csv_path, [
        {"concept_id": "194081", "concept_name": "Acute cystitis", "domain": "Condition", "standard_concept": "S", "standard_concept_status": "Standard", "assessment_status": "assessed", "review_include_descendants": "x"},
    ])

    with pytest.raises(ValueError, match="requires_include_concept"):
        MODULE.parse_review_csv(csv_path, "Cystitis")


class _EmissionMcp:
    def list_tools(self):
        return []

    def call_tool(self, name, arguments):
        if name == "phenotype_make_computable_emit":
            return emit_capr(**arguments)
        if name == "phenotype_make_computable_validate":
            return validate_capr_source(**arguments)
        raise AssertionError(name)


def test_saved_review_package_can_submit_after_session_expiry(tmp_path):
    csv_path = tmp_path / "review.csv"
    manifest_path = tmp_path / "review_manifest.json"
    manifest_path.write_text(json.dumps({
        "schema_version": 1,
        "narrative_statement": "Earliest cirrhosis.",
        "scope": {
            "index_event": "Cirrhosis",
            "criterion_domains": {"Cirrhosis": "Condition"},
            "entry_limit": "First",
            "prior_observation": 0,
            "index_day_boundary": "included",
            "windows": "none",
            "exit_strategy": "observation",
        },
    }), encoding="utf-8")
    _write_review_csv(csv_path, [
        {"concept_id": "4064161", "concept_name": "Cirrhosis of liver", "domain": "Condition", "assessment_status": "assessed", "review_include_concept": "x", "review_include_descendants": "x"},
    ])

    reviewed = MODULE.parse_review_csv(csv_path, "Cirrhosis", manifest_path)
    # No review_id or live session is used below: the persisted review package is sufficient.
    result = StudyAgent(mcp_client=_EmissionMcp()).run_phenotype_make_computable_flow(
        reviewed["manifest"]["narrative_statement"],
        True,
        reviewed["manifest"]["scope"],
        "provided_only",
        reviewed["concept_sets"],
    )

    assert result["status"] == "ok"
    assert result["validation"]["status"] == "passed"
    assert result["validation"]["r_environment"]["validation_packages"]["Capr"] != "not_installed"
