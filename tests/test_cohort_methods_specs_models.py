import pytest

from study_agent_core.models import (
    CohortMethodSpecsRecommendationInput,
    CohortMethodSpecsRecommendationOutput,
)


pytestmark = pytest.mark.core


def test_input_requires_description() -> None:
    with pytest.raises(Exception):
        CohortMethodSpecsRecommendationInput()  # type: ignore[call-arg]


def test_input_accepts_minimal_payload() -> None:
    payload = CohortMethodSpecsRecommendationInput(
        analytic_settings_description="compare A vs B",
    )
    assert payload.analytic_settings_description == "compare A vs B"
    assert payload.study_intent == ""
    assert payload.study_description is None


def test_input_accepts_full_wrapper_body() -> None:
    payload = CohortMethodSpecsRecommendationInput(
        analytic_settings_description="365-day washout, 1:1 PS match, Cox",
        study_description="365-day washout, 1:1 PS match, Cox",
        study_intent="CV outcomes comparative effectiveness",
    )
    assert payload.study_intent == "CV outcomes comparative effectiveness"
    assert payload.study_description == "365-day washout, 1:1 PS match, Cox"


def test_input_rejects_cohort_metadata_fields() -> None:
    with pytest.raises(Exception):
        CohortMethodSpecsRecommendationInput(
            analytic_settings_description="365-day washout",
            target_cohort_id=1001,
        )  # type: ignore[call-arg]


def test_output_defaults() -> None:
    out = CohortMethodSpecsRecommendationOutput(status="ok")
    assert out.status == "ok"
    assert out.recommendation == {}
    assert out.cohort_methods_specifications is None
    assert out.section_rationales == {}
    assert out.diagnostics == {}


def test_output_rejects_unknown_status() -> None:
    with pytest.raises(Exception):
        CohortMethodSpecsRecommendationOutput(status="stub")  # type: ignore[arg-type]
