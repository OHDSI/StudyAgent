#!/usr/bin/env python3
"""Validate an edited phenotype review CSV and emit review-gated concept sets."""

from __future__ import annotations

import argparse
import csv
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


def parse_review_csv(csv_path: Path, concept_set_name: str, manifest_path: Path | None = None) -> dict[str, Any]:
    if not concept_set_name.strip():
        raise ValueError("concept_set_name is required")
    manifest: dict[str, Any] = {}
    if manifest_path is not None:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("schema_version") != 1:
            raise ValueError("unsupported_review_manifest_schema")

    items: list[dict[str, Any]] = []
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
            items.append(item)
            policy = "Exclude" if exclude else "Include"
            policy += " + descendants" if item["include_descendants"] else ""
            policy += " + mapped" if item["include_mapped"] else ""
            approval_preview.append({
                "concept_id": concept_id,
                "concept_name": row.get("concept_name") or "",
                "domain": domain,
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

    selected_domains = {item["domain"] for item in items}
    if len(selected_domains) > 1:
        raise ValueError("selected_review_rows_span_multiple_domains; split the review or provide an explicit multi-domain policy")
    domain = next(iter(selected_domains), "")
    return {
        "manifest": manifest,
        "review_summary": {
            "selected_item_count": len(items),
            "unassessed_manually_included": unassessed_includes,
        },
        "approval_preview": approval_preview,
        "concept_sets": ([{"name": concept_set_name.strip(), "domain": domain, "items": items}] if items else []),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--concept-set-name", required=True)
    parser.add_argument("--manifest", type=Path)
    args = parser.parse_args()
    try:
        result = parse_review_csv(args.csv, args.concept_set_name, args.manifest)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
