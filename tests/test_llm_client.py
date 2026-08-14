import json

import pytest

from study_agent_acp import llm_client


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status

    def read(self):
        return self._payload.encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


@pytest.mark.acp
def test_call_llm_keyless_mode_omits_authorization_header(monkeypatch):
    payload = {"choices": [{"message": {"content": "{\"advice\":\"ok\"}"}}]}
    observed = {}

    def fake_urlopen(request, timeout=0):
        observed["authorization"] = request.get_header("Authorization")
        return _FakeResponse(json.dumps(payload))

    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_AUTHENTICATION", "none")
    monkeypatch.setattr(llm_client.urllib.request, "urlopen", fake_urlopen)

    result = llm_client.call_llm("prompt", required_keys=["advice"])
    assert result.status == "ok"
    assert observed["authorization"] is None


@pytest.mark.acp
def test_call_llm_diagnostic_flags_are_independent(monkeypatch):
    payload = {"choices": [{"message": {"content": "{\"advice\":\"ok\"}"}}]}
    messages: list[str] = []

    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_AUTHENTICATION", "none")
    monkeypatch.setenv("LLM_LOG", "1")
    monkeypatch.setenv("LLM_LOG_PROMPT", "1")
    monkeypatch.setenv("LLM_LOG_RESPONSE", "1")
    monkeypatch.setenv("LLM_LOG_JSON", "1")
    monkeypatch.setattr(llm_client, "_log_llm", messages.append)
    monkeypatch.setattr(
        llm_client.urllib.request,
        "urlopen",
        lambda request, timeout=0: _FakeResponse(json.dumps(payload)),
    )

    result = llm_client.call_llm("diagnostic prompt", required_keys=["advice"])

    assert result.status == "ok"
    assert any(message.startswith("CONFIG >") for message in messages)
    assert "OUTGOING PROMPT > diagnostic prompt" in messages
    assert any(message.startswith("RAW RESPONSE >") for message in messages)
    assert any(message.startswith("JSON > {") for message in messages)


@pytest.mark.acp
def test_missing_key_logging_explains_required_authentication(monkeypatch):
    messages: list[str] = []

    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("LLM_AUTHENTICATION", "required")
    monkeypatch.setenv("LLM_LOG", "1")
    monkeypatch.setenv("LLM_LOG_PROMPT", "1")
    monkeypatch.setattr(llm_client, "_log_llm", messages.append)

    result = llm_client.call_llm("diagnostic prompt")

    assert result.error == "missing_api_key"
    assert "OUTGOING PROMPT > diagnostic prompt" in messages
    assert any("llm.authentication: none" in message for message in messages)


@pytest.mark.acp
def test_call_llm_chat_completions_success(monkeypatch):
    payload = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "plan": "ok",
                            "phenotype_recommendations": [{"phenotype_id": "ohdsi:1"}],
                        }
                    )
                }
            }
        ]
    }

    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_USE_RESPONSES", "0")
    monkeypatch.setattr(llm_client.urllib.request, "urlopen", lambda request, timeout=0: _FakeResponse(json.dumps(payload)))

    result = llm_client.call_llm("prompt", required_keys=["plan", "phenotype_recommendations"])
    assert result.status == "ok"
    assert result.parsed_content["plan"] == "ok"
    assert result.schema_valid is True
    assert result.request_mode == "chat_completions"


@pytest.mark.acp
def test_call_llm_strips_fenced_json(monkeypatch):
    payload = {
        "choices": [
            {
                "message": {
                    "content": "```json\n{\"plan\":\"ok\",\"phenotype_recommendations\":[]}\n```"
                }
            }
        ]
    }

    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_USE_RESPONSES", "0")
    monkeypatch.setattr(llm_client.urllib.request, "urlopen", lambda request, timeout=0: _FakeResponse(json.dumps(payload)))

    result = llm_client.call_llm("prompt", required_keys=["plan", "phenotype_recommendations"])
    assert result.status == "ok"
    assert result.parsed_content["phenotype_recommendations"] == []


@pytest.mark.acp
def test_call_llm_strips_reasoning_prefix(monkeypatch):
    payload = {
        "choices": [
            {
                "message": {
                    "content": "<unused_reasoning>thought</unused_reasoning>\n{\"advice\":\"Refine intent\"}"
                }
            }
        ]
    }

    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_USE_RESPONSES", "0")
    monkeypatch.setattr(llm_client.urllib.request, "urlopen", lambda request, timeout=0: _FakeResponse(json.dumps(payload)))

    result = llm_client.call_llm("prompt", required_keys=["advice"])
    assert result.status == "ok"
    assert result.parsed_content["advice"] == "Refine intent"


@pytest.mark.acp
def test_call_llm_malformed_truncated_json(monkeypatch):
    payload = {
        "choices": [
            {
                "message": {
                    "content": "{\"plan\":\"oops\""
                }
            }
        ]
    }

    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_USE_RESPONSES", "0")
    monkeypatch.setattr(llm_client.urllib.request, "urlopen", lambda request, timeout=0: _FakeResponse(json.dumps(payload)))

    result = llm_client.call_llm("prompt", required_keys=["plan"])
    assert result.status == "json_parse_failed"
    assert result.parse_stage.endswith("json_brace_extract")


