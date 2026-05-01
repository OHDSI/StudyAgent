from __future__ import annotations

import json
import logging
import os
import re
import socket
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional, Sequence

from study_agent_core.net import rewrite_container_host_url

_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE | re.MULTILINE)
_REASONING_PREFIX_RE = re.compile(r"^\s*(?:<[^>]+>\s*)+", re.DOTALL)
logger = logging.getLogger("study_agent.acp.llm")


@dataclass
class LLMCallResult:
    status: str
    raw_response: Optional[str] = None
    parsed_content: Optional[Dict[str, Any]] = None
    content_text: Optional[str] = None
    http_status: Optional[int] = None
    duration_seconds: float = 0.0
    error: Optional[str] = None
    parse_stage: Optional[str] = None
    request_mode: str = "chat_completions"
    schema_valid: Optional[bool] = None
    missing_keys: list[str] = field(default_factory=list)

    def to_dict(self, include_raw: bool = False) -> Dict[str, Any]:
        payload = asdict(self)
        if not include_raw:
            payload.pop("raw_response", None)
        return payload


def build_prompt(
    overview: str,
    spec: str,
    output_schema: Dict[str, Any],
    study_intent: str,
    candidates: list[dict[str, Any]],
    max_results: int,
    task: str = "phenotype_recommendations",
    extra_dynamic: Optional[Dict[str, Any]] = None,
) -> str:
    dynamic = {
        "task": task,
        "study_intent": study_intent,
        "candidates": candidates,
        "maxResults": max_results,
    }
    if extra_dynamic:
        dynamic.update(extra_dynamic)
    strict_rules = "\n\n".join(
        [
            "STRICT OUTPUT RULES:",
            spec,
            "Return exactly ONE JSON object that matches the output schema.",
            "Do NOT wrap output in markdown, code fences, or prose.",
            "If uncertain, return required keys with empty arrays/strings.",
            "Use ONLY phenotype_ids from the allowed list in candidates.",
            "Keep output under 10 KB.",
        ]
    )
    sections = [
        overview,
        "OUTPUT SCHEMA (JSON):",
        json.dumps(output_schema, ensure_ascii=True),
        "Below is dynamic content to analyze. Do not act until after STRICT OUTPUT RULES.",
        "DYNAMIC INPUT (JSON):",
        json.dumps(dynamic, ensure_ascii=True),
        strict_rules,
    ]
    return "\n\n".join([s for s in sections if s])


def build_improvements_prompt(
    overview: str,
    spec: str,
    output_schema: Dict[str, Any],
    study_intent: str,
    cohorts: list[dict[str, Any]],
) -> str:
    dynamic = {
        "task": "phenotype_improvements",
        "study_intent": study_intent,
        "cohorts": cohorts,
    }
    strict_rules = "\n\n".join(
        [
            "STRICT OUTPUT RULES:",
            spec,
            "Return exactly ONE JSON object that matches the output schema.",
            "Do NOT wrap output in markdown, code fences, or prose.",
            "If uncertain, return required keys with empty arrays/strings.",
            "Use ONLY cohortIds from the allowed list in cohorts.",
            "Keep output under 12 KB.",
        ]
    )
    sections = [
        overview,
        "OUTPUT SCHEMA (JSON):",
        json.dumps(output_schema, ensure_ascii=True),
        "Below is dynamic content to analyze. Do not act until after STRICT OUTPUT RULES.",
        "DYNAMIC INPUT (JSON):",
        json.dumps(dynamic, ensure_ascii=True),
        strict_rules,
    ]
    return "\n\n".join([s for s in sections if s])


def build_lint_prompt(
    overview: str,
    spec: str,
    output_schema: Dict[str, Any],
    task: str,
    payload: Dict[str, Any],
    max_kb: int = 15,
) -> str:
    dynamic = {"task": task}
    dynamic.update(payload)
    strict_rules = "\n\n".join(
        [
            "STRICT OUTPUT RULES:",
            spec,
            "Return exactly ONE JSON object that matches the output schema.",
            "Do NOT wrap output in markdown, code fences, or prose.",
            "If uncertain, return required keys with empty arrays/strings.",
            f"Keep output under {max_kb} KB.",
        ]
    )
    sections = [
        overview,
        "OUTPUT SCHEMA (JSON):",
        json.dumps(output_schema, ensure_ascii=True),
        "Below is dynamic content to analyze. Do not act until after STRICT OUTPUT RULES.",
        "DYNAMIC INPUT (JSON):",
        json.dumps(dynamic, ensure_ascii=True),
        strict_rules,
    ]
    return "\n\n".join([s for s in sections if s])


