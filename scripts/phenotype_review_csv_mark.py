#!/usr/bin/env python3
"""Apply explicit bulk review marks to a phenotype review CSV safely."""
from __future__ import annotations
import argparse
import csv
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--include-all", action="store_true")
    parser.add_argument("--include-concept", action="append", default=[])
    parser.add_argument("--include-descendants", action="append", default=[])
    args = parser.parse_args()
    selected = {int(value) for value in args.include_concept}
    descendants = {int(value) for value in args.include_descendants}
    if descendants - selected and not args.include_all:
        parser.error("--include-descendants requires the same --include-concept ID")
    with args.csv.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not reader.fieldnames:
            parser.error("review_csv_has_no_header")
        fields = reader.fieldnames
        required = {"concept_id", "review_include_concept", "review_include_descendants"}
        if not required.issubset(fields):
            parser.error("review_csv_missing_required_review_columns")
        rows = list(reader)
    for row in rows:
        concept_id = int(row["concept_id"])
        if args.include_all or concept_id in selected:
            row["review_include_concept"] = "x"
        if concept_id in descendants:
            row["review_include_descendants"] = "x"
    with args.output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
