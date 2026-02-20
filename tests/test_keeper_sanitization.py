import pytest

from study_agent_mcp.tools import keeper_validation


class DummyMCP:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self, name: str):
        def decorator(fn):
            self.tools[name] = fn
            return fn

        return decorator


@pytest.mark.mcp
def test_keeper_sanitize_reports_phi_key():
    mcp = DummyMCP()
    keeper_validation.register(mcp)
    fn = mcp.tools["keeper_sanitize_row"]
    payload = fn({"personId": 1, "age": 40, "gender": "Male"})
    assert "sanitized_row" in payload
    assert payload["redaction_report"]["phi_keys_present"] is True


@pytest.mark.mcp
def test_keeper_sanitize_removes_dates():
    mcp = DummyMCP()
    keeper_validation.register(mcp)
    fn = mcp.tools["keeper_sanitize_row"]
    payload = fn({"age": 44, "gender": "Male", "presentation": "Dx on 2020-01-01"})
    assert "sanitized_row" in payload