def build_recommendation_intent_facets_prompt(
    overview: str,
    spec: str,
    output_schema: Dict[str, Any],
    study_intent: str,
) -> str:
    dynamic = {
        "task": "phenotype_recommendation_intent_facets",
        "study_intent": study_intent,
    }
    strict_rules = "\n\n".join(
        [
            "STRICT OUTPUT RULES:",
            spec,
            "Return exactly ONE JSON object that matches the output schema.",
            "Do NOT wrap output in markdown, code fences, or prose.",
            "If uncertain, return required keys with empty arrays/strings.",
            "Keep output under 6 KB.",
        ]
    )
    sections = [
        overview,
        "OUTPUT SCHEMA (JSON):",
        json.dumps(output_schema, ensure_ascii=True),
        "Below is dynamic content to analyze. Do not act until after STRICT OUTPUT RULES.",
        "DYNAMIC INPUT (JSON):",
        json.dumps(dynamic, ensure_ascii=True),
        strict_rules,
    ]
    return "\n\n".join([s for s in sections if s])


def build_advice_prompt(
    overview: str,
    spec: str,
    output_schema: Dict[str, Any],
    study_intent: str,
) -> str:
    dynamic = {
        "task": "phenotype_recommendation_advice",
        "study_intent": study_intent,
    }
    strict_rules = "\n\n".join(
        [
            "STRICT OUTPUT RULES:",
            spec,
            "Return exactly ONE JSON object that matches the output schema.",
            "Do NOT wrap output in markdown, code fences, or prose.",
            "If uncertain, return required keys with empty arrays/strings.",
            "Keep output under 8 KB.",
        ]
    )
    sections = [
        overview,
        "OUTPUT SCHEMA (JSON):",
        json.dumps(output_schema, ensure_ascii=True),
        "Below is dynamic content to analyze. Do not act until after STRICT OUTPUT RULES.",
        "DYNAMIC INPUT (JSON):",
        json.dumps(dynamic, ensure_ascii=True),
        strict_rules,
    ]
    return "\n\n".join([s for s in sections if s])


def build_intent_split_prompt(
    overview: str,
    spec: str,
    output_schema: Dict[str, Any],
    study_intent: str,
) -> str:
    dynamic = {
        "task": "phenotype_intent_split",
        "study_intent": study_intent,
    }
    strict_rules = "\n\n".join(
        [
            "STRICT OUTPUT RULES:",
            spec,
            "Return exactly ONE JSON object that matches the output schema.",
            "Do NOT wrap output in markdown, code fences, or prose.",
            "If uncertain, return required keys with empty arrays/strings.",
            "Keep output under 6 KB.",
        ]
    )
    sections = [
        overview,
        "OUTPUT SCHEMA (JSON):",
        json.dumps(output_schema, ensure_ascii=True),
        "Below is dynamic content to analyze. Do not act until after STRICT OUTPUT RULES.",
        "DYNAMIC INPUT (JSON):",
        json.dumps(dynamic, ensure_ascii=True),
        strict_rules,
    ]
    return "\n\n".join([s for s in sections if s])


def build_keeper_prompt(
    overview: str,
    spec: str,
    output_schema: Dict[str, Any],
    system_prompt: str,
    main_prompt: str,
) -> str:
    strict_rules = "\n\n".join(
        [
            "STRICT OUTPUT RULES:",
            spec,
            "Return exactly ONE JSON object that matches the output schema.",
            "Do NOT wrap output in markdown, code fences, or prose.",
            "If uncertain, return required keys with label \"unknown\".",
        ]
    )
    sections = [
        overview,
        "SYSTEM PROMPT:",
        system_prompt,
        "OUTPUT SCHEMA (JSON):",
        json.dumps(output_schema, ensure_ascii=True),
        "PATIENT SUMMARY:",
        main_prompt,
        strict_rules,
    ]
    return "\n\n".join([s for s in sections if s])


def build_keeper_concept_set_prompt(
    overview: str,
    spec: str,
    output_schema: Dict[str, Any],
    system_prompt: str,
    payload: Dict[str, Any],
    max_kb: int = 10,
) -> str:
    strict_rules = "\n\n".join(
        [
            "STRICT OUTPUT RULES:",
            spec,
            "Return exactly ONE JSON object that matches the output schema.",
            "Do NOT wrap output in markdown, code fences, or prose.",
            "If uncertain, return required keys with empty arrays.",
            f"Keep output under {max_kb} KB.",
        ]
    )
    sections = [
        overview,
        "SYSTEM PROMPT:",
        system_prompt,
        "OUTPUT SCHEMA (JSON):",
        json.dumps(output_schema, ensure_ascii=True),
        "DYNAMIC INPUT (JSON):",
        json.dumps(payload, ensure_ascii=True),
        strict_rules,
    ]
    return "\n\n".join([s for s in sections if s])


