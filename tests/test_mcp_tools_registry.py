import pytest

from study_agent_mcp.tools import register_all


class DummyMCP:
    def __init__(self) -> None:
        self.registered = []

    def tool(self, name: str):
        def decorator(fn):
            self.registered.append(name)
            return fn

        return decorator


@pytest.mark.mcp
def test_register_all_tools() -> None:
    mcp = DummyMCP()
    register_all(mcp)
    assert set(mcp.registered) == {
        "propose_concept_set_diff",
        "cohort_lint",
        "phenotype_recommendations",
        "phenotype_improvements",
        "phenotype_search",
        "phenotype_fetch_summary",
        "phenotype_fetch_definition",
        "phenotype_list_similar",
        "phenotype_reindex",
    }
