import pytest

from study_agent_acp.agent import StudyAgent
import study_agent_acp.agent as agent_module
from study_agent_acp.llm_client import LLMCallResult


class StubMCPClient:
    def __init__(self) -> None:
        self.calls = []

    def list_tools(self):
        return []

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "phenotype_search":
            return {
                "results": [
                    {
                        "phenotype_id": "ohdsi:1",
                        "name": "Alpha",
                        "short_description": "A",
                        "executable_definition_status": "native_ohdsi",
                        "execution_readiness_score": 1.0,
                    },
                    {
                        "phenotype_id": "cipher:2",
                        "name": "Beta",
                        "short_description": "B",
                        "executable_definition_status": "codes_only",
                        "execution_readiness_score": 0.45,
                    },
                ]
            }
        if name == "phenotype_prompt_bundle":
            task = arguments["task"]
            return {
                "overview": f"overview {task}",
                "spec": f"spec {task}",
                "output_schema": {"type": "object", "title": task},
            }
        if name == "phenotype_fetch_summary":
            phenotype_id = arguments["phenotype_id"]
            if phenotype_id == "ohdsi:1":
                return {
                    "content": {
                        "phenotype_id": "ohdsi:1",
                        "name": "Alpha",
                        "short_description": "A",
                        "retrieval_keywords": ["alpha diagnosis"],
                        "retrieval_concept_labels": ["Alpha condition"],
                        "methodology_summary": "Native OHDSI cohort.",
                    }
                }
            if phenotype_id == "cipher:2":
                return {
                    "content": {
                        "phenotype_id": "cipher:2",
                        "name": "Beta",
                        "short_description": "B",
                        "retrieval_keywords": ["beta phenotype"],
                        "retrieval_concept_labels": ["Beta concept"],
                        "methodology_summary": "CIPHER code-based phenotype.",
                    }
                }
        raise ValueError(f"unexpected tool {name}")


@pytest.mark.acp
def test_acp_flow_candidate_limit(monkeypatch):
    llm_calls = []

    def fake_llm(prompt, required_keys=None):
        llm_calls.append((prompt, tuple(required_keys or [])))
        if len(llm_calls) == 1:
            return {
                "plan": "Extract recommendation intent facets.",
                "intent_facets": {"phenotype_role": "diagnosis", "condition_or_topic": "test"},
                "reasoning_notes": ["Use diagnosis-focused interpretation."],
            }
        if len(llm_calls) == 2:
            return {
                "plan": "Shortlist top executable candidate.",
                "intent_facets": {"phenotype_role": "diagnosis"},
                "shortlist_ids": ["ohdsi:1"],
                "needs_more_search": False,
                "reasoning_notes": ["Need native OHDSI option."],
            }
        return {
            "plan": "Recommend hydrated candidate.",
            "phenotype_recommendations": [
                {"phenotype_id": "ohdsi:1", "phenotype_name": "Alpha", "justification": "ok"}
            ],
        }

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)

    client = StubMCPClient()
    agent = StudyAgent(mcp_client=client)
    result = agent.run_phenotype_recommendation_flow(
        study_intent="test intent",
        top_k=5,
        max_results=5,
        candidate_limit=1,
    )
    assert result["status"] == "ok"
    assert result["candidate_limit"] == 1
    assert result["candidate_count"] == 1
    assert result["llm_used"] is True
    assert result["llm_status"] == "ok"
    assert result["fallback_reason"] is None
    assert result["diagnostics"]["llm_schema_valid"] is True
    assert result["planning"]["shortlist_ids"] == ["ohdsi:1"]
    recs = result["recommendations"]["phenotype_recommendations"]
    assert len(recs) == 1
    assert recs[0]["phenotype_id"] == "ohdsi:1"
    prompt_bundle_tasks = [args["task"] for name, args in client.calls if name == "phenotype_prompt_bundle"]
    assert prompt_bundle_tasks == [
        "phenotype_recommendation_intent_facets",
        "phenotype_recommendation_plan",
        "phenotype_recommendations",
    ]
    assert result["intent_facets"]["intent_facets"]["phenotype_role"] == "diagnosis"
    fetch_ids = [args["phenotype_id"] for name, args in client.calls if name == "phenotype_fetch_summary"]
    assert fetch_ids == ["ohdsi:1", "cipher:2", "ohdsi:1"]


@pytest.mark.acp
def test_acp_flow_plan_parse_failure_uses_stub_shortlist(monkeypatch):
    llm_calls = []

    def fake_llm(prompt, required_keys=None):
        llm_calls.append((prompt, tuple(required_keys or [])))
        if len(llm_calls) == 1:
            return {
                "plan": "Extract recommendation intent facets.",
                "intent_facets": {"phenotype_role": "diagnosis", "condition_or_topic": "test"},
                "reasoning_notes": ["Use diagnosis-focused interpretation."],
            }
        if len(llm_calls) == 2:
            return LLMCallResult(
                status="json_parse_failed",
                error="json_parse_failed",
                parse_stage="chat_completions_content:json_loads",
                duration_seconds=1.0,
                request_mode="chat_completions",
                content_text='{"plan": ',
            )
        return {
            "plan": "Recommend fallback-shortlisted candidate.",
            "phenotype_recommendations": [
                {"phenotype_id": "ohdsi:1", "phenotype_name": "Alpha", "justification": "ok"}
            ],
        }

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)

    client = StubMCPClient()
    agent = StudyAgent(mcp_client=client)
    result = agent.run_phenotype_recommendation_flow(
        study_intent="test intent",
        top_k=5,
        max_results=3,
        candidate_limit=1,
    )
    assert result["status"] == "ok"
    assert result["planning"]["mode"] == "stub"
    assert result["planning"]["shortlist_ids"] == ["ohdsi:1"]
    assert result["llm_used"] is True
    assert result["diagnostics"]["planning"]["llm_status"] == "json_parse_failed"


@pytest.mark.acp
def test_acp_flow_final_parse_failure_returns_explicit_fallback(monkeypatch):
    llm_calls = []

    def fake_llm(prompt, required_keys=None):
        llm_calls.append((prompt, tuple(required_keys or [])))
        if len(llm_calls) == 1:
            return {
                "plan": "Extract recommendation intent facets.",
                "intent_facets": {"phenotype_role": "diagnosis", "condition_or_topic": "test"},
                "reasoning_notes": ["Use diagnosis-focused interpretation."],
            }
        if len(llm_calls) == 2:
            return {
                "plan": "Shortlist both.",
                "intent_facets": {"phenotype_role": "diagnosis"},
                "shortlist_ids": ["ohdsi:1", "cipher:2"],
                "needs_more_search": False,
                "reasoning_notes": ["Compare executable and non-executable options."],
            }
        return LLMCallResult(
            status="json_parse_failed",
            error="json_parse_failed",
            parse_stage="chat_completions_content:json_loads",
            duration_seconds=12.5,
            request_mode="chat_completions",
            content_text='{"plan": ',
        )

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)

    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_phenotype_recommendation_flow(
        study_intent="test intent",
        top_k=5,
        max_results=3,
        candidate_limit=2,
    )
    assert result["status"] == "ok"
    assert result["llm_used"] is False
    assert result["llm_status"] == "json_parse_failed"
    assert result["fallback_reason"] == "llm_json_parse_failed"
    assert result["fallback_mode"] == "stub"
    assert result["diagnostics"]["llm_parse_stage"] == "chat_completions_content:json_loads"
    assert result["diagnostics"]["planning"]["llm_status"] == "ok"
    assert result["recommendations"]["mode"] == "stub"
