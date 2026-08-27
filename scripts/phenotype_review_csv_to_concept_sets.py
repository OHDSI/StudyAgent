#!/usr/bin/env python3
"""Validate an edited phenotype review CSV and emit review-gated concept sets."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any

_TRUE_MARK = "x"
_POLICY_COLUMNS = (
    "review_include_concept",
    "review_include_descendants",
    "review_include_mapped",
    "review_exclude_concepts",
    "review_exclude_descendants",
    "review_exclude_mapped",
)


def _marked(row: dict[str, str], column: str, row_number: int) -> bool:
    value = (row.get(column) or "").strip()
    if not value:
        return False
    if value.casefold() == _TRUE_MARK:
        return True
    raise ValueError(f"row {row_number}: {column} must be blank or x")


def parse_review_csv(csv_path: Path, concept_set_name: str = "", manifest_path: Path | None = None) -> dict[str, Any]:
    # A single name remains a convenient fallback. Multi-set review packages carry a
    # frozen lane name per candidate row and are grouped by that explicit name.
    manifest: dict[str, Any] = {}
    if manifest_path is not None:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != 1:
            raise ValueError("unsupported_review_manifest_schema")

    concept_sets_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {}
    approval_preview: list[dict[str, Any]] = []
    unassessed_includes: list[dict[str, Any]] = []
    with csv_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("review_csv_has_no_header")
        missing = [column for column in _POLICY_COLUMNS if column not in reader.fieldnames]
        if missing:
            raise ValueError(f"review_csv_missing_columns:{','.join(missing)}")
        for row_number, row in enumerate(reader, start=2):
            include = _marked(row, "review_include_concept", row_number)
            include_descendants = _marked(row, "review_include_descendants", row_number)
            include_mapped = _marked(row, "review_include_mapped", row_number)
            exclude = _marked(row, "review_exclude_concepts", row_number)
            exclude_descendants = _marked(row, "review_exclude_descendants", row_number)
            exclude_mapped = _marked(row, "review_exclude_mapped", row_number)
            if include and exclude:
                raise ValueError(f"row {row_number}: include_and_exclude_are_mutually_exclusive")
            if (include_descendants or include_mapped) and not include:
                raise ValueError(f"row {row_number}: include_descendants_or_mapped_requires_include_concept")
            if (exclude_descendants or exclude_mapped) and not exclude:
                raise ValueError(f"row {row_number}: exclude_descendants_or_mapped_requires_exclude_concepts")
            if not include and not exclude:
                continue
            try:
                concept_id = int((row.get("concept_id") or "").strip())
            except ValueError as exc:
                raise ValueError(f"row {row_number}: invalid_concept_id") from exc
            domain = (row.get("domain") or "").strip()
            if not domain:
                raise ValueError(f"row {row_number}: domain is required for a selected concept")
            item = {
                "concept_id": concept_id,
                "domain": domain,
                "include_descendants": include_descendants if include else exclude_descendants,
                "include_mapped": include_mapped if include else exclude_mapped,
                "is_excluded": exclude,
            }
            row_set_name = (row.get("concept_set_name") or "").strip() or concept_set_name.strip()
            if not row_set_name:
                raise ValueError(f"row {row_number}: concept_set_name is required for a selected concept")
            concept_sets_by_key.setdefault((row_set_name, domain), []).append(item)
            policy = "Exclude" if exclude else "Include"
            policy += " + descendants" if item["include_descendants"] else ""
            policy += " + mapped" if item["include_mapped"] else ""
            approval_preview.append({
                "concept_set_name": row_set_name,
                "concept_id": concept_id,
                "concept_name": row.get("concept_name") or "",
                "domain": domain,
                "standard_concept": row.get("standard_concept") or "",
                "standard_concept_status": row.get("standard_concept_status") or "Unknown",
                "policy": policy,
                "assessment_status": row.get("assessment_status") or "",
                "precision_eligible": row.get("precision_eligible") or "",
                "relationship_evidence": row.get("relationship_evidence") or "",
            })
            if include and (row.get("assessment_status") or "").strip() == "not_assessed_retrieval_context":
                unassessed_includes.append({
                    "concept_id": concept_id,
                    "concept_name": row.get("concept_name") or "",
                    "relationship_evidence": row.get("relationship_evidence") or "",
                })

    concept_sets = [
        {"name": name, "domain": domain, "items": items}
        for (name, domain), items in concept_sets_by_key.items()
    ]
    return {
        "manifest": manifest,
        "review_summary": {
            "selected_item_count": sum(len(items) for items in concept_sets_by_key.values()),
            "selected_concept_set_count": len(concept_sets),
            "unassessed_manually_included": unassessed_includes,
        },
        "approval_preview": approval_preview,
        "concept_sets": concept_sets,
    }


def write_approval_artifacts(result: dict[str, Any], approval_json: Path, approval_csv: Path) -> dict[str, Any]:
    """Write the exact policy object and a human-readable preview for approval."""
    payload = {"concept_sets": result["concept_sets"]}
    encoded = (json.dumps(payload, indent=2, sort_keys=True) + "\n").encode("utf-8")
    approval_json.write_bytes(encoded)
    preview = result["approval_preview"]
    fields = ["concept_set_name", "concept_id", "concept_name", "domain", "standard_concept", "standard_concept_status", "policy", "assessment_status", "precision_eligible", "relationship_evidence"]
    with approval_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(preview)
    return {"approval_json": str(approval_json), "approval_csv": str(approval_csv), "sha256": hashlib.sha256(encoded).hexdigest(), "selected_item_count": result["review_summary"]["selected_item_count"]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--concept-set-name", default="", help="Fallback name for selected rows with no concept_set_name")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--approval-json", type=Path, help="Write exact policy-bearing concept_sets JSON")
    parser.add_argument("--approval-csv", type=Path, help="Write a human-readable approval preview CSV")
    args = parser.parse_args()
    if bool(args.approval_json) != bool(args.approval_csv):
        parser.error("--approval-json and --approval-csv must be provided together")
    try:
        result = parse_review_csv(args.csv, args.concept_set_name, args.manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    if args.approval_json:
        result["approval_artifacts"] = write_approval_artifacts(result, args.approval_json, args.approval_csv)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
