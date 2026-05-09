import pytest

from study_agent_mcp.tools import phenotype_prompt_bundle


class DummyMCP:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self, name: str):
        def decorator(fn):
            self.tools[name] = fn
            return fn

        return decorator


@pytest.mark.mcp
def test_prompt_bundle_intent_facets_schema() -> None:
    mcp = DummyMCP()
    phenotype_prompt_bundle.register(mcp)
    fn = mcp.tools["phenotype_prompt_bundle"]
    payload = fn("phenotype_recommendation_intent_facets")
    assert "overview" in payload
    assert "spec" in payload
    assert "output_schema" in payload
    assert payload["output_schema"]["title"] == "phenotype_recommendation_intent_facets_output"


@pytest.mark.mcp
def test_prompt_bundle_plan_schema() -> None:
    mcp = DummyMCP()
    phenotype_prompt_bundle.register(mcp)
    fn = mcp.tools["phenotype_prompt_bundle"]
    payload = fn("phenotype_recommendation_plan")
    assert "overview" in payload
    assert "spec" in payload
    assert "output_schema" in payload
    assert payload["output_schema"]["title"] == "phenotype_recommendation_plan_output"


@pytest.mark.mcp
def test_prompt_bundle_tool_returns_schema() -> None:
    mcp = DummyMCP()
    phenotype_prompt_bundle.register(mcp)
    fn = mcp.tools["phenotype_prompt_bundle"]
    payload = fn("phenotype_recommendations")
    assert "overview" in payload
    assert "spec" in payload
    assert "output_schema" in payload
    assert payload["output_schema"]["title"] == "phenotype_recommendations_output"


@pytest.mark.mcp
def test_cohort_methods_intent_split_bundle_schema() -> None:
    from study_agent_mcp.tools import cohort_methods_intent_split

    mcp = DummyMCP()
    cohort_methods_intent_split.register(mcp)
    fn = mcp.tools["cohort_methods_intent_split"]
    payload = fn()
    assert "overview" in payload
    assert "spec" in payload
    assert "output_schema" in payload
    assert payload["output_schema"]["title"] == "cohort_methods_intent_split_output"


@pytest.mark.mcp
def test_prompt_bundle_improvements_schema() -> None:
    mcp = DummyMCP()
    phenotype_prompt_bundle.register(mcp)
    fn = mcp.tools["phenotype_prompt_bundle"]
    payload = fn("phenotype_improvements")
    assert "overview" in payload
    assert "spec" in payload
    assert "output_schema" in payload
    assert payload["output_schema"]["title"] == "phenotype_improvements_output"


@pytest.mark.mcp
def test_lint_prompt_bundle_concept_sets_schema() -> None:
    from study_agent_mcp.tools import lint_prompt_bundle

    mcp = DummyMCP()
    lint_prompt_bundle.register(mcp)
    fn = mcp.tools["lint_prompt_bundle"]
    payload = fn("concept_sets_review")
    assert "overview" in payload
    assert "spec" in payload
    assert "output_schema" in payload
    assert payload["output_schema"]["title"] == "concept_sets_review_output"


@pytest.mark.mcp
def test_prompt_bundle_cohort_critique_schema() -> None:
    mcp = DummyMCP()
    phenotype_prompt_bundle.register(mcp)
    fn = mcp.tools["phenotype_prompt_bundle"]
    payload = fn("cohort_critique_general_design")
    assert "overview" in payload
    assert "spec" in payload
    assert "output_schema" in payload
    assert payload["output_schema"]["title"] == "cohort_critique_general_design_output"


@pytest.mark.mcp
def test_keeper_prompt_bundle_schema() -> None:
    from study_agent_mcp.tools import keeper_validation

    mcp = DummyMCP()
    keeper_validation.register(mcp)
    fn = mcp.tools["keeper_prompt_bundle"]
    payload = fn("Gastrointestinal bleeding")
    assert payload["output_schema"]["title"] == "phenotype_validation_review_output"
    assert payload["system_prompt"] == (
        "Act as a medical doctor reviewing a patient's healthcare data captured during routine clinical care.\n"
        "Write a brief clinical narrative and then determine whether the patient had Gastrointestinal bleeding.\n"
        "Remember that a diagnosis can be recorded as part of testing, and may not confirm disease.\n"
        "If evidence is insufficient, respond with label \"unknown\".\n"
        "Return JSON with label and rationale only."
    )


