import json
import urllib.error

import pytest

from study_agent_mcp.tools import case_causal_review
from study_agent_mcp.tools import _service_client


class DummyMCP:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self, name: str):
        def decorator(fn):
            self.tools[name] = fn
            return fn

        return decorator


class _FakeResponse:
    def __init__(self, payload: dict, status: int = 200) -> None:
        self._payload = json.dumps(payload).encode("utf-8")
        self.status = status

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def _registered_tools():
    mcp = DummyMCP()
    case_causal_review.register(mcp)
    return mcp.tools


@pytest.mark.mcp
def test_case_causal_review_sanitize_row_supports_candidate_and_context_items() -> None:
    tools = _registered_tools()
    payload = tools["case_causal_review_sanitize_row"](
        {
            "case_id": "case-1",
            "case_summary": "Bleeding event after anticoagulant exposure.",
            "index_event": {
                "domain": "index_event",
                "label": "Gastrointestinal bleeding",
                "source_record_id": "reaction-1",
                "why_observed": "Selected event",
            },
            "candidate_items": [
                {
                    "domain": "Drug Exposures",
                    "label": "Warfarin",
                    "source_record_id": "drug-1",
                    "source_kind": "reported_drug",
                    "subrole": "primary_suspect",
                    "annotations": {"has_disproportional_signal": True},
                }
            ],
            "context_items": [
                {
                    "domain": "Labs",
                    "label": "INR 4.2",
                    "source_record_id": "lab-1",
                    "source_kind": "lab",
                    "subrole": "proximate_marker",
                }
            ],
            "annotations": {
                "concept_set_id": "uuid",
                "concept_set_version": 1,
                "concept_set_available_domains": ["drugs", "symptoms"],
            },
            "tool_hints": {
                "available_expansions": [
                    "get_case_review_concept_set_domain",
                    "get_case_review_drug_signal_details",
                ],
                "prefetch_expansions": ["get_case_review_drug_signal_details"],
            },
        },
        ["drug_exposures", "labs"],
    )
    sanitized = payload["sanitized_row"]
    assert sanitized["candidate_items"][0]["subrole"] == "primary_suspect"
    assert sanitized["context_items"][0]["subrole"] == "proximate_marker"
    assert sanitized["tool_hints"]["prefetch_expansions"] == ["get_case_review_drug_signal_details"]


@pytest.mark.mcp
def test_case_causal_review_sanitize_row_preserves_controlled_identifier_fields() -> None:
    tools = _registered_tools()
    payload = tools["case_causal_review_sanitize_row"](
        {
            "case_id": "case-1",
            "case_summary": "Bleeding event after anticoagulant exposure.",
            "index_event": {
                "domain": "index_event",
                "label": "Gastrointestinal bleeding",
                "source_record_id": "reaction-1",
                "annotations": {"adverse_event_meddra_id": "10075534", "adverse_event_concept_id": 321},
            },
            "candidate_items": [
                {
                    "domain": "Drug Exposures",
                    "label": "Warfarin",
                    "source_record_id": "drug-1",
                    "source_kind": "reported_drug",
                    "subrole": "primary_suspect",
                    "annotations": {"ingred_rxcui": "36567", "ingredient_concept_id": 123},
                }
            ],
            "context_items": [],
        },
        ["drug_exposures"],
    )
    annotations = payload["sanitized_row"]["candidate_items"][0]["annotations"]
    index_annotations = payload["sanitized_row"]["index_event"]["annotations"]
    assert annotations["ingred_rxcui"] == "36567"
    assert annotations["ingredient_concept_id"] == 123
    assert index_annotations["adverse_event_meddra_id"] == "10075534"
    assert index_annotations["adverse_event_concept_id"] == 321


@pytest.mark.mcp
def test_case_causal_review_sanitize_row_redacts_zip_in_free_text() -> None:
    tools = _registered_tools()
    payload = tools["case_causal_review_sanitize_row"](
        {
            "case_id": "case-1",
            "case_summary": "Patient reported event near ZIP 15213 after exposure.",
            "index_event": {
                "domain": "index_event",
                "label": "Gastrointestinal bleeding",
                "source_record_id": "reaction-1",
            },
            "candidate_items": [
                {
                    "domain": "Drug Exposures",
                    "label": "Warfarin",
                    "source_record_id": "drug-1",
                    "source_kind": "reported_drug",
                    "subrole": "primary_suspect",
                    "why_observed": "Filled in 15213 and later implicated",
                }
            ],
            "context_items": [],
        },
        ["drug_exposures"],
    )
    sanitized = payload["sanitized_row"]
    assert "[REDACTED_ZIP]" in sanitized["case_summary"]
    assert "[REDACTED_ZIP]" in sanitized["candidate_items"][0]["why_observed"]


