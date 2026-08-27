#!/usr/bin/env python3
"""Normalize user-supplied Atlas concept-set JSON or concept IDs for ACP review."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _positive_id(value: Any) -> int:
    try:
        concept_id = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid_concept_id:{value}") from exc
    if concept_id <= 0:
        raise ValueError(f"invalid_concept_id:{value}")
    return concept_id


def _atlas_item(item: dict[str, Any], domain: str) -> dict[str, Any]:
    concept = item.get("concept") or {}
    if not isinstance(concept, dict):
        raise ValueError("atlas_item_missing_concept")
    item_domain = str(concept.get("DOMAIN_ID") or concept.get("domainId") or domain or "").strip()
    if not item_domain:
        raise ValueError("domain_required_for_atlas_item")
    if domain and item_domain != domain:
        raise ValueError("atlas_item_domain_mismatch")
    return {
        "concept_id": _positive_id(concept.get("CONCEPT_ID", concept.get("conceptId"))),
        "domain": item_domain,
        "include_descendants": bool(item.get("includeDescendants", False)),
        "include_mapped": bool(item.get("includeMapped", False)),
        "is_excluded": bool(item.get("isExcluded", False)),
    }


def parse_atlas_json(path: Path, name: str = "", domain: str = "") -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("atlas_json_must_be_object")
    expression = payload.get("expression") or payload.get("Expression") or payload
    items = expression.get("items") if isinstance(expression, dict) else None
    if not isinstance(items, list) or not items:
        raise ValueError("atlas_json_missing_expression_items")
    set_name = str(name or payload.get("name") or payload.get("Name") or "").strip()
    if not set_name:
        raise ValueError("concept_set_name_required")
    normalized = [_atlas_item(item, domain) for item in items if isinstance(item, dict)]
    if len(normalized) != len(items):
        raise ValueError("atlas_json_item_must_be_object")
    domains = {item["domain"] for item in normalized}
    if len(domains) != 1:
        raise ValueError("atlas_json_mixed_domains_require_separate_sets")
    return {"concept_sets": [{"name": set_name, "domain": normalized[0]["domain"], "items": normalized}], "source": "atlas_json"}


def parse_concept_ids(values: list[str], name: str, domain: str) -> dict[str, Any]:
    if not name.strip() or not domain.strip():
        raise ValueError("concept_set_name_and_domain_required_for_concept_ids")
    tokens = [token.strip() for value in values for token in value.split(",") if token.strip()]
    if not tokens:
        raise ValueError("concept_ids_required")
    concept_ids = []
    seen: set[int] = set()
    for token in tokens:
        concept_id = _positive_id(token)
        if concept_id not in seen:
            seen.add(concept_id)
            concept_ids.append(concept_id)
    return {"concept_sets": [{"name": name.strip(), "domain": domain.strip(), "concept_ids": concept_ids}], "source": "concept_ids"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--atlas-json", type=Path)
    source.add_argument("--concept-ids", action="append", default=[])
    source.add_argument("--concept-ids-file", type=Path)
    parser.add_argument("--concept-set-name", default="")
    parser.add_argument("--domain", default="")
    args = parser.parse_args()
    try:
        if args.atlas_json:
            result = parse_atlas_json(args.atlas_json, args.concept_set_name, args.domain)
        else:
            values = list(args.concept_ids)
            if args.concept_ids_file:
                values.append(args.concept_ids_file.read_text(encoding="utf-8").replace("\n", ","))
            result = parse_concept_ids(values, args.concept_set_name, args.domain)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
