import pytest

from study_agent_core.cohort_methods_spec_validation import (
    LLM_FILLED_SECTIONS,
    COHORT_METHODS_SPEC_TOP_LEVEL_KEYS,
    validate_section,
    validate_cohort_methods_spec,
)


pytestmark = pytest.mark.core


def _minimal_valid_spec() -> dict:
    return {
        "description": "Study",
        "getDbCohortMethodDataArgs": {
            "studyStartDate": "",
            "studyEndDate": "",
            "firstExposureOnly": False,
            "removeDuplicateSubjects": "keep all",
            "restrictToCommonPeriod": False,
            "washoutPeriod": 365,
            "maxCohortSize": 0,
        },
        "createStudyPopArgs": {
            "removeSubjectsWithPriorOutcome": True,
            "priorOutcomeLookback": 99999,
            "minDaysAtRisk": 1,
            "riskWindowStart": 1,
            "startAnchor": "cohort start",
            "riskWindowEnd": 0,
            "endAnchor": "cohort end",
            "censorAtNewRiskWindow": False,
        },
        "trimByPsArgs": {"trimFraction": 0.05, "equipoiseBounds": None},
        "matchOnPsArgs": {"maxRatio": 1, "caliper": 0.2, "caliperScale": "standardized logit"},
        "stratifyByPsArgs": None,
        "createPsArgs": {
            "maxCohortSizeForFitting": 250000,
            "errorOnHighCorrelation": True,
            "prior": None,
            "control": None,
        },
        "fitOutcomeModelArgs": {
            "modelType": "cox",
            "stratified": False,
            "useCovariates": False,
            "inversePtWeighting": False,
            "prior": None,
            "control": None,
        },
    }


def test_top_level_constants() -> None:
    assert LLM_FILLED_SECTIONS == [
        "getDbCohortMethodDataArgs",
        "createStudyPopArgs",
        "propensityScoreAdjustment",
        "fitOutcomeModelArgs",
    ]
    assert "description" in COHORT_METHODS_SPEC_TOP_LEVEL_KEYS


def test_validate_cohort_methods_spec_accepts_minimal() -> None:
    ok, missing = validate_cohort_methods_spec(_minimal_valid_spec())
    assert ok is True
    assert missing == []


def test_validate_cohort_methods_spec_reports_missing_keys() -> None:
    spec = _minimal_valid_spec()
    del spec["fitOutcomeModelArgs"]
    del spec["description"]
    ok, missing = validate_cohort_methods_spec(spec)
    assert ok is False
    assert set(missing) == {"description", "fitOutcomeModelArgs"}


def test_validate_section_accepts_good_study_pop() -> None:
    spec = _minimal_valid_spec()
    ok, violations = validate_section("createStudyPopArgs", spec["createStudyPopArgs"])
    assert ok is True
    assert violations == []


def test_validate_section_flags_bad_enum() -> None:
    bad = {
        "modelType": "svm",
        "stratified": False,
        "useCovariates": False,
        "inversePtWeighting": False,
        "prior": None,
        "control": None,
    }
    ok, violations = validate_section("fitOutcomeModelArgs", bad)
    assert ok is False
    assert any("modelType" in v for v in violations)


def test_validate_section_flags_range() -> None:
    bad = {
        "matchOnPsArgs": {
            "maxRatio": -1,
            "caliper": -0.5,
            "caliperScale": "standardized",
        }
    }
    ok, violations = validate_section("propensityScoreAdjustment", bad)
    assert ok is False
    assert any("caliper" in v for v in violations)
    assert any("maxRatio" in v for v in violations)


def test_validate_section_rejects_unknown_section() -> None:
    ok, violations = validate_section("unknownSection", {})
    assert ok is False
    assert violations and "unknown section" in violations[0]


from study_agent_core.cohort_methods_spec_validation import (
    backfill_section_from_defaults,
    merge_client_metadata,
)


def test_merge_client_metadata_overrides_llm_cohorts() -> None:
    spec = _minimal_valid_spec()
    client_cohort_defs = {
        "targetCohort": {"id": 1, "name": "Real Target"},
        "comparatorCohort": {"id": 2, "name": "Real Comp"},
        "outcomeCohort": [{"id": 3, "name": "Real Outcome"}],
    }
    merged = merge_client_metadata(
        spec,
        cohort_definitions=client_cohort_defs,
        negative_control={"id": 42, "name": "NC"},
        covariate_selection={"conceptsToInclude": [{"id": 7}], "conceptsToExclude": []},
    )
    assert merged["cohortDefinitions"]["targetCohort"]["id"] == 1
    assert merged["cohortDefinitions"]["targetCohort"]["name"] == "Real Target"
    assert merged["cohortDefinitions"]["comparatorCohort"]["id"] == 2
    assert merged["negativeControlConceptSet"]["id"] == 42
    assert merged["covariateSelection"]["conceptsToInclude"] == [{"id": 7}]


def test_merge_client_metadata_leaves_name_alone() -> None:
    spec = _minimal_valid_spec()
    spec["description"] = "LLM-supplied study name"
    merged = merge_client_metadata(
        spec,
        cohort_definitions={},
        negative_control={},
        covariate_selection={},
    )
    assert merged["description"] == "LLM-supplied study name"


