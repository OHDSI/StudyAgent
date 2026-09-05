from __future__ import annotations

import json
import os
from typing import Any, Dict

from ._common import with_meta
from ._review_row import has_phi_keys, phi_detected, sanitize_keeper_row

_CACHE: Dict[str, Dict[str, Any]] = {}


def _prompt_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "keeper"))


def _load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _render_template(template: str, values: Dict[str, Any]) -> str:
    return template.format_map({key: str(value) for key, value in values.items()})


def _build_prompt(template: str, sanitized: Dict[str, Any]) -> str:
    return _render_template(template, sanitized)


def _parse_label(text: str) -> str:
    if not text:
        return "unknown"
    lower = text.lower()
    if "yes" in lower and "no" not in lower:
        return "yes"
    if "no" in lower and "yes" not in lower:
        return "no"
    if "unknown" in lower or "unclear" in lower or "uncertain" in lower:
        return "unknown"
    return "unknown"


def _load_bundle() -> Dict[str, Any]:
    cached = _CACHE.get("phenotype_validation_review")
    if cached is not None:
        return cached
    base = _prompt_dir()
    overview = _load_text(os.path.join(base, "overview_keeper.md"))
    spec = _load_text(os.path.join(base, "spec_phenotype_validation_review.md"))
    schema = _load_json(os.path.join(base, "output_schema_phenotype_validation_review.json"))
    system_prompt_template = _load_text(os.path.join(base, "system_prompt_phenotype_validation_review.md"))
    patient_summary_template = _load_text(os.path.join(base, "template_keeper_patient_summary.md"))
    payload = {
        "task": "phenotype_validation_review",
        "overview": overview,
        "spec": spec,
        "output_schema": schema,
        "system_prompt_template": system_prompt_template,
        "patient_summary_template": patient_summary_template,
    }
    _CACHE["phenotype_validation_review"] = payload
    return payload


def register(mcp: object) -> None:
    @mcp.tool(name="keeper_prompt_bundle")
    def keeper_prompt_bundle_tool(disease_name: str) -> Dict[str, Any]:
        payload = _load_bundle()
        payload = dict(payload)
        payload["disease_name"] = disease_name
        payload["system_prompt"] = _render_template(
            payload.get("system_prompt_template", ""),
            {"disease_name": disease_name},
        )
        return with_meta(payload, "keeper_prompt_bundle")

    @mcp.tool(name="keeper_sanitize_row")
    def keeper_sanitize_row_tool(row: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(row, dict):
            return with_meta({"error": "row must be a dict"}, "keeper_sanitize_row")
        redaction_report = {
            "phi_keys_present": has_phi_keys(row),
            "phi_patterns_present": phi_detected(json.dumps(row, ensure_ascii=True)),
        }
        sanitized = sanitize_keeper_row(row)
        sanitized_text = json.dumps(sanitized, ensure_ascii=True)
        if phi_detected(sanitized_text):
            return with_meta({"error": "phi_detected"}, "keeper_sanitize_row")
        return with_meta(
            {"sanitized_row": sanitized, "redaction_report": redaction_report},
            "keeper_sanitize_row",
        )

    @mcp.tool(name="keeper_build_prompt")
    def keeper_build_prompt_tool(disease_name: str, sanitized_row: Dict[str, Any]) -> Dict[str, Any]:
        bundle = _load_bundle()
        prompt = _build_prompt(bundle.get("patient_summary_template", ""), sanitized_row)
        return with_meta({"prompt": prompt}, "keeper_build_prompt")

    @mcp.tool(name="keeper_parse_response")
    def keeper_parse_response_tool(llm_output: Any) -> Dict[str, Any]:
        label = "unknown"
        rationale = ""
        if isinstance(llm_output, dict):
            label = llm_output.get("label") or "unknown"
            if label not in ("yes", "no", "unknown"):
                label = "unknown"
            rationale = str(llm_output.get("rationale") or "").strip()
        else:
            label = _parse_label(str(llm_output))
        if not rationale:
            return with_meta(
                {"error": "missing_rationale", "label": label},
                "keeper_parse_response",
            )
        return with_meta({"label": label, "rationale": rationale}, "keeper_parse_response")

    return None
