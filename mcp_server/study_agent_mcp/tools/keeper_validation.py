from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

from ._common import with_meta

_CACHE: Dict[str, Dict[str, Any]] = {}

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_URL_RE = re.compile(r"https?://\S+")
_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_PHONE_RE = re.compile(r"\b\+?\d{1,2}[\s.-]?\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")
_DATE_RE = re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|\b\d{4}-\d{1,2}-\d{1,2}\b")
_ZIP_RE = re.compile(r"\b\d{5}(?:-\d{4})?\b")
_DAY_RE = re.compile(r"\(day[^)]*\)", re.IGNORECASE)

_PHI_KEYS = {
    "name",
    "full_name",
    "first_name",
    "last_name",
    "middle_name",
    "address",
    "street",
    "city",
    "county",
    "zip",
    "zipcode",
    "email",
    "phone",
    "fax",
    "ssn",
    "social_security",
    "medical_record_number",
    "mrn",
    "account_number",
    "health_plan_beneficiary_number",
    "certificate_number",
    "license_number",
    "vehicle_id",
    "device_id",
    "url",
    "ip_address",
    "biometric_id",
    "photo",
    "personid",
    "person_id",
    "visit_id",
    "visitid",
    "birth_date",
    "admission_date",
    "discharge_date",
    "death_date",
}


def _prompt_dir() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "prompts", "keeper"))


