"""Live ACP/MCP/LLM smoke coverage for computable phenotype proposal mode.

Uses synthetic, non-PHI narrative text. It intentionally stops at concept review and
never emits a Capr or Circe artifact from an unreviewed LLM proposal.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

FLOW_URL = os.getenv(
    "ACP_URL", "http://127.0.0.1:8765/flows/phenotype_make_computable"
)
TIMEOUT_SECONDS = int(os.getenv("ACP_TIMEOUT", "360"))


def main() -> int:
    payload = {
        "narrative_statement": (
            "Earliest event of cirrhosis of liver. "
            "Persons exit at end of observation period."
        ),
        "confirmed_scope": True,
        "scope": {
            "index_event": "Cirrhosis of liver",
            "criterion_domains": {"Cirrhosis of liver": "Condition"},
            "entry_limit": "First",
            "prior_observation": 0,
            "index_day_boundary": "included",
            "windows": "none",
            "exit_strategy": "observation",
        },
        "concept_review_mode": "propose",
        "concept_sets": [],
    }
    request = urllib.request.Request(
        FLOW_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ACP request failed with HTTP {exc.code}: {body}") from exc

    plan = result.get("proposed_plan")
    if result.get("status") != "needs_concept_review" or result.get("llm_status") != "ok":
        raise AssertionError(f"expected successful proposal for review, got {result}")
    if not result.get("concept_candidates") or not isinstance(plan, dict):
        raise AssertionError("expected vocabulary candidates and a structured LLM proposal")
    required = {"status", "scope_check", "concept_sets", "cohort_plan", "assumptions", "warnings"}
    if not required.issubset(plan):
        raise AssertionError(f"proposal missing contract keys: {sorted(required - set(plan))}")
    print(
        "phenotype_make_computable proposal smoke passed: "
        f"{len(result['concept_candidates'])} candidates; proposal status={plan['status']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
