from __future__ import annotations

import os
import time
from typing import Any, Dict, Optional

from study_agent_mcp.retrieval import get_default_index, index_status

from ._common import with_meta
from ._log import log_debug


def _search_error_details(exc: Exception) -> str:
    details = str(exc).strip()
    if details:
        return details
    if isinstance(exc, AssertionError):
        embed_model = os.getenv("EMBED_MODEL", "(not configured)")
        return (
            "FAISS rejected the query embedding (AssertionError with no message). "
            "This commonly means the dense phenotype index was built with a different "
            f"embedding model or vector dimension than the current EMBED_MODEL={embed_model!r}. "
            "Restore the model used to build the index, or rebuild the dense index. "
            "See docs/PHENOTYPE_INDEXING.md."
        )
    return f"{type(exc).__name__} with no error message"


def register(mcp: object) -> None:
    @mcp.tool(name="phenotype_search")
    def phenotype_search_tool(
        query: str,
        top_k: int = 20,
        offset: int = 0,
        dense_k: int = 100,
        sparse_k: int = 100,
        dense_weight: Optional[float] = None,
        sparse_weight: Optional[float] = None,
    ) -> Dict[str, Any]:
        default_dense_weight = float(os.getenv("PHENOTYPE_DENSE_WEIGHT", "0.7"))
        default_sparse_weight = float(os.getenv("PHENOTYPE_SPARSE_WEIGHT", "0.3"))
        if dense_weight is None:
            dense_weight = default_dense_weight
        if sparse_weight is None:
            sparse_weight = default_sparse_weight
        log_debug(
            "phenotype_search start",
            query_len=len(query or ""),
            top_k=top_k,
            dense_k=dense_k,
            sparse_k=sparse_k,
            dense_weight=dense_weight,
            sparse_weight=sparse_weight,
        )
        try:
            t0 = time.time()
            index = get_default_index()
            log_debug(
                "phenotype_search index_loaded",
                seconds=round(time.time() - t0, 3),
                dense_loaded=getattr(index, "_dense", None) is not None,
                sparse_loaded=getattr(index, "_sparse", None) is not None,
                catalog_count=len(getattr(index, "catalog", []) or []),
            )
        except Exception as exc:
            return with_meta(
                {
                    "error": "phenotype_index_unavailable",
                    "details": str(exc),
                    "index_status": index_status(),
                },
                "phenotype_search",
            )
        try:
            t1 = time.time()
            results = index.search(
                query=query,
                top_k=top_k,
                offset=offset,
                dense_k=dense_k,
                sparse_k=sparse_k,
                dense_weight=dense_weight,
                sparse_weight=sparse_weight,
            )
            log_debug(
                "phenotype_search done",
                seconds=round(time.time() - t1, 3),
                result_count=len(results),
            )
        except Exception as exc:
            return with_meta(
                {
                    "error": "phenotype_search_failed",
                    "details": _search_error_details(exc),
                },
                "phenotype_search",
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
