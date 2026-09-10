from __future__ import annotations

from typing import Any, Dict

from study_agent_mcp.retrieval import get_default_index

from ._common import with_meta


def register(mcp: object) -> None:
    @mcp.tool(name="phenotype_fetch_source_snapshot")
    def phenotype_fetch_source_snapshot_tool(phenotype_id: str) -> Dict[str, Any]:
        index = get_default_index()
        snapshot = index.fetch_source_snapshot(str(phenotype_id))
        if snapshot is None:
            payload = {"error": f"source snapshot not found for phenotype_id {phenotype_id}"}
        else:
            payload = {"snapshot": snapshot}
        return with_meta(payload, "phenotype_fetch_source_snapshot")

    return None
