from __future__ import annotations

from typing import Any, Dict


def with_meta(payload: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
    if "_meta" not in payload:
        payload["_meta"] = {"tool": tool_name}
    return payload
