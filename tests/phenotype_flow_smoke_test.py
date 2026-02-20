#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import urllib.request

ACP_URL = os.getenv("ACP_URL", "http://127.0.0.1:8765/flows/phenotype_recommendation")
ACP_TIMEOUT = int(os.getenv("ACP_TIMEOUT", "180"))

STUDY_INTENT = (
    "Study intent: Identify clinical risk factors for older adult patients who experience "
    "an adverse event of acute gastro-intenstinal (GI) bleeding. The GI bleed has to be "
    "detected in the hospital setting. Risk factors can include concomitant medications "
    "or chronic and acute conditions."
)


def main() -> int:
    payload = {
        "study_intent": STUDY_INTENT,
        "top_k": 20,
        "max_results": 10,
        "candidate_limit": int(os.getenv("LLM_CANDIDATE_LIMIT", "10")),
    }
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(ACP_URL, data=body, method="POST")
    request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=ACP_TIMEOUT) as response:
            raw = response.read().decode("utf-8")
            print(raw)
            return 0
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        print(raw)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
