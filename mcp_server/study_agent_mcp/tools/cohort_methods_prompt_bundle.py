from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional

from ._common import with_meta


_CACHE: Optional[Dict[str, Any]] = None


def _prompt_dir() -> str:
    return os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "cohort_methods")
    )


def _analysis_template_path() -> str:
    return os.path.join(_prompt_dir(), "cmAnalysis_template.json")


def _field_descriptions_path() -> str:
    return os.path.join(_prompt_dir(), "CM_ANALYSIS_TEMPLATE.md")


def _instruction_template_path() -> str:
    return os.path.join(_prompt_dir(), "instruction_cohort_methods_specs.md")


def _output_style_template_path() -> str:
    return os.path.join(_prompt_dir(), "output_style_cohort_methods_specs.md")


def _load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _load_field_descriptions() -> str:
    text = _load_text(_field_descriptions_path())
    marker = "## Top-Level Shape"
    idx = text.find(marker)
    if idx == -1:
        raise ValueError(f"missing field description marker: {marker}")
    return text[idx:].strip()


def _build_bundle() -> Dict[str, Any]:
    defaults_spec = _load_json(_analysis_template_path())
    analysis_template = json.dumps(defaults_spec, indent=2)
    return {
        "instruction_template": _load_text(_instruction_template_path()),
        "output_style_template": _load_text(_output_style_template_path()),
        "annotated_template": analysis_template,
        "analysis_specifications_template": analysis_template,
        "json_field_descriptions": _load_field_descriptions(),
        "defaults_spec": defaults_spec,
        "schema_version": "v1.4.0",
    }


def register(mcp: object) -> None:
    global _CACHE

    @mcp.tool(name="cohort_methods_prompt_bundle")
    def cohort_methods_prompt_bundle_tool() -> Dict[str, Any]:
        global _CACHE
        if _CACHE is None:
            _CACHE = _build_bundle()
        return with_meta(_CACHE, "cohort_methods_prompt_bundle")

    return None
