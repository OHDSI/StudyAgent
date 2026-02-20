from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any, Dict, Optional


def build_prompt(
    overview: str,
    spec: str,
    output_schema: Dict[str, Any],
    study_intent: str,
    candidates: list[dict[str, Any]],
    max_results: int,
) -> str:
    dynamic = {
        "task": "phenotype_recommendations",
        "study_intent": study_intent,
        "candidates": candidates,
        "maxResults": max_results,
    }
    strict_rules = "\n\n".join(
        [
            "STRICT OUTPUT RULES:",
            spec,
            "Return exactly ONE JSON object that matches the output schema.",
            "Do NOT wrap output in markdown, code fences, or prose.",
            "If uncertain, return required keys with empty arrays/strings.",
            "Use ONLY cohortIds from the allowed list in candidates.",
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


def _extract_json_object(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None


def call_llm(prompt: str) -> Optional[Dict[str, Any]]:
    api_url = os.getenv("LLM_API_URL", "http://localhost:3000/api/chat/completions")
    api_key = os.getenv("LLM_API_KEY")
    model = os.getenv("LLM_MODEL", "agentstudyassistant")
    timeout = int(os.getenv("LLM_TIMEOUT", "180"))
    log_enabled = os.getenv("LLM_LOG", "0") == "1"
    dry_run = os.getenv("LLM_DRY_RUN", "0") == "1"
    use_responses = os.getenv("LLM_USE_RESPONSES", "0") == "1"

    if log_enabled:
        print(f"LLM CONFIG > url={api_url} model={model} timeout={timeout} responses={use_responses}")

    if dry_run:
        if log_enabled:
            print("LLM DRY RUN > skipping API call")
            print("LLM OUTGOING PROMPT >", prompt)
        return None

    if not api_key:
        if log_enabled:
            print("LLM ERROR > missing LLM_API_KEY")
        return None

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

    if log_enabled:
        print("LLM OUTGOING PROMPT >", prompt)

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        if log_enabled:
            print(f"LLM HTTP ERROR > {exc.code}")
            print("LLM ERROR BODY >", raw)
        return None
    except urllib.error.URLError as exc:
        if log_enabled:
            print(f"LLM ERROR > {exc}")
        return None

    if log_enabled:
        print("LLM RAW RESPONSE >", raw)

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _extract_json_object(raw)

    if use_responses:
        output_text = None
        if isinstance(data, dict):
            output = data.get("output") or []
            if output and isinstance(output, list):
                for item in output:
                    if isinstance(item, dict) and item.get("type") == "output_text":
                        output_text = item.get("text")
                        break
        return _extract_json_object(output_text or raw)

    content = None
    if isinstance(data, dict):
        choices = data.get("choices") or []
        if choices and isinstance(choices[0], dict):
            msg = choices[0].get("message")
            if isinstance(msg, dict):
                content = msg.get("content")
            if content is None:
                content = choices[0].get("text")
    if content is None:
        content = raw
    return _extract_json_object(content)
