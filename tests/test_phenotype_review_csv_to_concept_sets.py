import csv
import importlib.util
import json
from pathlib import Path

import pytest


SCRIPT_PATH = Path("scripts/phenotype_review_csv_to_concept_sets.py")
SPEC = importlib.util.spec_from_file_location("phenotype_review_csv_to_concept_sets", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def _write_review_csv(path, rows):
    fields = [
        "concept_id", "concept_name", "domain", "assessment_status", "relationship_evidence",
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
        {"concept_id": "194081", "concept_name": "Acute cystitis", "domain": "Condition", "assessment_status": "assessed", "review_include_concept": "x", "review_include_descendants": "x"},
        {"concept_id": "37018854", "concept_name": "Hematuria due to cystitis", "domain": "Condition", "assessment_status": "not_assessed_retrieval_context", "relationship_evidence": "Patient context", "review_include_concept": "X"},
        {"concept_id": "198809", "concept_name": "Acute cholecystitis", "domain": "Condition", "assessment_status": "assessed", "review_exclude_concepts": "x"},
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
        {"concept_id": 194081, "concept_name": "Acute cystitis", "domain": "Condition", "policy": "Include + descendants", "assessment_status": "assessed", "precision_eligible": "", "relationship_evidence": ""},
        {"concept_id": 37018854, "concept_name": "Hematuria due to cystitis", "domain": "Condition", "policy": "Include", "assessment_status": "not_assessed_retrieval_context", "precision_eligible": "", "relationship_evidence": "Patient context"},
        {"concept_id": 198809, "concept_name": "Acute cholecystitis", "domain": "Condition", "policy": "Exclude", "assessment_status": "assessed", "precision_eligible": "", "relationship_evidence": ""},
    ]


def test_review_csv_rejects_descendant_without_matching_root(tmp_path):
    csv_path = tmp_path / "review.csv"
    _write_review_csv(csv_path, [
        {"concept_id": "194081", "concept_name": "Acute cystitis", "domain": "Condition", "assessment_status": "assessed", "review_include_descendants": "x"},
    ])

    with pytest.raises(ValueError, match="requires_include_concept"):
        MODULE.parse_review_csv(csv_path, "Cystitis")