def test_merge_client_metadata_does_not_mutate_input() -> None:
    spec = _minimal_valid_spec()
    merge_client_metadata(
        spec,
        cohort_definitions={"targetCohort": {"id": 42, "name": "X"}},
        negative_control={},
        covariate_selection={},
    )
    assert "cohortDefinitions" not in spec


def test_backfill_section_from_defaults_replaces_single_section() -> None:
    spec = _minimal_valid_spec()
    defaults = _minimal_valid_spec()
    defaults["fitOutcomeModelArgs"] = {"modelType": "cox", "stratified": True, "useCovariates": False, "inversePtWeighting": False, "prior": None, "control": None}
    spec["fitOutcomeModelArgs"] = {"modelType": "BROKEN"}
    out = backfill_section_from_defaults(spec, defaults, "fitOutcomeModelArgs")
    assert out["fitOutcomeModelArgs"]["modelType"] == "cox"
    assert out["fitOutcomeModelArgs"]["stratified"] is True
    assert out["createStudyPopArgs"] == spec["createStudyPopArgs"]  # other sections untouched


def test_backfill_section_rejects_unknown_section() -> None:
    spec = _minimal_valid_spec()
    defaults = _minimal_valid_spec()
    with pytest.raises(ValueError):
        backfill_section_from_defaults(spec, defaults, "unknownSection")


from study_agent_core.cohort_methods_spec_validation import cohort_methods_spec_to_shell_recommendation


def _full_spec_with_tar() -> dict:
    spec = _minimal_valid_spec()
    spec["createStudyPopArgs"]["washoutPeriod"] = 365
    spec["createStudyPopArgs"]["startAnchor"] = "cohort start"
    spec["createStudyPopArgs"]["riskWindowStart"] = 1
    spec["createStudyPopArgs"]["endAnchor"] = "cohort end"
    spec["createStudyPopArgs"]["riskWindowEnd"] = 365
    return spec


def test_cohort_methods_spec_to_shell_separates_tar_keys() -> None:
    spec = _full_spec_with_tar()
    out = cohort_methods_spec_to_shell_recommendation(
        cohort_methods_spec=spec,
        raw_description="desc",
        defaults_snapshot={"x": 1},
        profile_name="P",
        input_method="typed_text",
        rec_status="received",
    )
    assert out["mode"] == "free_text"
    assert out["source"] == "acp_flow"
    assert out["status"] == "received"
    assert out["profile_name"] == "P"
    assert out["raw_description"] == "desc"
    assert out["defaults_snapshot"] == {"x": 1}
    tar = out["time_at_risk"]
    assert tar["startAnchor"] == "cohort start"
    assert tar["riskWindowStart"] == 1
    assert tar["endAnchor"] == "cohort end"
    assert tar["riskWindowEnd"] == 365
    sp = out["study_population"]
    assert "startAnchor" not in sp
    assert "riskWindowStart" not in sp
    assert sp["washoutPeriod"] == 365
    assert sp["cohortMethodDataArgs"] == spec["getDbCohortMethodDataArgs"]
    assert out["propensity_score_adjustment"] == {
        "trimByPsArgs": spec["trimByPsArgs"],
        "matchOnPsArgs": spec["matchOnPsArgs"],
        "stratifyByPsArgs": spec["stratifyByPsArgs"],
        "createPsArgs": spec["createPsArgs"],
    }
    assert out["outcome_model"] == spec["fitOutcomeModelArgs"]
    assert out["deferred_inputs"]["function_argument_description"] == "implemented"


def test_cohort_methods_spec_to_shell_honors_rec_status_backfilled() -> None:
    out = cohort_methods_spec_to_shell_recommendation(
        cohort_methods_spec=_minimal_valid_spec(),
        raw_description="d",
        defaults_snapshot={},
        profile_name="X",
        input_method="description_argument",
        rec_status="backfilled",
    )
    assert out["status"] == "backfilled"
    assert out["input_method"] == "description_argument"


def test_cohort_methods_spec_to_shell_handles_missing_sections() -> None:
    out = cohort_methods_spec_to_shell_recommendation(
        cohort_methods_spec={},
        raw_description="d",
        defaults_snapshot={},
        profile_name="X",
        input_method="typed_text",
        rec_status="received",
    )
    assert out["study_population"] == {}
    assert out["time_at_risk"] == {}
    assert out["propensity_score_adjustment"] == {
        "trimByPsArgs": None,
        "matchOnPsArgs": None,
        "stratifyByPsArgs": None,
        "createPsArgs": None,
    }
    assert out["outcome_model"] == {}


def test_cohort_methods_spec_to_shell_does_not_mutate_input() -> None:
    spec = _full_spec_with_tar()
    snapshot = {"profile_name": "snap"}
    out = cohort_methods_spec_to_shell_recommendation(
        cohort_methods_spec=spec,
        raw_description="d",
        defaults_snapshot=snapshot,
        profile_name="X",
        input_method="typed_text",
        rec_status="received",
    )
    out["study_population"]["washoutPeriod"] = 9999
    out["defaults_snapshot"]["profile_name"] = "mutated"
    assert spec["createStudyPopArgs"]["washoutPeriod"] == 365
    assert snapshot["profile_name"] == "snap"
