import pytest

from study_agent_acp import server as acp_server
from study_agent_acp.mcp_client import StdioMCPClient
from study_agent_acp.agent import StudyAgent


@pytest.mark.acp
def test_acp_shutdown_closes_mcp_client():
    class FakeServer:
        def serve_forever(self) -> None:
            raise RuntimeError("stop")

    class FakeMCPClient:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    fake_server = FakeServer()
    fake_client = FakeMCPClient()

    try:
        acp_server._serve(fake_server, fake_client)
    except RuntimeError:
        pass

    assert fake_client.closed is True


@pytest.mark.acp
def test_mcp_health_check_success():
    class Portal:
        def call(self, func, *args, **kwargs):
            return func(*args, **kwargs)

    class Client:
        def __init__(self):
            self._portal = Portal()
            self._session = True

        def _ensure_session(self):
            return None

        def _ping(self):
            return {"ok": True}

        health_check = StdioMCPClient.health_check

    client = Client()
    assert client.health_check() == {"ok": True}


class StubMCPClient:
    def __init__(self) -> None:
        self.calls = []

    def list_tools(self):
        return []

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "phenotype_improvements":
            return {"plan": "ok", "phenotype_improvements": []}
        if name == "phenotype_prompt_bundle":
            return {"overview": "overview", "spec": "spec", "output_schema": {"type": "object"}}
        if name == "propose_concept_set_diff":
            return {"plan": "ok", "findings": [], "patches": [], "actions": [], "risk_notes": []}
        if name == "cohort_lint":
            return {"plan": "ok", "findings": [], "patches": [], "actions": [], "risk_notes": []}
        raise ValueError("unexpected tool")


@pytest.mark.acp
def test_flow_phenotype_improvements_calls_tool(monkeypatch):
    import study_agent_acp.agent as agent_module

    def fake_llm(prompt):
        return {"phenotype_improvements": []}

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)
    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_phenotype_improvements_flow(
        protocol_text="protocol",
        cohorts=[{"id": 1}, {"id": 2}],
        characterization_previews=[],
    )
    assert result["status"] == "ok"
    assert result["tool"] == "phenotype_improvements"
    assert result["cohort_count"] == 1


@pytest.mark.acp
def test_flow_concept_sets_review_calls_tool():
    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_concept_sets_review_flow(
        concept_set={"items": []},
        study_intent="intent",
    )
    assert result["status"] == "ok"
    assert result["tool"] == "propose_concept_set_diff"


@pytest.mark.acp
def test_flow_cohort_critique_calls_tool():
    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_cohort_critique_general_design_flow(cohort={"PrimaryCriteria": {}})
    assert result["status"] == "ok"
    assert result["tool"] == "cohort_lint"
