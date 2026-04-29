from __future__ import annotations

from typing import Any, Dict

from study_agent_mcp.retrieval import get_default_index

from ._common import with_meta


def register(mcp: object) -> None:
    @mcp.tool(name="phenotype_list_similar")
    def phenotype_list_similar_tool(
        phenotype_id: str,
        top_k: int = 10,
    ) -> Dict[str, Any]:
        index = get_default_index()
        results = index.list_similar(str(phenotype_id), top_k=top_k)
        payload = {
            "phenotype_id": str(phenotype_id),
            "results": results,
            "count": len(results),
        }
        return with_meta(payload, "phenotype_list_similar")

    return None