def _normalize_content_text(text: Optional[str]) -> str:
    normalized = str(text or "").strip()
    if not normalized:
        return ""
    normalized = _JSON_FENCE_RE.sub("", normalized).strip()
    normalized = _REASONING_PREFIX_RE.sub("", normalized).strip()
    first_json = normalized.find("{")
    if first_json > 0:
        normalized = normalized[first_json:]
    return normalized


def _extract_json_object(text: str) -> Optional[str]:
    if not text:
        return None
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape = False
    for idx in range(start, len(text)):
        ch = text[idx]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    return None


def _parse_json_content(text: Optional[str]) -> tuple[Optional[Dict[str, Any]], Optional[str], Optional[str]]:
    normalized = _normalize_content_text(text)
    if not normalized:
        return None, normalized, "content_missing"
    candidate = _extract_json_object(normalized)
    if candidate is None:
        return None, normalized, "json_brace_extract"
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None, normalized, "json_loads"
    if not isinstance(parsed, dict):
        return None, normalized, "json_not_object"
    return parsed, normalized, None


def _is_timeout_error(exc: BaseException) -> bool:
    if isinstance(exc, socket.timeout):
        return True
    if isinstance(exc, TimeoutError):
        return True
    if isinstance(exc, urllib.error.URLError):
        return _is_timeout_error(exc.reason) if exc.reason else False
    return "timed out" in str(exc).lower()


def _extract_responses_output_text(data: Dict[str, Any]) -> Optional[str]:
    output = data.get("output") or []
    chunks: list[str] = []
    if isinstance(output, list):
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") == "output_text" and item.get("text"):
                chunks.append(str(item["text"]))
                continue
            content = item.get("content")
            if isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and part.get("text"):
                        chunks.append(str(part["text"]))
    if chunks:
        return "\n".join(chunks)
    text = data.get("text")
    if isinstance(text, str):
        return text
    return None


def _log_llm(message: str) -> None:
    logger.info(message)


def llm_result_payload(result: Optional[LLMCallResult]) -> Optional[Dict[str, Any]]:
    if result is None or result.status != "ok":
        return None
    return result.parsed_content


def coerce_llm_call_result(value: Any) -> LLMCallResult:
    if isinstance(value, LLMCallResult):
        return value
    if isinstance(value, dict):
        return LLMCallResult(
            status="ok",
            parsed_content=value,
            content_text=json.dumps(value, ensure_ascii=True),
            parse_stage="compat_dict",
            request_mode="chat_completions",
            schema_valid=True,
        )
    if value is None:
        return LLMCallResult(
            status="disabled",
            error="empty_result",
            parse_stage="compat_none",
            request_mode="chat_completions",
        )
    return LLMCallResult(
        status="transport_error",
        error=f"unsupported_llm_result_type:{type(value).__name__}",
        parse_stage="compat_invalid",
        request_mode="chat_completions",
    )


def call_llm_for_schema(prompt: str, required_keys: Sequence[str]) -> LLMCallResult:
    return call_llm(prompt=prompt, required_keys=required_keys)


