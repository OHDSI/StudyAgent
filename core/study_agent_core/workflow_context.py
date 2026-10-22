"""Bounded, client-neutral context handling for workflow-context dialogue."""
from __future__ import annotations

import json
from typing import Any, Dict

CONTEXT_CONTRACT_VERSION = "1"
MAX_CONTEXT_BYTES = 12_000
MAX_CONTEXT_DEPTH = 4
MAX_CONTEXT_KEYS = 32
MAX_CONTEXT_ITEMS = 20
MAX_CONTEXT_STRING_CHARS = 800


class WorkflowContextContractError(ValueError):
    """Raised when a client context cannot be safely bounded for prompting."""


def _compact(value: Any, depth: int = 0) -> Any:
    if depth >= MAX_CONTEXT_DEPTH:
        return "[omitted: maximum context depth reached]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if len(value) <= MAX_CONTEXT_STRING_CHARS:
            return value
        return value[:MAX_CONTEXT_STRING_CHARS] + f"... [truncated {len(value) - MAX_CONTEXT_STRING_CHARS} chars]"
    if isinstance(value, (list, tuple)):
        result = [_compact(item, depth + 1) for item in value[:MAX_CONTEXT_ITEMS]]
        if len(value) > MAX_CONTEXT_ITEMS:
            result.append(f"[omitted {len(value) - MAX_CONTEXT_ITEMS} additional items]")
        return result
    if isinstance(value, dict):
        result: Dict[str, Any] = {}
        items = list(value.items())
        for key, item in items[:MAX_CONTEXT_KEYS]:
            if not isinstance(key, str):
                continue
            result[key[:120]] = _compact(item, depth + 1)
        if len(items) > MAX_CONTEXT_KEYS:
            result["_omitted_keys"] = len(items) - MAX_CONTEXT_KEYS
        return result
    return str(value)[:MAX_CONTEXT_STRING_CHARS]


def normalize_workflow_context(current_context: Dict[str, Any] | None) -> Dict[str, Any]:
    """Return a bounded JSON-safe context while preserving legacy client keys.

    Clients may use the documented envelope categories or legacy fields during
    migration. This function does not attempt PHI detection: clients must never
    submit patient-level data. It enforces deterministic shape and size bounds
    before an LLM prompt is assembled.
    """
    if current_context is None:
        return {}
    if not isinstance(current_context, dict):
        raise WorkflowContextContractError("current_context must be an object")
    normalized = _compact(current_context)
    try:
        encoded = json.dumps(normalized, ensure_ascii=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise WorkflowContextContractError("current_context must be JSON serializable") from exc
    if len(encoded.encode("utf-8")) > MAX_CONTEXT_BYTES:
        raise WorkflowContextContractError(
            f"current_context exceeds the {MAX_CONTEXT_BYTES}-byte dialogue contract limit"
        )
    return normalized