@pytest.mark.mcp
def test_case_causal_review_sanitize_row_rejects_phi() -> None:
    tools = _registered_tools()
    payload = tools["case_causal_review_sanitize_row"](
        {
            "case_id": "case-2",
            "case_summary": "Unsafe payload",
            "index_event": {
                "domain": "index_event",
                "label": "Cystitis",
                "source_record_id": "reaction-4",
            },
            "candidate_items": [
                {"domain": "drug_exposures", "label": "Ketamine", "source_record_id": "drug-1"}
            ],
            "case_metadata": {"birth_date": "2020-01-01"},
        },
        [],
    )
    assert payload["error"] == "unsafe_case_row"


@pytest.mark.mcp
def test_case_causal_review_sanitize_row_rejects_person_id_phi_key() -> None:
    tools = _registered_tools()
    payload = tools["case_causal_review_sanitize_row"](
        {
            "case_id": "case-2",
            "case_summary": "Unsafe payload",
            "index_event": {
                "domain": "index_event",
                "label": "Cystitis",
                "source_record_id": "reaction-4",
            },
            "candidate_items": [
                {"domain": "drug_exposures", "label": "Ketamine", "source_record_id": "drug-1"}
            ],
            "case_metadata": {"person_id": "12345"},
        },
        [],
    )
    assert payload["error"] == "unsafe_case_row"


@pytest.mark.mcp
def test_case_causal_review_build_prompt_keeps_candidate_and_context_items_distinct() -> None:
    tools = _registered_tools()
    payload = tools["case_causal_review_build_prompt"](
        "Cystitis",
        {
            "case_id": "25196051",
            "case_summary": "Single suspect-drug spontaneous report.",
            "index_event": {
                "domain": "index_event",
                "label": "Cystitis",
                "source_record_id": "reaction-4",
                "subrole": "index_event",
            },
            "candidate_items": [
                {
                    "domain": "drug_exposures",
                    "label": "Ketamine hydrochloride",
                    "source_record_id": "drug-1",
                    "source_kind": "reported_drug",
                    "subrole": "primary_suspect",
                    "why_observed": "Primary suspect drug",
                    "annotations": {"has_disproportional_signal": True},
                }
            ],
            "context_items": [
                {
                    "domain": "conditions",
                    "label": "Drug abuse",
                    "source_record_id": "reaction-5",
                    "source_kind": "reported_reaction",
                    "subrole": "contextual_factor",
                    "why_observed": "Additional reported reaction",
                    "annotations": {"concept_set_match": False},
                }
            ],
            "case_metadata": {"sex": "male", "timing_granularity": "coarse"},
            "annotations": {
                "concept_set_id": "uuid",
                "concept_set_version": 1,
                "concept_set_available_domains": ["doi", "drugs"],
            },
            "tool_hints": {
                "available_expansions": ["get_case_review_concept_set_domain"],
                "prefetch_expansions": [],
            },
        },
        "signal_validation",
        ["drug_exposures", "conditions"],
        {"get_case_review_concept_set_domain": [{"status": "ok", "domain_name": "drug_exposures"}]},
    )
    assert '"candidate_items": [' in payload["prompt"]
    assert '"context_items": [' in payload["prompt"]
    assert '"concept_set_id": "uuid"' in payload["prompt"]
    assert '"get_case_review_concept_set_domain"' in payload["prompt"]


