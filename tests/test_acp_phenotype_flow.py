import pytest

from study_agent_acp.agent import StudyAgent
import study_agent_acp.agent as agent_module


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
                    {"cohortId": 1, "name": "Alpha", "short_description": "A"},
                    {"cohortId": 2, "name": "Beta", "short_description": "B"},
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
                {"cohortId": 1, "cohortName": "Alpha", "justification": "ok"}
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
    recs = result["recommendations"]["phenotype_recommendations"]
    assert len(recs) == 1
