import pytest

from study_agent_core.tools import (
    cohort_lint,
    phenotype_improvements,
    phenotype_recommendations,
    propose_concept_set_diff,
)


@pytest.mark.core
def test_propose_concept_set_diff_empty():
    result = propose_concept_set_diff([], "test intent")
    assert any(f.get("id") == "empty_concept_set" for f in result["findings"])


@pytest.mark.core
def test_propose_concept_set_diff_descendants_action():
    concept_set = [
        {
            "concept": {"conceptId": 1, "domainId": "Drug", "conceptClassId": "Ingredient"},
            "includeDescendants": False,
        }
    ]
    result = propose_concept_set_diff(concept_set, "test intent")
    assert any(a.get("type") == "set_include_descendants" for a in result["actions"])


@pytest.mark.core
def test_cohort_lint_washout_and_inverted():
    cohort = {
        "PrimaryCriteria": {"ObservationWindow": {"PriorDays": 0}},
        "InclusionRules": [{"window": {"start": 10, "end": 5}}],
    }
    result = cohort_lint(cohort)
    ids = {f.get("id") for f in result["findings"]}
    assert "missing_washout" in ids
    assert "inverted_window_0" in ids


@pytest.mark.core
def test_phenotype_recommendations_stub():
    catalog = [
        {"cohortId": 1, "cohortName": "Alpha"},
        {"cohortId": 2, "cohortName": "Beta"},
    ]
    result = phenotype_recommendations("protocol", catalog, max_results=1)
    assert result["mode"] == "stub"
    assert len(result["phenotype_recommendations"]) == 1


@pytest.mark.core
def test_phenotype_recommendations_llm_filters():
    catalog = [
        {"cohortId": 1, "cohortName": "Alpha"},
        {"cohortId": 2, "cohortName": "Beta"},
    ]
    llm = {
        "phenotype_recommendations": [
            {"cohortId": 1, "cohortName": "Alpha", "justification": "ok"},
            {"cohortId": 999, "cohortName": "Nope"},
        ]
    }
    result = phenotype_recommendations("protocol", catalog, max_results=2, llm_result=llm)
    assert result["invalid_ids_filtered"] == [999]
    assert len(result["phenotype_recommendations"]) == 1


@pytest.mark.core
def test_phenotype_improvements_filters_targets():
    cohorts = [{"id": 10}, {"id": 20}]
    llm = {
        "phenotype_improvements": [
            {"targetCohortId": 10, "suggestion": "good"},
            {"targetCohortId": 999, "suggestion": "bad"},
        ],
        "code_suggestion": {"language": "R", "summary": "example", "snippet": "x"},
    }
    result = phenotype_improvements("protocol", cohorts, llm_result=llm)
    assert result["invalid_targets_filtered"] == [999]
    assert len(result["phenotype_improvements"]) == 1


@pytest.mark.core
def test_phenotype_improvements_remaps_single_target():
    cohorts = [{"id": 33}]
    llm = {
        "phenotype_improvements": [
            {"targetCohortId": 999, "suggestion": "fix"},
        ]
    }
    result = phenotype_improvements("protocol", cohorts, llm_result=llm)
    assert len(result["phenotype_improvements"]) == 1
    assert result["phenotype_improvements"][0]["targetCohortId"] == 33
