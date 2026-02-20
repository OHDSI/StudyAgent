from __future__ import annotations

import json
import os
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
        cohortId: int,
        truncate: bool = True,
    ) -> Dict[str, Any]:
        index = get_default_index()
        definitions_dir = os.path.join(index.index_dir, "definitions")
        path = os.path.join(definitions_dir, f"{int(cohortId)}.json")
        if not os.path.exists(path):
            payload = {"error": f"definition not found for cohortId {cohortId}"}
            return with_meta(payload, "phenotype_fetch_definition")

        with open(path, "r", encoding="utf-8") as handle:
            try:
                data = json.load(handle)
            except json.JSONDecodeError:
                payload = {"error": f"definition JSON invalid for cohortId {cohortId}"}
                return with_meta(payload, "phenotype_fetch_definition")

        if truncate:
            data = _truncate(data)
        payload = {"definition": data}
        return with_meta(payload, "phenotype_fetch_definition")

    return None
