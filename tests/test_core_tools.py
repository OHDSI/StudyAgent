import pytest

from study_agent_core.tools import (
    cohort_methods_intent_split,
    cohort_lint,
    phenotype_intent_split,
    phenotype_improvements,
    phenotype_recommendation_plan,
    phenotype_recommendations,
    phenotype_validation_review,
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
def test_phenotype_recommendation_plan_stub():
    catalog = [
        {"phenotype_id": "ohdsi:1", "phenotype_name": "Alpha"},
        {"phenotype_id": "cipher:2", "phenotype_name": "Beta"},
    ]
    result = phenotype_recommendation_plan("protocol", catalog, max_shortlist=1)
    assert result["mode"] == "stub"
    assert result["shortlist_ids"] == ["ohdsi:1"]


@pytest.mark.core
def test_phenotype_recommendation_plan_llm_filters():
    catalog = [
        {"phenotype_id": "ohdsi:1", "phenotype_name": "Alpha"},
        {"phenotype_id": "cipher:2", "phenotype_name": "Beta"},
    ]
    llm = {
        "plan": "plan",
        "intent_facets": {"phenotype_role": "diagnosis"},
        "shortlist_ids": ["cipher:2", "missing:999", "ohdsi:1"],
        "needs_more_search": False,
        "reasoning_notes": ["note"],
    }
    result = phenotype_recommendation_plan("protocol", catalog, max_shortlist=2, llm_result=llm)
    assert result["invalid_ids_filtered"] == ["missing:999"]
    assert result["shortlist_ids"] == ["cipher:2", "ohdsi:1"]


@pytest.mark.core
def test_phenotype_recommendation_plan_maps_bare_ids_and_falls_back():
    catalog = [
        {"phenotype_id": "ohdsi:170", "phenotype_name": "Alpha"},
        {"phenotype_id": "cipher:17590", "phenotype_name": "Beta"},
    ]
    llm = {
        "plan": "plan",
        "intent_facets": {"phenotype_role": "diagnosis"},
        "shortlist_ids": ["17590", "missing:999"],
        "needs_more_search": False,
        "reasoning_notes": ["note"],
    }
    result = phenotype_recommendation_plan("protocol", catalog, max_shortlist=2, llm_result=llm)
    assert result["shortlist_ids"] == ["cipher:17590"]
    assert result["invalid_ids_filtered"] == ["missing:999"]


@pytest.mark.core
def test_phenotype_recommendation_plan_coerces_string_reasoning_notes():
    catalog = [
        {"phenotype_id": "ohdsi:1", "phenotype_name": "Alpha"},
    ]
    llm = {
        "plan": "plan",
        "intent_facets": "not a dict",
        "shortlist_ids": ["ohdsi:1"],
        "needs_more_search": False,
        "reasoning_notes": "single note",
    }
    result = phenotype_recommendation_plan("protocol", catalog, max_shortlist=1, llm_result=llm)
    assert result["intent_facets"] == {}
    assert result["reasoning_notes"] == ["single note"]


@pytest.mark.core
def test_phenotype_recommendations_stub():
    catalog = [
        {"phenotype_id": "ohdsi:1", "phenotype_name": "Alpha"},
        {"phenotype_id": "cipher:2", "phenotype_name": "Beta"},
    ]
    result = phenotype_recommendations("protocol", catalog, max_results=1)
    assert result["mode"] == "stub"
    assert len(result["phenotype_recommendations"]) == 1


@pytest.mark.core
def test_phenotype_recommendations_llm_filters():
    catalog = [
        {"phenotype_id": "ohdsi:1", "phenotype_name": "Alpha"},
        {"phenotype_id": "cipher:2", "phenotype_name": "Beta"},
    ]
    llm = {
        "phenotype_recommendations": [
            {"phenotype_id": "ohdsi:1", "phenotype_name": "Alpha", "justification": "ok"},
            {"phenotype_id": "missing:999", "phenotype_name": "Nope"},
        ]
    }
    result = phenotype_recommendations("protocol", catalog, max_results=2, llm_result=llm)
    assert result["invalid_ids_filtered"] == ["missing:999"]
    assert len(result["phenotype_recommendations"]) == 1


@pytest.mark.core
def test_phenotype_recommendations_maps_bare_ids_and_falls_back():
    catalog = [
        {"phenotype_id": "ohdsi:181", "phenotype_name": "Alpha"},
        {"phenotype_id": "cipher:17590", "phenotype_name": "Beta"},
    ]
    llm = {
        "plan": "plan",
        "phenotype_recommendations": [
            {"phenotype_id": "17590", "phenotype_name": "Beta", "justification": "ok"},
            {"phenotype_id": "missing:999", "phenotype_name": "Nope"},
        ]
    }
    result = phenotype_recommendations("protocol", catalog, max_results=2, llm_result=llm)
    assert result["phenotype_recommendations"][0]["phenotype_id"] == "cipher:17590"
    assert result["invalid_ids_filtered"] == ["missing:999"]


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


@pytest.mark.core
def test_phenotype_validation_review_stub():
    result = phenotype_validation_review("GI bleed")
    assert result["mode"] == "stub"
    assert result["label"] == "unknown"
    assert "phenotype_improvements" not in result


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


@pytest.mark.core
def test_phenotype_intent_split_requires_llm():
    result = phenotype_intent_split("intent", llm_result=None)
    assert result["error"] == "no_llm_response"


@pytest.mark.core
def test_phenotype_intent_split_llm():
    llm = {
        "plan": "plan",
        "target_statement": "Target",
        "outcome_statement": "Outcome",
        "rationale": "Because",
        "questions": ["Q1"],
    }
    result = phenotype_intent_split("intent", llm_result=llm)
    assert result["target_statement"] == "Target"
    assert result["outcome_statement"] == "Outcome"


@pytest.mark.core
def test_cohort_methods_intent_split_llm():
    llm = {
        "status": "ok",
        "plan": "plan",
        "target_statement": "Metformin users",
        "comparator_statement": "Sulfonylurea users",
        "outcome_statement": "GI bleeding",
        "outcome_statements": ["GI bleeding", "Stroke"],
        "rationale": "Because",
        "questions": [],
    }
    result = cohort_methods_intent_split("intent", llm_result=llm)
    assert result["status"] == "ok"
    assert result["target_statement"] == "Metformin users"
    assert result["comparator_statement"] == "Sulfonylurea users"
    assert result["outcome_statement"] == "GI bleeding"
    assert result["outcome_statements"] == ["GI bleeding", "Stroke"]


@pytest.mark.core
def test_cohort_methods_intent_split_backfills_outcome_statements():
    llm = {
        "status": "ok",
        "plan": "plan",
        "target_statement": "Metformin users",
        "comparator_statement": "Sulfonylurea users",
        "outcome_statement": "GI bleeding",
        "rationale": "Because",
        "questions": [],
    }
    result = cohort_methods_intent_split("intent", llm_result=llm)
    assert result["outcome_statement"] == "GI bleeding"
    assert result["outcome_statements"] == ["GI bleeding"]


@pytest.mark.core
def test_cohort_methods_intent_split_requires_comparator_when_ok():
    llm = {
        "status": "ok",
        "plan": "plan",
        "target_statement": "Metformin users",
        "comparator_statement": "",
        "outcome_statement": "GI bleeding",
        "outcome_statements": ["GI bleeding"],
        "rationale": "Because",
    }
    result = cohort_methods_intent_split("intent", llm_result=llm)
    assert result["error"] == "invalid_cohort_methods_intent_split"
    assert result["missing"] == ["comparator_statement"]


@pytest.mark.core
def test_cohort_methods_intent_split_allows_clarification():
    llm = {
        "status": "needs_clarification",
        "plan": "plan",
        "target_statement": "",
        "comparator_statement": "",
        "outcome_statement": "",
        "outcome_statements": [],
        "rationale": "Intent is underspecified.",
        "questions": ["What exposure should define the target cohort?"],
    }
    result = cohort_methods_intent_split("intent", llm_result=llm)
    assert result["status"] == "needs_clarification"
    assert result["questions"] == ["What exposure should define the target cohort?"]
