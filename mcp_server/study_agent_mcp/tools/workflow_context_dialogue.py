from __future__ import annotations

import json
import os
from typing import Any, Dict

from ._common import with_meta


_CACHE: Dict[str, Dict[str, Any]] = {}


def _prompt_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "workflow_dialogue"))


def _load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_bundle() -> Dict[str, Any]:
    cached = _CACHE.get("workflow_context_dialogue")
    if cached is not None:
        return cached
    base = _prompt_dir()
    payload = {
        "task": "workflow_context_dialogue",
        "overview": _load_text(os.path.join(base, "overview_workflow_context_dialogue.md")),
        "spec": _load_text(os.path.join(base, "spec_workflow_context_dialogue.md")),
        "output_schema": _load_json(os.path.join(base, "output_schema_workflow_context_dialogue.json")),
    }
    _CACHE["workflow_context_dialogue"] = payload
    return payload


def register(mcp: object) -> None:
    @mcp.tool(name="workflow_context_dialogue")
    def workflow_context_dialogue_tool() -> Dict[str, Any]:
        return with_meta(_load_bundle(), "workflow_context_dialogue")

    return None