@pytest.mark.mcp
def test_keeper_build_prompt_uses_template() -> None:
    from study_agent_mcp.tools import keeper_validation

    mcp = DummyMCP()
    keeper_validation.register(mcp)
    fn = mcp.tools["keeper_build_prompt"]
    payload = fn(
        "Gastrointestinal bleeding",
        {
            "gender": "Male",
            "age_bucket": "40-44",
            "visit_context": "Inpatient Visit",
            "presentation": "Gastrointestinal hemorrhage",
            "prior_disease": "Peptic ulcer",
            "symptoms": "None",
            "comorbidities": "None",
            "prior_drugs": "celecoxib",
            "prior_treatments": "None",
            "diagnostic_procedures": "EGD",
            "measurements": "Hemoglobin low",
            "alternative_diagnosis": "None",
            "after_disease": "None",
            "after_drugs": "Naproxen",
            "after_treatments": "None",
            "death": "None",
        },
    )
    assert "Male, 40-44 yo; Visit: Inpatient Visit" in payload["prompt"]
    assert "Diagnoses recorded on the day of the visit: Gastrointestinal hemorrhage" in payload["prompt"]
    assert "Treatments recorded during or after the visit: Naproxen; None" in payload["prompt"]


@pytest.mark.mcp
def test_case_causal_review_prompt_bundle_schema() -> None:
    from study_agent_mcp.tools import case_causal_review

    mcp = DummyMCP()
    case_causal_review.register(mcp)
    fn = mcp.tools["case_causal_review_prompt_bundle"]
    payload = fn("Hepatic failure", "signal_validation")
    assert payload["output_schema"]["title"] == "case_causal_review_output"
    assert "Hepatic failure" in payload["system_prompt"]


@pytest.mark.mcp
def test_case_causal_review_build_prompt_contains_allowed_domains() -> None:
    from study_agent_mcp.tools import case_causal_review

    mcp = DummyMCP()
    case_causal_review.register(mcp)
    fn = mcp.tools["case_causal_review_build_prompt"]
    payload = fn(
        "Hepatic failure",
        {
            "case_id": "case-1",
            "case_summary": "Observed jaundice after exposure.",
            "index_event": {
                "domain": "index_event",
                "label": "Hepatic failure",
                "source_record_id": "reaction-1",
                "subrole": "index_event",
            },
            "candidate_items": [
                {
                    "domain": "drug_exposures",
                    "label": "Valproate",
                    "source_record_id": "drug-1",
                    "subrole": "primary_suspect",
                    "annotations": {"label_mentions_event": True},
                }
            ],
            "context_items": [],
            "case_metadata": {},
            "annotations": {"concept_set_id": "cs-1", "concept_set_version": 2, "concept_set_available_domains": ["drugs"]},
            "tool_hints": {"available_expansions": ["get_case_review_drug_label_details"], "prefetch_expansions": []},
        },
        "signal_validation",
        ["drug_exposures"],
        {},
    )
    assert '"adverse_event_name": "Hepatic failure"' in payload["prompt"]
    assert '"allowed_domains": [' in payload["prompt"]
    assert '"candidate_items": [' in payload["prompt"]


@pytest.mark.mcp
def test_workflow_context_dialogue_bundle_schema() -> None:
    from study_agent_mcp.tools import workflow_context_dialogue

    mcp = DummyMCP()
    workflow_context_dialogue.register(mcp)
    fn = mcp.tools["workflow_context_dialogue"]
    payload = fn()
    assert "overview" in payload
    assert "spec" in payload
    assert "output_schema" in payload
    assert payload["output_schema"]["title"] == "workflow_context_dialogue_output"
