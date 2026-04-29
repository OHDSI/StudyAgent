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
