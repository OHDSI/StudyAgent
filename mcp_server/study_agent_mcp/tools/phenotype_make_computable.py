from __future__ import annotations

import json
import os
from typing import Any, Dict

from ._common import with_meta

_CACHE: Dict[str, Dict[str, Any]] = {}


def _prompt_dir() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "phenotype_make_computable")
    )


def _load_text(path: str) -> str:
    with open(path, encoding="utf-8") as handle:
        return handle.read().strip()


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _load_bundle() -> Dict[str, Any]:
    cached = _CACHE.get("bundle")
    if cached is not None:
        return cached
    base = _prompt_dir()
    payload = {
        "task": "phenotype_make_computable",
        "overview": _load_text(os.path.join(base, "overview_phenotype_make_computable.md")),
        "spec": _load_text(os.path.join(base, "spec_phenotype_make_computable.md")),
        "output_schema": _load_json(os.path.join(base, "output_schema_phenotype_make_computable.json")),
        "capr_reference": _load_text(os.path.join(base, "CAPR_REFERENCE.md")),
    }
    _CACHE["bundle"] = payload
    return payload


def register(mcp: object) -> None:
    @mcp.tool(name="phenotype_make_computable_prompt_bundle")
    def phenotype_make_computable_prompt_bundle_tool() -> Dict[str, Any]:
        return with_meta(_load_bundle(), "phenotype_make_computable_prompt_bundle")
