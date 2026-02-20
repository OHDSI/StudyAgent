import pytest

from study_agent_mcp.tools import phenotype_prompt_bundle


class DummyMCP:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self, name: str):
        def decorator(fn):
            self.tools[name] = fn
            return fn

        return decorator


@pytest.mark.mcp
def test_prompt_bundle_tool_returns_schema() -> None:
    mcp = DummyMCP()
    phenotype_prompt_bundle.register(mcp)
    fn = mcp.tools["phenotype_prompt_bundle"]
    payload = fn("phenotype_recommendations")
    assert "overview" in payload
    assert "spec" in payload
    assert "output_schema" in payload
    assert payload["output_schema"]["title"] == "phenotype_recommendations_output"


@pytest.mark.mcp
def test_prompt_bundle_improvements_schema() -> None:
    mcp = DummyMCP()
    phenotype_prompt_bundle.register(mcp)
    fn = mcp.tools["phenotype_prompt_bundle"]
    payload = fn("phenotype_improvements")
    assert "overview" in payload
    assert "spec" in payload
    assert "output_schema" in payload
    assert payload["output_schema"]["title"] == "phenotype_improvements_output"
