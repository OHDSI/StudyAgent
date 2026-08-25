import pytest

from study_agent_acp import server as acp_server
from study_agent_acp.agent import StudyAgent


def _post(monkeypatch, body):
    handler = acp_server.ACPRequestHandler.__new__(acp_server.ACPRequestHandler)
    handler.path = "/flows/phenotype_make_computable"
    handler.headers = {}
    handler.debug = False
    handler.agent = StudyAgent(mcp_client=None)
    handler.mcp_client = None
    handler.wfile = None
    handler.rfile = None
    captured = {}
    monkeypatch.setattr(acp_server, "_read_json", lambda _handler: body)
    monkeypatch.setattr(acp_server, "_write_json", lambda _handler, status, payload: captured.update(status=status, payload=payload))
    handler.do_POST()
    return captured


@pytest.mark.acp
def test_phenotype_make_computable_route_validates_and_dispatches(monkeypatch):
    received = {}

    def fake_flow(self, **kwargs):
        received.update(kwargs)
        return {"status": "ok", "capr": {"filename": "phenotype_definition.R"}}

    monkeypatch.setattr(StudyAgent, "run_phenotype_make_computable_flow", fake_flow)
    body = {"narrative_statement": "Earliest cirrhosis.", "confirmed_scope": True, "scope": {"index_event": "Cirrhosis"}, "concept_review_mode": "provided_only", "concept_sets": []}
    captured = _post(monkeypatch, body)
    assert captured["status"] == 200
    assert captured["payload"]["status"] == "ok"
    assert received["narrative_statement"] == "Earliest cirrhosis."
    assert received["concept_review_mode"] == "provided_only"


@pytest.mark.acp
def test_phenotype_make_computable_route_rejects_invalid_payload(monkeypatch):
    captured = _post(monkeypatch, {"narrative_statement": 42})
    assert captured["status"] == 422
    assert captured["payload"]["error"].startswith("invalid_payload:")
