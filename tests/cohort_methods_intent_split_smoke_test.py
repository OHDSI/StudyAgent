#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

ACP_URL = os.getenv(
    "ACP_URL",
    "http://127.0.0.1:8765/flows/cohort_methods_intent_split",
)
ACP_TIMEOUT = int(os.getenv("ACP_TIMEOUT", "180"))

STUDY_INTENT = (
    "Compare new users of sitagliptin versus new users of glipizide for acute myocardial "
    "infarction in adults with type 2 diabetes."
)


def main() -> int:
    payload = {
        "study_intent": STUDY_INTENT,
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(ACP_URL, data=body, method="POST")
    request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=ACP_TIMEOUT) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        print(raw)
        return 1

    print(raw)
    result = json.loads(raw)
    assert result.get("status") == "ok", result

    intent_split = result.get("intent_split") or {}
    assert intent_split.get("status") in {"ok", "needs_clarification"}, intent_split
    if intent_split.get("status") == "ok":
        assert intent_split.get("target_statement"), "target_statement must be non-empty"
        assert intent_split.get("comparator_statement"), "comparator_statement must be non-empty"
        assert intent_split.get("outcome_statement"), "outcome_statement must be non-empty"
        assert intent_split.get("outcome_statements"), "outcome_statements must be non-empty"
    return 0


if __name__ == "__main__":
    sys.exit(main())
