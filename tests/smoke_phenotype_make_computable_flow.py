"""Live ACP/MCP/R smoke coverage for the computable phenotype flow.

Uses reviewed reference-set concept policies only; no LLM request is made.
"""

from __future__ import annotations

import csv
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
FLOW_URL = os.getenv(
    "ACP_URL", "http://127.0.0.1:8765/flows/phenotype_make_computable"
)
TIMEOUT_SECONDS = int(os.getenv("ACP_TIMEOUT", "360"))


def _reviewed_concept_sets(case_id: str) -> list[dict[str, Any]]:
    path = REPO_ROOT / "docs" / "evaluation" / "phenotype_make_computable" / "reference_set" / "training_cohorts" / case_id / "concept_roots.csv"
    grouped: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            concept_set = grouped.setdefault(
                row["concept_set_name"],
                {"name": row["concept_set_name"], "domain": row["domain_id"], "items": []},
            )
            concept_set["items"].append(
                {
                    "concept_id": int(row["concept_id"]),
                    "domain": row["domain_id"],
                    "include_descendants": row["include_descendants"].lower() == "true",
                    "include_mapped": row["include_mapped"].lower() == "true",
                    "is_excluded": row["is_excluded"].lower() == "true",
                }
            )
    return list(grouped.values())


def _post(payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(
        FLOW_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ACP request failed with HTTP {exc.code}: {body}") from exc


def _request(case_id: str, narrative: str, scope: dict[str, Any]) -> dict[str, Any]:
    return _post(
        {
            "narrative_statement": narrative,
            "confirmed_scope": True,
            "scope": scope,
            "concept_review_mode": "provided_only",
            "concept_sets": _reviewed_concept_sets(case_id),
        }
    )


def _assert_validated(case_id: str, result: dict[str, Any], concept_sets: int, limit: str) -> None:
    if result.get("status") != "ok" or result.get("validation", {}).get("status") != "passed":
        raise AssertionError(f"{case_id}: expected validated response, got {result}")
    circe = result.get("circe_json") or {}
    primary = circe.get("PrimaryCriteria") or {}
    actual_limit = (primary.get("PrimaryCriteriaLimit") or {}).get("Type")
    if len(circe.get("ConceptSets") or []) != concept_sets or actual_limit != limit:
        raise AssertionError(f"{case_id}: unexpected Circe structure")
    capr = result.get("capr") or {}
    if capr.get("entry_point") != "phenotype_make_computable_definition" or not capr.get("source"):
        raise AssertionError(f"{case_id}: missing function-form Capr artifact")



def _database_backed_concept_review_smoke() -> str:
    """Exercise live vocabulary retrieval when a database engine is configured."""
    if not os.getenv("OMOP_DB_ENGINE", "").strip():
        return "database-backed concept review skipped: OMOP_DB_ENGINE is not set"

    result = _post(
        {
            "narrative_statement": "New users of warfarin.",
            "confirmed_scope": True,
            "scope": {
                "index_event": "warfarin",
                "criterion_domains": {"warfarin": "Drug"},
                "criterion_vocabularies": {"warfarin": ["RxNorm"]},
                "entry_limit": "First",
                "prior_observation": 0,
                "index_day_boundary": "included",
                "windows": "none",
                "exit_strategy": "observation",
                "visit_overlap": False,
            },
            "concept_review_mode": "required",
            "review_delivery": "session",
            "candidate_limit": 20,
            "concept_sets": [],
        }
    )
    if result.get("status") != "needs_concept_review":
        raise AssertionError(
            "database-backed concept review: expected needs_concept_review, got "
            f"{result}"
        )
    if int(result.get("candidate_count") or 0) < 1:
        raise AssertionError(
            "database-backed concept review: OMOP_DB_ENGINE is set but no "
            "Warfarin RxNorm Drug candidates were returned"
        )
    return "database-backed concept review passed"
def main() -> int:
    simple = _request(
        "710",
        "Earliest event of Advanced Liver Disease. Persons exit on end of observation period.",
        {
            "index_event": "Advanced Liver Disease",
            "criterion_domains": {"Advanced Liver Disease": "Condition"},
            "entry_limit": "First",
            "prior_observation": 0,
            "index_day_boundary": "included",
            "windows": "none",
            "exit_strategy": "observation",
        },
    )
    _assert_validated("710", simple, concept_sets=1, limit="First")

    visit = _request(
        "222",
        "Earliest SJS/TEN diagnosis overlapping an inpatient or ER visit; exit one day after cohort end.",
        {
            "index_event": "Stevens-Johnson syndrome, Toxic epidermal necrolysis spectrum",
            "criterion_domains": {"SJS/TEN diagnosis": "Condition", "Inpatient or ER visit": "Visit"},
            "entry_limit": "All",
            "prior_observation": 0,
            "index_day_boundary": "included",
            "windows": "none",
            "visit_overlap": True,
            "visit_overlap_mode": "attrition",
            "exit_strategy": {"type": "fixed", "index": "endDate", "offset_days": 1},
        },
    )
    _assert_validated("222", visit, concept_sets=2, limit="All")
    if ((visit["circe_json"].get("EndStrategy") or {}).get("DateOffset") or {}).get("Offset") != 1:
        raise AssertionError("222: expected one-day fixed exit")

    additional_cases = {
        "794": (
            "Earliest hemorrhage of digestive system; exit 14 days after cohort end.",
            {
                "index_event": "Digestive hemorrhage",
                "criterion_domains": {"Digestive hemorrhage": "Condition"},
                "entry_limit": "All",
                "prior_observation": 0,
                "index_day_boundary": "included",
                "windows": "none",
                "exit_strategy": {"type": "fixed", "index": "endDate", "offset_days": 14},
            },
            1,
            14,
            None,
        ),
        "743": (
            "Earliest diabetic ketoacidosis diagnosis overlapping an inpatient or ER visit; exit 30 days after index start.",
            {
                "index_event": "Diabetic ketoacidosis",
                "criterion_domains": {"Diabetic ketoacidosis": "Condition", "Inpatient or ER visit": "Visit"},
                "entry_limit": "All",
                "prior_observation": 0,
                "index_day_boundary": "included",
                "windows": "none",
                "visit_overlap": True,
                "visit_overlap_mode": "entry",
                "exit_strategy": {"type": "fixed", "index": "startDate", "offset_days": 30},
            },
            2,
            30,
            None,
        ),
        "1340": (
            "Earliest anorexia nervosa event; exit 30 days after cohort end and collapse within 365 days.",
            {
                "index_event": "Anorexia nervosa",
                "criterion_domains": {"Anorexia nervosa": "Condition"},
                "entry_limit": "All",
                "prior_observation": 0,
                "index_day_boundary": "included",
                "windows": "none",
                "exit_strategy": {"type": "fixed", "index": "endDate", "offset_days": 30},
                "era_days": 365,
            },
            1,
            30,
            365,
        ),
        "1341": (
            "Earliest eating disorder event; exit 30 days after cohort end and collapse within 365 days.",
            {
                "index_event": "Eating disorders",
                "criterion_domains": {"Eating disorders": "Condition"},
                "entry_limit": "All",
                "prior_observation": 0,
                "index_day_boundary": "included",
                "windows": "none",
                "exit_strategy": {"type": "fixed", "index": "endDate", "offset_days": 30},
                "era_days": 365,
            },
            1,
            30,
            365,
        ),
        "1345": (
            "Earliest personality disorder event; exit 30 days after cohort end and collapse within 365 days.",
            {
                "index_event": "Personality disorders",
                "criterion_domains": {"Personality disorders": "Condition"},
                "entry_limit": "All",
                "prior_observation": 0,
                "index_day_boundary": "included",
                "windows": "none",
                "exit_strategy": {"type": "fixed", "index": "endDate", "offset_days": 30},
                "era_days": 365,
            },
            1,
            30,
            365,
        ),
        "1346": (
            "Earliest attention-deficit hyperactivity disorder event; exit 30 days after cohort end and collapse within 365 days.",
            {
                "index_event": "Attention-deficit hyperactivity disorder",
                "criterion_domains": {"Attention-deficit hyperactivity disorder": "Condition"},
                "entry_limit": "All",
                "prior_observation": 0,
                "index_day_boundary": "included",
                "windows": "none",
                "exit_strategy": {"type": "fixed", "index": "endDate", "offset_days": 30},
                "era_days": 365,
            },
            1,
            30,
            365,
        ),
        "1347": (
            "Earliest posttraumatic stress disorder event; exit 30 days after cohort end and collapse within 365 days.",
            {
                "index_event": "Posttraumatic stress disorder",
                "criterion_domains": {"Posttraumatic stress disorder": "Condition"},
                "entry_limit": "All",
                "prior_observation": 0,
                "index_day_boundary": "included",
                "windows": "none",
                "exit_strategy": {"type": "fixed", "index": "endDate", "offset_days": 30},
                "era_days": 365,
            },
            1,
            30,
            365,
        ),
    }
    for case_id, (narrative, scope, concept_sets, offset_days, era_days) in additional_cases.items():
        result = _request(case_id, narrative, scope)
        _assert_validated(case_id, result, concept_sets=concept_sets, limit="All")
        date_offset = ((result["circe_json"].get("EndStrategy") or {}).get("DateOffset") or {}).get("Offset")
        if date_offset != offset_days:
            raise AssertionError(f"{case_id}: expected {offset_days}-day fixed exit")
        if era_days is not None and (result["circe_json"].get("CollapseSettings") or {}).get("EraPad") != era_days:
            raise AssertionError(f"{case_id}: expected {era_days}-day era collapse")

    temporal = _request(
        "63",
        "Earliest transverse myelitis diagnosis or symptom followed by diagnosis within 30 days, with 365 days continuous observation before index.",
        {
            "index_event": "Transverse myelitis",
            "criterion_domains": {"Transverse myelitis diagnosis": "Condition", "Transverse myelitis symptoms": "Condition"},
            "entry_limit": "All",
            "prior_observation": 365,
            "index_day_boundary": "included",
            "windows": "none",
            "exit_strategy": {"type": "fixed", "index": "startDate", "offset_days": 1},
            "temporal_followup": {"index_concept_set": "Transverse Myelitis", "trigger_concept_set": "Symptoms for Transverse Myelitis", "followup_days": 30, "washout_days": 365},
        },
    )
    _assert_validated("63", temporal, concept_sets=2, limit="All")
    if (temporal["circe_json"].get("PrimaryCriteria") or {}).get("ObservationWindow") != {"PriorDays": 365, "PostDays": 0}:
        raise AssertionError("63: expected 365-day observation window")

    mixed = _request(
        "858",
        "Earliest rheumatoid arthritis diagnosis by condition or observation date.",
        {
            "index_event": "Rheumatoid arthritis",
            "criterion_domains": {"Rheumatoid arthritis": "Condition or Observation"},
            "entry_limit": "First",
            "prior_observation": 0,
            "index_day_boundary": "included",
            "windows": "none",
            "exit_strategy": "observation",
        },
    )
    if mixed.get("status") != "needs_clarification" or mixed.get("clarification_type") != "mixed_domain_entry":
        raise AssertionError(f"858: expected mixed-domain clarification, got {mixed}")

    print("phenotype_make_computable workflow smoke passed: 9 validated reference cases, corrected 63, and 858 clarification")
    print(_database_backed_concept_review_smoke())
    return 0


if __name__ == "__main__":
    sys.exit(main())
