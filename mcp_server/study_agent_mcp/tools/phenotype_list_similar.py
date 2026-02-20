from __future__ import annotations

from typing import Any, Dict

from study_agent_mcp.retrieval import get_default_index

from ._common import with_meta


def register(mcp: object) -> None:
    @mcp.tool(name="phenotype_list_similar")
    def phenotype_list_similar_tool(
        cohortId: int,
        top_k: int = 10,
    ) -> Dict[str, Any]:
        index = get_default_index()
        results = index.list_similar(int(cohortId), top_k=top_k)
        payload = {
            "cohortId": int(cohortId),
            "results": results,
            "count": len(results),
        }
        return with_meta(payload, "phenotype_list_similar")

    return None
