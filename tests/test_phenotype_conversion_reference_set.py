import json
from pathlib import Path

import pytest
from study_agent_mcp.tools.phenotype_code_mapping_evidence import summarize_mapping


_REFERENCE_PATH = Path("docs/evaluation/phenotype_conversion/reference_set/reference_cases.json")
_MAPPING_POLICY_REFERENCE_PATH = Path("docs/evaluation/phenotype_conversion/reference_set/mapping_policy_cases.json")
_ALLOWED_ACTIONS = {
    "not_supported",
    "source_informed_review",
    "mapping_and_scope_review",
    "conversion_candidate",
}


@pytest.mark.mcp
def test_conversion_reference_set_has_unique_complete_cases() -> None:
    payload = json.loads(_REFERENCE_PATH.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    cases = payload["cases"]
    assert len(cases) >= 6
    identifiers = [case["phenotype_id"] for case in cases]
    assert len(identifiers) == len(set(identifiers))
    for case in cases:
        assert case["phenotype_id"].startswith("cipher:")
        assert case["expected_action_class"] in _ALLOWED_ACTIONS
        assert isinstance(case["circe_prohibited"], bool)
        composition = case.get("expected_composition")
        if composition is not None:
            assert composition["template"] == "exposure_followed_by_outcome"
            assert composition["index_domain"] == "Drug"
            assert composition["outcome_domain"] == "Condition"
            assert composition["requires_explicit_approval"] is True
        assert isinstance(case["required_human_decisions"], list)
        assert case["notes"].strip()


@pytest.mark.mcp
def test_conversion_reference_set_preserves_safety_examples() -> None:
    cases = {case["phenotype_id"]: case for case in json.loads(_REFERENCE_PATH.read_text(encoding="utf-8"))["cases"]}
    assert cases["cipher:30687"]["expected_action_class"] == "not_supported"
    assert cases["cipher:30687"]["circe_prohibited"] is True
    assert cases["cipher:29197"]["expected_action_class"] == "source_informed_review"
    assert cases["cipher:29197"]["circe_prohibited"] is True
    composition = cases["cipher:29197"]["expected_composition"]
    assert composition["follow_on_query"] == "Cough"
    assert composition["requires_explicit_approval"] is True
    for phenotype_id in ("cipher:17527", "cipher:14189"):
        assert "PheCode map/version" in cases[phenotype_id]["required_human_decisions"]

@pytest.mark.mcp
def test_mapping_policy_reference_matrix_covers_supported_domains() -> None:
    payload = json.loads(_MAPPING_POLICY_REFERENCE_PATH.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    cases = payload["cases"]
    assert {"Condition", "Drug", "Procedure", "Measurement"}.issubset({case["target_domain"] for case in cases})

    for index, case in enumerate(cases, start=1):
        lanes = [{"source_system": case["source_vocabulary_id"], "vocabulary_id": case["source_vocabulary_id"], "codes": [case["source_code"]], "source_code_count": 1, "truncated": False}]
        rows = [{"vocabulary_id": case["source_vocabulary_id"], "concept_code": case["source_code"], "standard_concept_id": index, "standard_concept_name": case["label"], "standard_vocabulary_id": case["target_vocabulary_id"], "standard_domain_id": case["target_domain"]}]
        evidence = summarize_mapping(lanes, rows, expected_domains=case["expected_domains"])
        assert evidence["code_results"][0]["standard_candidates"][0]["domain_policy_status"] == case["expected_policy_status"]