@pytest.mark.mcp
def test_case_causal_review_parse_response_drops_unobserved_candidates_and_keeps_optional_fields() -> None:
    tools = _registered_tools()
    payload = tools["case_causal_review_parse_response"](
        {
            "candidates_by_domain": {
                "drug_exposures": [
                    {
                        "domain": "drug_exposures",
                        "label": "Warfarin",
                        "source_record_id": "drug-1",
                        "why_it_may_contribute": "Bleeding risk",
                        "confidence": "high",
                        "rank": 2,
                        "candidate_role": "primary_suspect",
                        "evidence_basis": "Signal annotation and temporal plausibility",
                    },
                    {
                        "domain": "drug_exposures",
                        "label": "Ibuprofen",
                        "source_record_id": "drug-99",
                        "why_it_may_contribute": "Not observed",
                        "confidence": "low",
                        "rank": 1,
                    }
                ]
            },
            "narrative": "Warfarin is a plausible contributor.",
            "mode": "case_causal_review",
            "diagnostics": {},
        },
        {
            "candidate_items": [
                {
                    "domain": "drug_exposures",
                    "label": "Warfarin",
                    "source_record_id": "drug-1",
                    "subrole": "primary_suspect",
                }
            ]
        },
        ["drug_exposures"],
    )
    kept = payload["candidates_by_domain"]["drug_exposures"]
    assert len(kept) == 1
    assert kept[0]["label"] == "Warfarin"
    assert kept[0]["rank"] == 1
    assert kept[0]["candidate_role"] == "primary_suspect"
    assert kept[0]["evidence_basis"] == "Signal annotation and temporal plausibility"
    assert payload["diagnostics"]["dropped_unobserved_count"] == 1


@pytest.mark.mcp
@pytest.mark.parametrize(
    ("tool_name", "kwargs", "expected_path", "expected_payload", "response_payload"),
    [
        (
            "get_case_review_concept_set_domain",
            {
                "concept_set_id": "uuid",
                "concept_set_version": 3,
                "domain_name": "drug_exposures",
                "limit": 25,
            },
            "/api/case-review-tools/concept-set-domain",
            {
                "concept_set_id": "uuid",
                "concept_set_version": 3,
                "domain_name": "drug_exposures",
                "limit": 25,
            },
            {"status": "ok", "domain_name": "drug_exposures", "items": [{"code": "123"}]},
        ),
        (
            "get_case_review_drug_signal_details",
            {
                "source_type": "signal_validation",
                "adverse_event_name": "Cystitis",
                "source_record_id": "drug-1",
                "report_lookup_key": {"primaryid": "report-1", "isr": None},
                "adverse_event_meddra_id": "789",
                "ingredient_concept_id": 123,
                "ingred_rxcui": "456",
                "adverse_event_concept_id": 321,
                "case_id": "case-1",
            },
            "/api/case-review-tools/drug-signal-details",
            {
                "source_type": "signal_validation",
                "adverse_event_name": "Cystitis",
                "source_record_id": "drug-1",
                "report_lookup_key": {"primaryid": "report-1", "isr": None},
                "adverse_event_meddra_id": "789",
                "ingredient_concept_id": 123,
                "ingred_rxcui": "456",
                "adverse_event_concept_id": 321,
                "case_id": "case-1",
                "outcome_concept_id": 321,
            },
            {"status": "ok", "source_record_id": "drug-1", "signal_score": 0.9},
        ),
        (
            "get_case_review_drug_label_details",
            {
                "source_type": "signal_validation",
                "adverse_event_name": "Cystitis",
                "source_record_id": "drug-1",
                "adverse_event_concept_id": 321,
                "adverse_event_meddra_id": "789",
                "ingredient_concept_id": 123,
                "ingred_rxcui": "456",
                "report_lookup_key": {"primaryid": None, "isr": "6526923"},
                "mention_limit": 5,
                "case_id": "case-1",
            },
            "/api/case-review-tools/drug-label-details",
            {
                "source_type": "signal_validation",
                "adverse_event_name": "Cystitis",
                "source_record_id": "drug-1",
                "adverse_event_concept_id": 321,
                "outcome_concept_id": 321,
                "adverse_event_meddra_id": "789",
                "ingredient_concept_id": 123,
                "ingred_rxcui": "456",
                "report_lookup_key": {"primaryid": None, "isr": "6526923"},
                "mention_limit": 5,
                "case_id": "case-1",
            },
            {"status": "ok", "source_record_id": "drug-1", "mentions": []},
        ),
        (
            "get_case_review_report_literature_stub",
            {
                "source_type": "signal_validation",
                "case_id": "case-1",
                "report_lookup_key": {"primaryid": None, "isr": "6526923"},
            },
            "/api/case-review-tools/report-literature-stub",
            {
                "source_type": "signal_validation",
                "case_id": "case-1",
                "report_lookup_key": {"primaryid": None, "isr": "6526923"},
            },
            {"status": "ok", "case_id": "case-1", "references": []},
        ),
    ],
)
def test_case_review_enrichment_tools_call_expected_pv_copilot_endpoint(
    monkeypatch,
    tool_name,
    kwargs,
    expected_path,
    expected_payload,
    response_payload,
) -> None:
    tools = _registered_tools()
    captured = {}

    def fake_urlopen(request, timeout=0):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["authorization"] = request.get_header("Authorization")
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse(response_payload)

    monkeypatch.setenv("PV_COPILOT_BASE_URL", "http://pv-copilot.test:8787")
    monkeypatch.setenv("PV_COPILOT_TOKEN", "secret-token")
    monkeypatch.setattr(_service_client.urllib.request, "urlopen", fake_urlopen)

    result = tools[tool_name](**kwargs)

    assert captured["url"] == f"http://pv-copilot.test:8787{expected_path}"
    assert captured["authorization"] == "Bearer secret-token"
    assert captured["payload"] == expected_payload
    assert result["status"] == "ok"
    for key, value in response_payload.items():
        assert result[key] == value


