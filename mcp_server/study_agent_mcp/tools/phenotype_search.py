from __future__ import annotations

import os
from typing import Any, Dict, Optional

from study_agent_mcp.retrieval import get_default_index

from ._common import with_meta


def register(mcp: object) -> None:
    @mcp.tool(name="phenotype_search")
    def phenotype_search_tool(
        query: str,
        top_k: int = 20,
        dense_k: int = 100,
        sparse_k: int = 100,
        dense_weight: Optional[float] = None,
        sparse_weight: Optional[float] = None,
    ) -> Dict[str, Any]:
        default_dense_weight = float(os.getenv("PHENOTYPE_DENSE_WEIGHT", "0.9"))
        default_sparse_weight = float(os.getenv("PHENOTYPE_SPARSE_WEIGHT", "0.1"))
        if dense_weight is None:
            dense_weight = default_dense_weight
        if sparse_weight is None:
            sparse_weight = default_sparse_weight
        index = get_default_index()
        results = index.search(
            query=query,
            top_k=top_k,
            dense_k=dense_k,
            sparse_k=sparse_k,
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
        )
        payload = {
            "query": query,
            "results": results,
            "count": len(results),
            "weights": {
                "dense": dense_weight,
                "sparse": sparse_weight,
            },
        }
        return with_meta(payload, "phenotype_search")

    return None
