import pytest

from study_agent_mcp.retrieval import PhenotypeIndex


@pytest.mark.mcp
def test_search_normalizes_dense_and_sparse_scores_before_weighting(monkeypatch):
    index = PhenotypeIndex(index_dir="/tmp", allow_dense=False, allow_sparse=False)
    index._catalog = [
        {"phenotype_id": "a", "name": "A", "short_description": "A", "tags": [], "signals": [], "executable_definition_status": "native_ohdsi", "execution_readiness_score": 1.0},
        {"phenotype_id": "b", "name": "B", "short_description": "B", "tags": [], "signals": [], "executable_definition_status": "native_ohdsi", "execution_readiness_score": 1.0},
        {"phenotype_id": "c", "name": "C", "short_description": "C", "tags": [], "signals": [], "executable_definition_status": "native_ohdsi", "execution_readiness_score": 1.0},
    ]
    index._dense = object()
    index.embedding_client = object()
    index._sparse = {"enabled": True}

    monkeypatch.setattr(index, "_dense_search", lambda query, top_k: {0: 0.9, 1: 0.6})
    monkeypatch.setattr(index, "_sparse_search", lambda query, top_k: {1: 25.0, 2: 10.0})

    results = index.search(
        query="test",
        top_k=3,
        dense_weight=0.8,
        sparse_weight=0.2,
    )

    assert [row["phenotype_id"] for row in results] == ["a", "b", "c"]

    by_id = {row["phenotype_id"]: row for row in results}
    assert by_id["a"]["score_dense"] == pytest.approx(1.0)
    assert by_id["a"]["score_sparse"] is None
    assert by_id["a"]["score"] == pytest.approx(0.8)

    assert by_id["b"]["score_dense"] == pytest.approx(0.0)
    assert by_id["b"]["score_sparse"] == pytest.approx(1.0)
    assert by_id["b"]["score"] == pytest.approx(0.2)

    assert by_id["c"]["score_dense"] is None
    assert by_id["c"]["score_sparse"] == pytest.approx(0.0)
    assert by_id["c"]["score"] == pytest.approx(0.0)

    assert by_id["a"]["score_dense_raw"] == pytest.approx(0.9)
    assert by_id["b"]["score_sparse_raw"] == pytest.approx(25.0)


@pytest.mark.mcp
def test_normalize_score_map_returns_one_for_flat_scores():
    from study_agent_mcp.retrieval.index import _normalize_score_map

    normalized = _normalize_score_map({1: 4.0, 2: 4.0})
    assert normalized == {1: 1.0, 2: 1.0}
