from __future__ import annotations

import json
import re
from typing import Any, Dict, Iterable, List

from ._service_registry import get_controlled_identifier_keys

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

_DEFAULT_CONTROLLED_IDENTIFIER_KEYS = {
    "ingred_rxcui",
    "rxcui",
    "adverse_event_meddra_id",
    "meddra_code",
    "meddra_id",
    "concept_id",
    "ingredient_concept_id",
    "adverse_event_concept_id",
    "outcome_concept_id",
}


def _configured_controlled_identifier_keys() -> frozenset[str]:
    return get_controlled_identifier_keys("case_causal_review", _DEFAULT_CONTROLLED_IDENTIFIER_KEYS)

_ALLOWED_SUBROLES = {
    "primary_suspect",
    "secondary_suspect",
    "concomitant_exposure",
    "alternative_explanation",
    "vulnerability_factor",
    "contextual_factor",
    "proximate_marker",
    "candidate_exposure",
    "background_exposure",
    "candidate_condition",
    "index_event",
}

_ALLOWED_EXPANSION_TOOLS = {
    "get_case_review_concept_set_domain",
    "get_case_review_drug_signal_details",
    "get_case_review_drug_label_details",
    "get_case_review_report_literature_stub",
}


def bucket_age(age: Any) -> str:
    try:
        age_val = float(age)
    except (TypeError, ValueError):
        return "unknown"
    if age_val >= 85:
        return "85+"
    bucket = int(age_val // 5) * 5
    return f"{bucket}-{bucket+4}"


def sanitize_text(text: str, key_name: str | None = None) -> str:
    if not text:
        return "None"
    value = str(text).strip()
    if not value:
        return "None"
    value = _DAY_RE.sub("(prior)", value)
    key_norm = str(key_name or "").strip().lower()
    if key_norm in _configured_controlled_identifier_keys():
        return value
    value = _EMAIL_RE.sub("[REDACTED_EMAIL]", value)
    value = _URL_RE.sub("[REDACTED_URL]", value)
    value = _IP_RE.sub("[REDACTED_IP]", value)
    value = _PHONE_RE.sub("[REDACTED_PHONE]", value)
    value = _DATE_RE.sub("[REDACTED_DATE]", value)
    value = _ZIP_RE.sub("[REDACTED_ZIP]", value)
    return value


def clean_optional_text(value: Any, key_name: str | None = None) -> str:
    text = sanitize_text(str(value or ""), key_name=key_name)
    return "" if text == "None" else text


def phi_detected(text: str) -> bool:
    if not text:
        return False
    value = str(text)
    return bool(
        _EMAIL_RE.search(value)
        or _URL_RE.search(value)
        or _IP_RE.search(value)
        or _PHONE_RE.search(value)
        or _DATE_RE.search(value)
    )


def has_phi_keys(row: Dict[str, Any]) -> bool:
    for key, value in row.items():
        if key is None:
            continue
        key_norm = str(key).lower()
        if key_norm in _PHI_KEYS and value not in (None, "", [], {}):
            return True
    return False


def sanitize_keeper_row(row: Dict[str, Any]) -> Dict[str, Any]:
    sanitized = {}
    sanitized["age_bucket"] = bucket_age(row.get("age"))
    sanitized["gender"] = sanitize_text(str(row.get("gender") or row.get("sex") or "unknown"))
    sanitized["visit_context"] = sanitize_text(str(row.get("visitContext") or row.get("visits") or "unknown"))
    sanitized["presentation"] = sanitize_text(str(row.get("presentation") or "None"))
    sanitized["prior_disease"] = sanitize_text(str(row.get("priorDisease") or "None"))
    sanitized["symptoms"] = sanitize_text(str(row.get("symptoms") or "None"))
    sanitized["comorbidities"] = sanitize_text(str(row.get("comorbidities") or "None"))
    sanitized["prior_drugs"] = sanitize_text(str(row.get("priorDrugs") or "None"))
    sanitized["prior_treatments"] = sanitize_text(str(row.get("priorTreatmentProcedures") or "None"))
    sanitized["diagnostic_procedures"] = sanitize_text(str(row.get("diagnosticProcedures") or "None"))
    sanitized["measurements"] = sanitize_text(str(row.get("measurements") or "None"))
    sanitized["alternative_diagnosis"] = sanitize_text(
        str(row.get("alternativeDiagnosis") or row.get("alternativeDiagnoses") or "None")
    )
    sanitized["after_disease"] = sanitize_text(str(row.get("afterDisease") or row.get("postDisease") or "None"))
    sanitized["after_drugs"] = sanitize_text(str(row.get("afterDrugs") or row.get("postDrugs") or "None"))
    sanitized["after_treatments"] = sanitize_text(
        str(row.get("afterTreatmentProcedures") or row.get("postTreatmentProcedures") or "None")
    )
    sanitized["death"] = sanitize_text(str(row.get("death") or "None"))
    return sanitized


def normalize_domain(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")


def normalize_subrole(value: Any, default: str) -> str:
    raw = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    if raw in _ALLOWED_SUBROLES:
        return raw
    return default


def sanitize_scalar(value: Any, key_name: str | None = None) -> Any:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    return sanitize_text(str(value), key_name=key_name)


def sanitize_nested(value: Any, depth: int = 0, key_name: str | None = None) -> Any:
    if depth > 4:
        return sanitize_text(json.dumps(value, ensure_ascii=True, sort_keys=True), key_name=key_name)
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for key, inner in value.items():
            raw_key = str(key)
            sanitized[sanitize_text(raw_key)] = sanitize_nested(inner, depth + 1, key_name=raw_key)
        return sanitized
    if isinstance(value, list):
        return [sanitize_nested(item, depth + 1, key_name=key_name) for item in value[:50]]
    return sanitize_scalar(value, key_name=key_name)


def collect_phi_issues(value: Any, path: str = "case_row") -> List[str]:
    issues: List[str] = []
    if isinstance(value, dict):
        for key, inner in value.items():
            key_text = str(key or "")
            key_path = f"{path}.{key_text}" if path else key_text
            if key_text.lower() in _PHI_KEYS and inner not in (None, "", [], {}):
                issues.append(f"phi_key:{key_path}")
            issues.extend(collect_phi_issues(inner, key_path))
        return issues
    if isinstance(value, list):
        for idx, inner in enumerate(value):
            issues.extend(collect_phi_issues(inner, f"{path}[{idx}]"))
        return issues
    if phi_detected(str(value or "")):
        issues.append(f"phi_pattern:{path}")
    return issues


def _sanitize_case_item(item: Any, item_index: int, default_subrole: str) -> Dict[str, Any]:
    if not isinstance(item, dict):
        return {"error": "item_must_be_object", "item_index": item_index}

    domain = normalize_domain(item.get("domain"))
    label = clean_optional_text(item.get("label") or item.get("name") or item.get("term"))
    source_record_id = clean_optional_text(item.get("source_record_id") or item.get("id"))
    if not domain or not label or not source_record_id:
        return {
            "error": "item_requires_domain_label_source_record_id",
            "item_index": item_index,
        }

    return {
        "domain": domain,
        "label": label,
        "source_record_id": source_record_id,
        "source_kind": clean_optional_text(item.get("source_kind")),
        "why_observed": clean_optional_text(item.get("why_observed")),
        "subrole": normalize_subrole(item.get("subrole"), default_subrole),
        "annotations": sanitize_nested(item.get("annotations") or {}),
    }


def sanitize_case_causal_review_row(
    case_row: Dict[str, Any],
    allowed_domains: Iterable[str] | None = None,
) -> Dict[str, Any]:
    if not isinstance(case_row, dict):
        return {"error": "case_row_must_be_object"}

    issues = collect_phi_issues(case_row)
    if issues:
        return {
            "error": "unsafe_case_row",
            "diagnostics": {"sanitization_status": "rejected", "issues": issues[:20]},
        }

    allowed = {normalize_domain(domain) for domain in (allowed_domains or []) if normalize_domain(domain)}
    case_id = clean_optional_text(case_row.get("case_id"))
    case_summary = clean_optional_text(case_row.get("case_summary"))

    index_event = _sanitize_case_item(case_row.get("index_event") or {}, 0, "index_event")
    if index_event.get("error"):
        return {
            "error": "invalid_case_row_shape",
            "diagnostics": {
                "sanitization_status": "rejected",
                "reason": "invalid_index_event",
                "details": index_event,
            },
        }
    index_event["domain"] = "index_event"
    index_event["subrole"] = "index_event"

    candidate_items_raw = case_row.get("candidate_items")
    if not isinstance(candidate_items_raw, list) or not candidate_items_raw:
        return {
            "error": "invalid_case_row_shape",
            "diagnostics": {
                "sanitization_status": "rejected",
                "reason": "candidate_items_required",
            },
        }

    candidate_items = []
    candidate_items_by_domain: Dict[str, List[Dict[str, Any]]] = {}
    for idx, item in enumerate(candidate_items_raw, start=1):
        sanitized_item = _sanitize_case_item(item, idx, "contextual_factor")
        if sanitized_item.get("error"):
            return {
                "error": "invalid_case_row_shape",
                "diagnostics": {
                    "sanitization_status": "rejected",
                    "reason": "invalid_candidate_item",
                    "details": sanitized_item,
                },
            }
        if sanitized_item["subrole"] == "index_event":
            return {
                "error": "invalid_case_row_shape",
                "diagnostics": {
                    "sanitization_status": "rejected",
                    "reason": "candidate_items_must_not_use_index_event_subrole",
                    "item_index": idx,
                },
            }
        if allowed and sanitized_item["domain"] not in allowed:
            continue
        if sanitized_item["source_record_id"] == index_event["source_record_id"]:
            return {
                "error": "invalid_case_row_shape",
                "diagnostics": {
                    "sanitization_status": "rejected",
                    "reason": "candidate_items_must_not_repeat_index_event",
                    "item_index": idx,
                },
            }
        candidate_items.append(sanitized_item)
        candidate_items_by_domain.setdefault(sanitized_item["domain"], []).append(sanitized_item)

    if not candidate_items:
        return {
            "error": "no_candidate_items_in_allowed_domains",
            "diagnostics": {
                "sanitization_status": "rejected",
                "allowed_domains": sorted(allowed),
            },
        }

    context_items = []
    context_items_by_domain: Dict[str, List[Dict[str, Any]]] = {}
    for idx, item in enumerate(case_row.get("context_items") or [], start=1):
        sanitized_item = _sanitize_case_item(item, idx, "contextual_factor")
        if sanitized_item.get("error"):
            return {
                "error": "invalid_case_row_shape",
                "diagnostics": {
                    "sanitization_status": "rejected",
                    "reason": "invalid_context_item",
                    "details": sanitized_item,
                },
            }
        if allowed and sanitized_item["domain"] not in allowed:
            continue
        context_items.append(sanitized_item)
        context_items_by_domain.setdefault(sanitized_item["domain"], []).append(sanitized_item)

    case_metadata = sanitize_nested(case_row.get("case_metadata") or {})
    annotations = sanitize_nested(case_row.get("annotations") or {})
    raw_annotation_payload = case_row.get("annotations") or {}
    available_domains = [
        normalize_domain(domain)
        for domain in raw_annotation_payload.get("concept_set_available_domains", [])
        if normalize_domain(domain)
    ]
    if isinstance(annotations, dict):
        annotations["concept_set_available_domains"] = available_domains

    tool_hints_input = case_row.get("tool_hints") or {}
    available_expansions = [
        tool_name
        for tool_name in tool_hints_input.get("available_expansions", [])
        if tool_name in _ALLOWED_EXPANSION_TOOLS
    ]
    prefetch_expansions = [
        tool_name
        for tool_name in tool_hints_input.get("prefetch_expansions", [])
        if tool_name in available_expansions
    ]
    tool_hints = {
        "available_expansions": available_expansions,
        "prefetch_expansions": prefetch_expansions,
    }

    sanitized = {
        "case_id": case_id,
        "case_summary": case_summary,
        "index_event": index_event,
        "candidate_items": candidate_items,
        "candidate_items_by_domain": candidate_items_by_domain,
        "context_items": context_items,
        "context_items_by_domain": context_items_by_domain,
        "case_metadata": case_metadata,
        "annotations": annotations,
        "tool_hints": tool_hints,
    }
    diagnostics = {
        "sanitization_status": "ok",
        "candidate_item_count": len(candidate_items),
        "context_item_count": len(context_items),
        "candidate_domains": list(candidate_items_by_domain.keys()),
        "context_domains": list(context_items_by_domain.keys()),
        "allowed_domains_applied": sorted(allowed),
        "available_expansions": available_expansions,
        "prefetch_expansions": prefetch_expansions,
    }
    return {"sanitized_row": sanitized, "diagnostics": diagnostics}


def case_review_optional_tools() -> List[str]:
    return sorted(_ALLOWED_EXPANSION_TOOLS)
