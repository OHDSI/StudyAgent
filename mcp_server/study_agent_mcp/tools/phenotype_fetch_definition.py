from __future__ import annotations

from typing import Any, Dict

from study_agent_mcp.retrieval import get_default_index

from ._common import with_meta


def _truncate(obj: Any, depth: int = 0, max_depth: int = 4, max_list: int = 20, max_keys: int = 50) -> Any:
    if depth >= max_depth:
        return "..."
    if isinstance(obj, list):
        trimmed = obj[:max_list]
        return [_truncate(item, depth + 1, max_depth, max_list, max_keys) for item in trimmed]
    if isinstance(obj, dict):
        items = list(obj.items())[:max_keys]
        return {key: _truncate(value, depth + 1, max_depth, max_list, max_keys) for key, value in items}
    return obj


def register(mcp: object) -> None:
    @mcp.tool(name="phenotype_fetch_definition")
    def phenotype_fetch_definition_tool(
        phenotype_id: str,
        truncate: bool = True,
    ) -> Dict[str, Any]:
        index = get_default_index()
        data = index.fetch_definition(str(phenotype_id))
        if data is None:
            payload = {"error": f"definition not found for phenotype_id {phenotype_id}"}
            return with_meta(payload, "phenotype_fetch_definition")

        if truncate:
            data = _truncate(data)
        payload = {"definition": data}
        return with_meta(payload, "phenotype_fetch_definition")

    return None