@pytest.mark.mcp
@pytest.mark.parametrize("provider_status", ["not_found", "unsupported"])
def test_case_review_enrichment_tools_preserve_nonfatal_provider_statuses(monkeypatch, provider_status: str) -> None:
    tools = _registered_tools()

    def fake_urlopen(request, timeout=0):
        return _FakeResponse({"status": provider_status, "source_record_id": "drug-1"})

    monkeypatch.setenv("PV_COPILOT_BASE_URL", "http://pv-copilot.test:8787")
    monkeypatch.setenv("PV_COPILOT_TOKEN", "secret-token")
    monkeypatch.setattr(_service_client.urllib.request, "urlopen", fake_urlopen)

    result = tools["get_case_review_drug_signal_details"](
        source_type="patient_profile",
        adverse_event_name="Hepatic failure",
        source_record_id="drug-1",
    )

    assert result["status"] == provider_status
    assert result["source_record_id"] == "drug-1"


@pytest.mark.mcp
def test_case_review_signal_and_label_tools_do_not_require_case_id(monkeypatch) -> None:
    tools = _registered_tools()
    captured = []

    def fake_urlopen(request, timeout=0):
        captured.append(json.loads(request.data.decode("utf-8")))
        return _FakeResponse({"status": "ok", "source_record_id": "drug-1"})

    monkeypatch.setenv("PV_COPILOT_BASE_URL", "http://pv-copilot.test:8787")
    monkeypatch.setenv("PV_COPILOT_TOKEN", "secret-token")
    monkeypatch.setattr(_service_client.urllib.request, "urlopen", fake_urlopen)

    tools["get_case_review_drug_signal_details"](
        source_type="signal_validation",
        adverse_event_name="Hepatic failure",
        source_record_id="drug-1",
    )
    tools["get_case_review_drug_label_details"](
        source_type="signal_validation",
        adverse_event_name="Hepatic failure",
        source_record_id="drug-1",
    )

    assert all("case_id" not in payload for payload in captured)
    assert all(payload["source_record_id"] == "drug-1" for payload in captured)


@pytest.mark.mcp
def test_case_review_label_and_signal_tools_preserve_external_identifier_and_legacy_mapping(monkeypatch) -> None:
    tools = _registered_tools()
    captured = []

    def fake_urlopen(request, timeout=0):
        captured.append(json.loads(request.data.decode("utf-8")))
        return _FakeResponse({"status": "ok", "source_record_id": "drug-1"})

    monkeypatch.setenv("PV_COPILOT_BASE_URL", "http://pv-copilot.test:8787")
    monkeypatch.setenv("PV_COPILOT_TOKEN", "secret-token")
    monkeypatch.setattr(_service_client.urllib.request, "urlopen", fake_urlopen)

    tools["get_case_review_drug_signal_details"](
        source_type="signal_validation",
        adverse_event_name="Hepatic failure",
        source_record_id="drug-1",
        adverse_event_concept_id=999,
    )
    tools["get_case_review_drug_label_details"](
        source_type="signal_validation",
        adverse_event_name="Hepatic failure",
        source_record_id="drug-1",
        adverse_event_concept_id=999,
        adverse_event_meddra_id="1001",
    )

    assert all(payload["source_record_id"] == "drug-1" for payload in captured)
    assert all(payload["adverse_event_concept_id"] == 999 for payload in captured)
    assert all(payload["outcome_concept_id"] == 999 for payload in captured)
    assert "adverse_event_meddra_id" not in captured[0]
    assert captured[1]["adverse_event_meddra_id"] == "1001"