def _load_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _bucket_age(age: Any) -> str:
    try:
        age_val = float(age)
    except (TypeError, ValueError):
        return "unknown"
    if age_val >= 85:
        return "85+"
    bucket = int(age_val // 5) * 5
    return f"{bucket}-{bucket+4}"


def _sanitize_text(text: str) -> str:
    if not text:
        return "None"
    text = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    text = _URL_RE.sub("[REDACTED_URL]", text)
    text = _IP_RE.sub("[REDACTED_IP]", text)
    text = _PHONE_RE.sub("[REDACTED_PHONE]", text)
    text = _DATE_RE.sub("[REDACTED_DATE]", text)
    text = _ZIP_RE.sub("[REDACTED_ZIP]", text)
    text = _DAY_RE.sub("(prior)", text)
    return text


def _phi_detected(text: str) -> bool:
    if not text:
        return False
    return bool(
        _EMAIL_RE.search(text)
        or _URL_RE.search(text)
        or _IP_RE.search(text)
        or _PHONE_RE.search(text)
        or _DATE_RE.search(text)
    )


def _has_phi_keys(row: Dict[str, Any]) -> bool:
    for key, value in row.items():
        if key is None:
            continue
        key_norm = str(key).lower()
        if key_norm in _PHI_KEYS and value not in (None, "", [], {}):
            return True
    return False


def _sanitize_row(row: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = {}
    sanitized["age_bucket"] = _bucket_age(row.get("age"))
    sanitized["gender"] = _sanitize_text(str(row.get("gender") or "unknown"))
    sanitized["visit_context"] = _sanitize_text(str(row.get("visitContext") or "unknown"))
    sanitized["presentation"] = _sanitize_text(str(row.get("presentation") or "None"))
    sanitized["prior_disease"] = _sanitize_text(str(row.get("priorDisease") or "None"))
    sanitized["symptoms"] = _sanitize_text(str(row.get("symptoms") or "None"))
    sanitized["comorbidities"] = _sanitize_text(str(row.get("comorbidities") or "None"))
    sanitized["prior_drugs"] = _sanitize_text(str(row.get("priorDrugs") or "None"))
    sanitized["prior_treatments"] = _sanitize_text(str(row.get("priorTreatmentProcedures") or "None"))
    sanitized["diagnostic_procedures"] = _sanitize_text(str(row.get("diagnosticProcedures") or "None"))
    sanitized["measurements"] = _sanitize_text(str(row.get("measurements") or "None"))
    sanitized["alternative_diagnosis"] = _sanitize_text(str(row.get("alternativeDiagnosis") or "None"))
    sanitized["after_disease"] = _sanitize_text(str(row.get("afterDisease") or "None"))
    sanitized["after_drugs"] = _sanitize_text(str(row.get("afterDrugs") or "None"))
    sanitized["after_treatments"] = _sanitize_text(str(row.get("afterTreatmentProcedures") or "None"))
    sanitized["death"] = _sanitize_text(str(row.get("death") or "None"))
    return sanitized


def _build_prompt(disease_name: str, sanitized: Dict[str, Any]) -> str:
    lines = [
        f"Demographics and details about the visit: {sanitized['gender']}, {sanitized['age_bucket']} yo; Visit: {sanitized['visit_context']}",
        f"Diagnoses recorded on the day of the visit: {sanitized['presentation']}",
        f"Diagnoses recorded prior to the visit: {sanitized['prior_disease']}; Symptoms: {sanitized['symptoms']}; Comorbidities: {sanitized['comorbidities']}",
        f"Treatments recorded prior to the visit: {sanitized['prior_drugs']}; {sanitized['prior_treatments']}",
        f"Diagnostic procedures recorded proximal to the visit: {sanitized['diagnostic_procedures']}",
        f"Laboratory tests recorded proximal to the visit: {sanitized['measurements']}",
        f"Alternative diagnoses recorded proximal to the visit: {sanitized['alternative_diagnosis']}",
        f"Diagnoses recorded after the visit: {sanitized['after_disease']}",
        f"Treatments recorded during or after the visit: {sanitized['after_drugs']}; {sanitized['after_treatments']}",
    ]
    return "\n\n".join(lines)


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
    payload = {
        "task": "phenotype_validation_review",
        "overview": overview,
        "spec": spec,
        "output_schema": schema,
    }
    _CACHE["phenotype_validation_review"] = payload
    return payload


def register(mcp: object) -> None:
    @mcp.tool(name="keeper_prompt_bundle")
    def keeper_prompt_bundle_tool(disease_name: str) -> Dict[str, Any]:
        payload = _load_bundle()
        payload = dict(payload)
        payload["disease_name"] = disease_name
        payload["system_prompt"] = (
            "Act as a medical doctor reviewing a patient's healthcare data captured during routine clinical care. "
            f"Write a brief clinical narrative and then determine whether the patient had {disease_name}. "
            "Remember that a diagnosis can be recorded as part of testing, and may not confirm disease. "
            "If evidence is insufficient, respond with label \"unknown\". "
            "Return JSON with label and rationale only."
        )
        return with_meta(payload, "keeper_prompt_bundle")

    @mcp.tool(name="keeper_sanitize_row")
    def keeper_sanitize_row_tool(row: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(row, dict):
            return with_meta({"error": "row must be a dict"}, "keeper_sanitize_row")
        redaction_report = {
            "phi_keys_present": _has_phi_keys(row),
            "phi_patterns_present": _phi_detected(json.dumps(row, ensure_ascii=True)),
        }
        sanitized = _sanitize_row(row)
        sanitized_text = json.dumps(sanitized, ensure_ascii=True)
        if _phi_detected(sanitized_text):
            return with_meta({"error": "phi_detected"}, "keeper_sanitize_row")
        return with_meta(
            {"sanitized_row": sanitized, "redaction_report": redaction_report},
            "keeper_sanitize_row",
        )

    @mcp.tool(name="keeper_build_prompt")
    def keeper_build_prompt_tool(disease_name: str, sanitized_row: Dict[str, Any]) -> Dict[str, Any]:
        prompt = _build_prompt(disease_name, sanitized_row)
        return with_meta({"prompt": prompt}, "keeper_build_prompt")

    @mcp.tool(name="keeper_parse_response")
    def keeper_parse_response_tool(llm_output: Any) -> Dict[str, Any]:
        label = "unknown"
        rationale = ""
        if isinstance(llm_output, dict):
            label = llm_output.get("label") or "unknown"
            if label not in ("yes", "no", "unknown"):
                label = "unknown"
            rationale = llm_output.get("rationale") or ""
        else:
            label = _parse_label(str(llm_output))
        return with_meta({"label": label, "rationale": rationale}, "keeper_parse_response")

    return None
