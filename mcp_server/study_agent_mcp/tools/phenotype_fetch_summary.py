from __future__ import annotations

from typing import Any, Dict

from study_agent_mcp.retrieval import get_default_index

from ._common import with_meta


def register(mcp: object) -> None:
    @mcp.tool(name="phenotype_fetch_summary")
    def phenotype_fetch_summary_tool(cohortId: int) -> Dict[str, Any]:
        index = get_default_index()
        summary = index.fetch_summary(int(cohortId))
        if summary is None:
            payload = {"error": f"cohortId {cohortId} not found"}
        else:
            payload = {"summary": summary}
        return with_meta(payload, "phenotype_fetch_summary")

    return None