@pytest.mark.mcp
def test_case_review_enrichment_tools_degrade_gracefully_on_transport_failure(monkeypatch) -> None:
    tools = _registered_tools()

    def fake_urlopen(request, timeout=0):
        raise urllib.error.URLError("connection refused")

    monkeypatch.setenv("PV_COPILOT_BASE_URL", "http://pv-copilot.test:8787")
    monkeypatch.setenv("PV_COPILOT_TOKEN", "secret-token")
    monkeypatch.setattr(_service_client.urllib.request, "urlopen", fake_urlopen)

    result = tools["get_case_review_report_literature_stub"](
        source_type="signal_validation",
        case_id="case-1",
        report_lookup_key="report-1",
    )

    assert result["status"] == "unavailable"
    assert result["error"] == "transport_error"


@pytest.mark.mcp
def test_service_client_resolves_base_url_from_host_port(monkeypatch) -> None:
    monkeypatch.delenv("PV_COPILOT_BASE_URL", raising=False)
    monkeypatch.delenv("PV_COPILOT_URL", raising=False)
    monkeypatch.setenv("PV_COPILOT_HOST", "pv-copilot.test")
    monkeypatch.setenv("PV_COPILOT_PORT", "8787")
    monkeypatch.setenv("PV_COPILOT_SCHEME", "http")
    monkeypatch.setenv("PV_COPILOT_API_PREFIX", "")

    assert _service_client.resolve_service_base_url("PV_COPILOT") == "http://pv-copilot.test:8787"


@pytest.mark.mcp
def test_service_client_resolves_token_and_timeout(monkeypatch) -> None:
    monkeypatch.setenv("PV_COPILOT_API_TOKEN", "secret-token")
    monkeypatch.setenv("PV_COPILOT_TIMEOUT", "45")

    assert _service_client.resolve_service_token("PV_COPILOT") == "secret-token"
    assert _service_client.resolve_service_timeout("PV_COPILOT") == 45


@pytest.mark.mcp
def test_service_client_post_json_service_allows_no_auth_when_not_required(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout=0):
        captured["authorization"] = request.get_header("Authorization")
        captured["payload"] = json.loads(request.data.decode("utf-8"))
        return _FakeResponse({"status": "ok", "value": 1})

    monkeypatch.setenv("PV_COPILOT_BASE_URL", "http://pv-copilot.test:8787")
    monkeypatch.delenv("PV_COPILOT_TOKEN", raising=False)
    monkeypatch.delenv("PV_COPILOT_API_TOKEN", raising=False)
    monkeypatch.delenv("PV_COPILOT_BEARER_TOKEN", raising=False)
    monkeypatch.setattr(_service_client.urllib.request, "urlopen", fake_urlopen)

    result = _service_client.post_json_service(
        tool_name="demo_tool",
        service_prefix="PV_COPILOT",
        path="/api/demo",
        payload={"x": 1},
        allowed_statuses=("ok",),
        require_auth=False,
    )

    assert captured["authorization"] is None
    assert captured["payload"] == {"x": 1}
    assert result["status"] == "ok"
    assert result["value"] == 1


@pytest.mark.mcp
def test_service_client_requires_auth_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("PV_COPILOT_BASE_URL", "http://pv-copilot.test:8787")
    monkeypatch.delenv("PV_COPILOT_TOKEN", raising=False)
    monkeypatch.delenv("PV_COPILOT_API_TOKEN", raising=False)
    monkeypatch.delenv("PV_COPILOT_BEARER_TOKEN", raising=False)

    result = _service_client.post_json_service(
        tool_name="demo_tool",
        service_prefix="PV_COPILOT",
        path="/api/demo",
        payload={"x": 1},
        allowed_statuses=("ok",),
        require_auth=True,
    )

    assert result["status"] == "unavailable"
    assert result["error"] == "pv_copilot_auth_unconfigured"