@pytest.mark.acp
def test_call_llm_responses_mode_mismatch(monkeypatch):
    payload = {"choices": [{"message": {"content": "{\"advice\":\"hi\"}"}}]}

    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_USE_RESPONSES", "1")
    monkeypatch.setattr(llm_client.urllib.request, "urlopen", lambda request, timeout=0: _FakeResponse(json.dumps(payload)))

    result = llm_client.call_llm("prompt", required_keys=["advice"])
    assert result.status == "json_parse_failed"
    assert result.request_mode == "responses"


@pytest.mark.acp
def test_call_llm_missing_required_keys(monkeypatch):
    payload = {
        "choices": [
            {
                "message": {
                    "content": "{\"advice\":\"Refine intent\"}"
                }
            }
        ]
    }

    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_USE_RESPONSES", "0")
    monkeypatch.setattr(llm_client.urllib.request, "urlopen", lambda request, timeout=0: _FakeResponse(json.dumps(payload)))

    result = llm_client.call_llm("prompt", required_keys=["advice", "next_steps"])
    assert result.status == "schema_mismatch"
    assert result.missing_keys == ["next_steps"]


@pytest.mark.acp
def test_call_llm_uses_later_json_object_matching_required_keys(monkeypatch):
    schema_echo = {
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "target_statement": {"type": "string"},
        },
    }
    actual_output = {
        "status": "ok",
        "target_statement": "Metformin initiators.",
        "comparator_statement": "Sulfonylurea initiators.",
        "outcome_statement": "GI bleeding.",
        "outcome_statements": ["GI bleeding.", "MACE."],
        "rationale": "Comparative cohort method intent.",
    }
    payload = {
        "choices": [
            {
                "message": {
                    "content": f"{json.dumps(schema_echo)}\n{json.dumps(actual_output)}"
                }
            }
        ]
    }

    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_USE_RESPONSES", "0")
    monkeypatch.setattr(
        llm_client.urllib.request,
        "urlopen",
        lambda request, timeout=0: _FakeResponse(json.dumps(payload)),
    )

    result = llm_client.call_llm(
        "prompt",
        required_keys=[
            "status",
            "target_statement",
            "comparator_statement",
            "outcome_statement",
            "outcome_statements",
            "rationale",
        ],
    )
    assert result.status == "ok"
    assert result.parsed_content["target_statement"] == "Metformin initiators."
    assert result.parsed_content["outcome_statements"] == ["GI bleeding.", "MACE."]


@pytest.mark.acp
def test_call_llm_recovers_schema_wrapped_properties_output(monkeypatch):
    schema_wrapped_output = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "cohort_methods_intent_split_output",
        "type": "object",
        "properties": {
            "status": "ok",
            "plan": "Derived cohort statements.",
            "target_statement": "Patients treated with Ticagrelor.",
            "comparator_statement": "Patients treated with Clopidogrel.",
            "outcome_statement": "Cardiovascular events.",
            "outcome_statements": ["Myocardial infarction", "Stroke"],
            "rationale": "Comparative antiplatelet study intent.",
            "questions": [],
        },
        "required": [
            "status",
            "plan",
            "target_statement",
            "comparator_statement",
            "outcome_statement",
            "outcome_statements",
            "rationale",
        ],
        "additionalProperties": False,
    }
    payload = {"choices": [{"message": {"content": json.dumps(schema_wrapped_output)}}]}

    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_USE_RESPONSES", "0")
    monkeypatch.setattr(
        llm_client.urllib.request,
        "urlopen",
        lambda request, timeout=0: _FakeResponse(json.dumps(payload)),
    )

    result = llm_client.call_llm(
        "prompt",
        required_keys=[
            "status",
            "target_statement",
            "comparator_statement",
            "outcome_statement",
            "outcome_statements",
            "rationale",
        ],
    )
    assert result.status == "ok"
    assert result.schema_valid is True
    assert result.parsed_content["status"] == "ok"
    assert result.parsed_content["target_statement"] == "Patients treated with Ticagrelor."
    assert result.parsed_content["outcome_statements"] == ["Myocardial infarction", "Stroke"]


@pytest.mark.acp
def test_call_llm_does_not_recover_plain_schema_echo(monkeypatch):
    schema_echo = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "cohort_methods_intent_split_output",
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["ok", "needs_clarification"]},
            "target_statement": {"type": "string"},
            "comparator_statement": {"type": "string"},
            "outcome_statement": {"type": "string"},
            "outcome_statements": {"type": "array", "items": {"type": "string"}},
            "rationale": {"type": "string"},
        },
        "required": [
            "status",
            "target_statement",
            "comparator_statement",
            "outcome_statement",
            "outcome_statements",
            "rationale",
        ],
        "additionalProperties": False,
    }
    payload = {"choices": [{"message": {"content": json.dumps(schema_echo)}}]}

    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_USE_RESPONSES", "0")
    monkeypatch.setattr(
        llm_client.urllib.request,
        "urlopen",
        lambda request, timeout=0: _FakeResponse(json.dumps(payload)),
    )

    result = llm_client.call_llm(
        "prompt",
        required_keys=[
            "status",
            "target_statement",
            "comparator_statement",
            "outcome_statement",
            "outcome_statements",
            "rationale",
        ],
    )
    assert result.status == "schema_mismatch"
    assert result.schema_valid is False