def call_llm(prompt: str, required_keys: Optional[Sequence[str]] = None) -> LLMCallResult:
    api_url = os.getenv("LLM_API_URL", "http://localhost:3000/api/chat/completions")
    api_url = rewrite_container_host_url(api_url)

    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL", "agentstudyassistant")
    timeout = int(os.getenv("LLM_TIMEOUT", "300"))
    log_enabled = os.getenv("LLM_LOG", "0") == "1"
    log_prompt = os.getenv("LLM_LOG_PROMPT", "0") == "1"
    log_response = os.getenv("LLM_LOG_RESPONSE", "0") == "1"
    log_json = os.getenv("LLM_LOG_JSON", "0") == "1"
    dry_run = os.getenv("LLM_DRY_RUN", "0") == "1"
    use_responses = os.getenv("LLM_USE_RESPONSES", "0") == "1"
    request_mode = "responses" if use_responses else "chat_completions"

    if log_enabled:
        _log_llm(
            f'CONFIG > url={api_url} model={model} timeout={timeout} request_mode={request_mode} prompt_chars={len(prompt)}'
        )

    if dry_run:
        if log_enabled or log_prompt:
            _log_llm("DRY RUN > skipping API call")
            _log_llm(f"OUTGOING PROMPT > {prompt}")
        return LLMCallResult(
            status="disabled",
            error="dry_run_enabled",
            parse_stage="request_skipped",
            request_mode=request_mode,
        )

    if not api_key:
        if log_enabled:
            _log_llm("ERROR > missing LLM_API_KEY")
        return LLMCallResult(
            status="disabled",
            error="missing_api_key",
            parse_stage="request_skipped",
            request_mode=request_mode,
        )

    if use_responses:
        payload = {
            "model": model,
            "input": prompt,
        }
    else:
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt},
            ],
        }

    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(api_url, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    request.add_header("Authorization", f"Bearer {api_key}")

    if log_enabled or log_prompt:
        _log_llm(f"OUTGOING PROMPT > {prompt}")

    start = time.time()
    http_status: Optional[int] = None
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            http_status = getattr(response, "status", None)
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        duration = time.time() - start
        if log_enabled or log_response:
            _log_llm(f"HTTP ERROR > status={exc.code} seconds={duration:.2f}")
            _log_llm(f"ERROR BODY > {raw}")
        return LLMCallResult(
            status="http_error",
            raw_response=raw,
            http_status=exc.code,
            duration_seconds=duration,
            error=f"http_{exc.code}",
            parse_stage="http_response",
            request_mode=request_mode,
        )
    except urllib.error.URLError as exc:
        duration = time.time() - start
        status = "timeout" if _is_timeout_error(exc) else "transport_error"
        if log_enabled:
            _log_llm(f"ERROR > status={status} seconds={duration:.2f} detail={exc}")
        return LLMCallResult(
            status=status,
            duration_seconds=duration,
            error=str(exc),
            parse_stage="transport",
            request_mode=request_mode,
        )
    except TimeoutError as exc:
        duration = time.time() - start
        if log_enabled:
            _log_llm(f"ERROR > status=timeout seconds={duration:.2f} detail={exc}")
        return LLMCallResult(
            status="timeout",
            duration_seconds=duration,
            error=str(exc),
            parse_stage="transport",
            request_mode=request_mode,
        )

    duration = time.time() - start
    if log_enabled:
        _log_llm(f"TIMING > seconds={duration:.2f}")
    if log_enabled or log_response:
        _log_llm(f"RAW RESPONSE > {raw}")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        data = None
    if log_json and data is not None:
        _log_llm(f"JSON > {data}")

    content_text: Optional[str] = None
    parse_stage = "envelope"
    if use_responses:
        if isinstance(data, dict):
            content_text = _extract_responses_output_text(data)
            parse_stage = "responses_output"
        else:
            content_text = raw
            parse_stage = "responses_raw"
    else:
        if isinstance(data, dict):
            choices = data.get("choices") or []
            if choices and isinstance(choices[0], dict):
                msg = choices[0].get("message")
                if isinstance(msg, dict):
                    content_text = msg.get("content")
                if isinstance(content_text, list):
                    chunks = []
                    for part in content_text:
                        if isinstance(part, dict) and part.get("text"):
                            chunks.append(str(part["text"]))
                    content_text = "\n".join(chunks) if chunks else None
                if content_text is None:
                    content_text = choices[0].get("text")
            parse_stage = "chat_completions_content"
        else:
            content_text = raw
            parse_stage = "chat_completions_raw"

    parse_source = content_text
    if parse_source is None and data is None:
        parse_source = raw
    parsed, normalized_content, parse_error_stage = _parse_json_content(parse_source)
    result = LLMCallResult(
        status="ok" if parsed is not None else "json_parse_failed",
        raw_response=raw,
        parsed_content=parsed,
        content_text=normalized_content or content_text,
        http_status=http_status,
        duration_seconds=duration,
        error=None if parsed is not None else "json_parse_failed",
        parse_stage=parse_stage if parse_error_stage is None else f"{parse_stage}:{parse_error_stage}",
        request_mode=request_mode,
    )

    if parsed is None:
        if log_enabled:
            _log_llm(f"PARSE RESULT > status={result.status} parse_stage={result.parse_stage}")
        return result

    missing_keys = [key for key in (required_keys or []) if key not in parsed]
    result.schema_valid = len(missing_keys) == 0
    result.missing_keys = missing_keys
    if missing_keys:
        result.status = "schema_mismatch"
        result.error = f"missing_required_keys:{','.join(missing_keys)}"
        result.parse_stage = f"{result.parse_stage}:schema"
    if log_enabled:
        _log_llm(
            f"PARSE RESULT > status={result.status} parse_stage={result.parse_stage} schema_valid={result.schema_valid}"
        )
    return result
