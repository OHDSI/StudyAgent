import json
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from study_agent_acp.agent import StudyAgent


pytestmark = pytest.mark.acp


def _annotated_template() -> str:
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.abspath(os.path.join(here, "..", "mcp_server", "prompts", "cohort_methods", "cmAnalysis_template.json"))
    with open(path, "r", encoding="utf-8") as fh:
        return fh.read()


def _defaults_spec() -> Dict[str, Any]:
    return json.loads(_annotated_template())


def _make_bundle_payload() -> Dict[str, Any]:
    return {
        "status": "ok",
        "full_result": {
            "instruction_template": "<Instruction>...</Instruction>",
            "output_style_template": "<Output Style>...</Output Style>",
            "annotated_template": _annotated_template(),
            "analysis_specifications_template": _annotated_template(),
            "json_field_descriptions": "## Top-Level Shape\n...",
            "defaults_spec": _defaults_spec(),
            "schema_version": "v1.4.0",
        },
    }


def _make_llm_result(content: Dict[str, Any], status: str = "ok") -> MagicMock:
    m = MagicMock()
    m.status = status
    m.duration_seconds = 1.23
    m.error = None
    m.parse_stage = "ok" if status == "ok" else "json_decode_failed"
    m.schema_valid = True if status == "ok" else False
    m.request_mode = "structured"
    m.missing_keys = []
    m.raw_response = json.dumps(content) if status == "ok" else "<bad>"
    m.content_text = m.raw_response
    m.parsed_content = content if status == "ok" else None
    return m


def _valid_llm_payload(defaults: Dict[str, Any]) -> Dict[str, Any]:
    spec = json.loads(json.dumps(defaults))
    spec["description"] = "Example"
    spec["getDbCohortMethodDataArgs"]["washoutPeriod"] = 365
    return {
        "specifications": spec,
        "sectionRationales": {
            "study_population":             {"rationale": "washout lengthened", "confidence": "high"},
            "time_at_risk":                 {"rationale": "risk window kept", "confidence": "medium"},
            "propensity_score_adjustment":  {"rationale": "defaults", "confidence": "medium"},
            "outcome_model":                {"rationale": "defaults", "confidence": "medium"},
        },
    }


def _build_agent_with_mocks(bundle_payload: Dict[str, Any], llm_result) -> StudyAgent:
    agent = StudyAgent.__new__(StudyAgent)
    agent._mcp_client = MagicMock()
    agent.call_tool = MagicMock(return_value=bundle_payload)
    agent._call_llm = MagicMock(return_value=llm_result)
    agent.debug = False
    return agent


def test_happy_path_returns_shell_shape() -> None:
    defaults = _defaults_spec()
    agent = _build_agent_with_mocks(_make_bundle_payload(), _make_llm_result(_valid_llm_payload(defaults)))
    result = agent.run_cohort_methods_specs_recommendation_flow(
        analytic_settings_description="compare A vs B with 1-year washout",
    )
    assert result["status"] == "ok"
    rec = result["recommendation"]
    assert rec["mode"] == "free_text"
    assert rec["source"] == "acp_flow"
    assert rec["status"] == "received"
    assert rec["profile_name"] == "Example"
    assert rec["raw_description"] == "compare A vs B with 1-year washout"
    assert rec["study_population"]["cohortMethodDataArgs"]["washoutPeriod"] == 365
    assert rec["defaults_snapshot"] == {}
    assert "section_rationales" in result
    assert result["section_rationales"]["study_population"]["confidence"] == "high"
    assert result["section_rationales"]["time_at_risk"]["confidence"] == "medium"
    assert result["section_rationales"]["propensity_score_adjustment"]["confidence"] == "medium"
    assert result["section_rationales"]["outcome_model"]["confidence"] == "medium"
    prompt = agent._call_llm.call_args.args[0]
    assert "<Current Analysis Specifications>" not in prompt
    assert "<Analysis Specifications Template>" in prompt
    assert "<JSON Fields Descriptions>" in prompt
    assert "## Top-Level Shape" in prompt


def test_llm_cohort_definitions_are_passed_through_without_request_metadata() -> None:
    defaults = _defaults_spec()
    drifted = _valid_llm_payload(defaults)
    drifted["specifications"]["cohortDefinitions"] = {"targetCohort": {"id": 666, "name": "LLM supplied"}}
    agent = _build_agent_with_mocks(_make_bundle_payload(), _make_llm_result(drifted))
    result = agent.run_cohort_methods_specs_recommendation_flow(
        analytic_settings_description="desc",
    )
    assert result["cohort_methods_specifications"]["cohortDefinitions"]["targetCohort"]["id"] == 666


def test_llm_parse_error_returns_defaults_fallback() -> None:
    bad = _make_llm_result({}, status="error")
    bad.parsed_content = None
    bad.content_text = "this is not json"
    bad.raw_response = "this is not json"
    agent = _build_agent_with_mocks(_make_bundle_payload(), bad)
    result = agent.run_cohort_methods_specs_recommendation_flow(
        analytic_settings_description="desc",
    )
    assert result["status"] == "llm_parse_error"
    assert result["recommendation"]["status"] == "backfilled"
    assert result["diagnostics"]["llm_parse_stage"] in {"json_extract_failed", "json_decode_failed"}


def test_section_schema_violation_backfills_with_low_confidence() -> None:
    defaults = _defaults_spec()
    payload = _valid_llm_payload(defaults)
    payload["specifications"]["fitOutcomeModelArgs"] = {
        "modelType": "svm", "stratified": False, "useCovariates": False,
        "inversePtWeighting": False, "prior": None, "control": None,
    }
    agent = _build_agent_with_mocks(_make_bundle_payload(), _make_llm_result(payload))
    result = agent.run_cohort_methods_specs_recommendation_flow(
        analytic_settings_description="desc",
    )
    assert result["status"] == "ok"
    assert "fitOutcomeModelArgs" in result["diagnostics"]["failed_sections"]
    assert result["recommendation"]["status"] == "backfilled"
    assert result["recommendation"]["outcome_model"]["modelType"] == "cox"
    assert result["section_rationales"]["outcome_model"]["confidence"] == "low"


def test_missing_description_errors_out() -> None:
    agent = _build_agent_with_mocks(_make_bundle_payload(), _make_llm_result({}))
    result = agent.run_cohort_methods_specs_recommendation_flow(
        analytic_settings_description="",
    )
    assert result["status"] == "llm_parse_error"
    assert "analytic_settings_description" in json.dumps(result["diagnostics"])


def test_mcp_bundle_failure_raises() -> None:
    bundle_fail = {"status": "error", "error": "bundle unavailable"}
    agent = _build_agent_with_mocks(bundle_fail, _make_llm_result({}))
    with pytest.raises(RuntimeError):
        agent.run_cohort_methods_specs_recommendation_flow(
            analytic_settings_description="desc",
        )
