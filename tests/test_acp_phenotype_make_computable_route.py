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


@pytest.mark.acp
def test_phenotype_review_session_routes_page_and_download(monkeypatch):
    handler = acp_server.ACPRequestHandler.__new__(acp_server.ACPRequestHandler)
    handler.path = "/flows/phenotype_make_computable/reviews/review123/candidates?offset=2&limit=5"
    handler.headers = {}
    handler.debug = False
    handler.mcp_client = None
    handler.agent = type("ReviewAgent", (), {
        "get_phenotype_review_candidates": staticmethod(lambda review_id, offset, limit: {"review_id": review_id, "offset": offset, "limit": limit, "candidates": []}),
        "get_phenotype_review_proposal": staticmethod(lambda review_id: {"review_id": review_id, "proposed_plan": {}}),
        "get_phenotype_review_manifest": staticmethod(lambda review_id: {"review_id": review_id, "schema_version": 1}),
        "get_phenotype_review_csv": staticmethod(lambda review_id: "concept_id\n1\n"),
    })()
    captured = {}
    monkeypatch.setattr(acp_server, "_write_json", lambda _handler, status, payload: captured.update(status=status, payload=payload))
    handler.do_GET()
    assert captured == {"status": 200, "payload": {"review_id": "review123", "offset": 2, "limit": 5, "candidates": []}}

    handler.path = "/flows/phenotype_make_computable/reviews/review123/candidates.csv"
    captured = {}
    monkeypatch.setattr(acp_server, "_write_text", lambda _handler, status, body, content_type, filename=None: captured.update(status=status, body=body, content_type=content_type, filename=filename))
    handler.do_GET()
    assert captured["status"] == 200
    assert captured["body"] == "concept_id\n1\n"
    assert captured["filename"] == "phenotype_review_review123.csv"

    handler.path = "/flows/phenotype_make_computable/reviews/review123/manifest"
    captured = {}
    handler.do_GET()
    assert captured == {"status": 200, "payload": {"review_id": "review123", "schema_version": 1}}


def test_write_text_strips_response_splitting_characters_from_filename():
    headers = []

    class Handler:
        debug = False

        def send_response(self, _status):
            pass

        def send_header(self, name, value):
            headers.append((name, value))

        def end_headers(self):
            pass

        class wfile:
            @staticmethod
            def write(_body):
                pass

    acp_server._write_text(
        Handler(),
        200,
        "concept_id\n1\n",
        "text/csv; charset=utf-8",
        filename='review.csv\r\nX-Injected: true"',
    )

    assert ("Content-Disposition", 'attachment; filename="review.csvX-Injected: true"') in headers
