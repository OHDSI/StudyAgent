import pytest

from study_agent_mcp.tools import phenotype_search


class StubIndex:
    def __init__(self) -> None:
        self.args = None

    def search(self, **kwargs):
        self.args = kwargs
        return []


class DummyMCP:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self, name: str):
        def decorator(fn):
            self.tools[name] = fn
            return fn

        return decorator


@pytest.mark.mcp
def test_phenotype_search_uses_env_weights(monkeypatch) -> None:
    stub = StubIndex()
    monkeypatch.setattr(phenotype_search, "get_default_index", lambda: stub)
    monkeypatch.setenv("PHENOTYPE_DENSE_WEIGHT", "0.9")
    monkeypatch.setenv("PHENOTYPE_SPARSE_WEIGHT", "0.1")

    mcp = DummyMCP()
    phenotype_search.register(mcp)
    fn = mcp.tools["phenotype_search"]

    payload = fn(
        query="test",
        top_k=5,
        dense_k=10,
        sparse_k=10,
    )
    assert payload["weights"]["dense"] == 0.9
    assert payload["weights"]["sparse"] == 0.1
    assert stub.args["dense_weight"] == 0.9
    assert stub.args["sparse_weight"] == 0.1


@pytest.mark.mcp
def test_phenotype_search_explains_blank_faiss_assertion(monkeypatch) -> None:
    class MismatchedIndex:
        def search(self, **kwargs):
            raise AssertionError

    monkeypatch.setattr(phenotype_search, "get_default_index", lambda: MismatchedIndex())
    monkeypatch.setenv("EMBED_MODEL", "new-embedding-model")

    mcp = DummyMCP()
    phenotype_search.register(mcp)
    payload = mcp.tools["phenotype_search"](query="test")

    assert payload["error"] == "phenotype_search_failed"
    assert "dense phenotype index was built with a different embedding model" in payload["details"]
    assert "new-embedding-model" in payload["details"]
    assert "rebuild the dense index" in payload["details"]
