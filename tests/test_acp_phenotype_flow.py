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
                    {"phenotype_id": "ohdsi:1", "name": "Alpha", "short_description": "A"},
                    {"phenotype_id": "cipher:2", "name": "Beta", "short_description": "B"},
                ]
            }
        if name == "phenotype_prompt_bundle":
            return {
                "overview": "overview",
                "spec": "spec",
                "output_schema": {"type": "object"},
            }
        raise ValueError("unexpected tool")


@pytest.mark.acp
def test_acp_flow_candidate_limit(monkeypatch):
    def fake_llm(prompt):
        return {
            "phenotype_recommendations": [
                {"phenotype_id": "ohdsi:1", "phenotype_name": "Alpha", "justification": "ok"}
            ]
        }

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)

    agent = StudyAgent(mcp_client=StubMCPClient())
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
    recs = result["recommendations"]["phenotype_recommendations"]
    assert len(recs) == 1


@pytest.mark.acp
def test_acp_flow_parse_failure_returns_explicit_fallback(monkeypatch):
    def fake_llm(prompt, required_keys=None):
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
    assert result["recommendations"]["mode"] == "stub"
