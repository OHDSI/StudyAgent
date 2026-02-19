from __future__ import annotations

import json
import os
from typing import Any, Dict

from ._common import with_meta


_CACHE: Dict[str, Dict[str, Any]] = {}


def _prompt_dir() -> str:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "phenotype"))
    return base


def _load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_bundle(task: str) -> Dict[str, Any]:
    cached = _CACHE.get(task)
    if cached is not None:
        return cached
    if task != "phenotype_recommendations":
        return {"error": f"unsupported task {task}"}
    base = _prompt_dir()
    overview = _load_text(os.path.join(base, "overview_phenotype.md"))
    spec = _load_text(os.path.join(base, "spec_phenotype_recommendations.md"))
    schema = _load_json(os.path.join(base, "output_schema_phenotype_recommendations.json"))
    payload = {
        "task": task,
        "overview": overview,
        "spec": spec,
        "output_schema": schema,
    }
    _CACHE[task] = payload
    return payload


def register(mcp: object) -> None:
    @mcp.tool(name="phenotype_prompt_bundle")
    def phenotype_prompt_bundle_tool(task: str) -> Dict[str, Any]:
        payload = _load_bundle(task)
        return with_meta(payload, "phenotype_prompt_bundle")

    return None
