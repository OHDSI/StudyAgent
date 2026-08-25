from __future__ import annotations

from typing import Any, Dict, List

from ._common import with_meta


def _r_string(value: Any) -> str:
    return str(value or "").replace('"', "'")


def _member_domains(item: Dict[str, Any]) -> set[str]:
    rows = item.get("items") or item.get("concepts") or []
    return {str(row.get("domain") or row.get("domainId")) for row in rows if isinstance(row, dict) and (row.get("domain") or row.get("domainId"))}


def _concept_set_expression(item: Dict[str, Any]) -> tuple[str | None, str | None]:
    """Render a Capr cs() argument list while preserving per-concept policy."""
    supplied_items = item.get("items") or item.get("concepts") or []
    normalized: list[tuple[int, bool, bool, bool]] = []
    if supplied_items:
        for row in supplied_items:
            if not isinstance(row, dict):
                return None, "concept_set_items_must_be_objects"
            value = row.get("concept_id", row.get("conceptId"))
            if not isinstance(value, int):
                return None, "concept_ids_must_be_nonempty_integers"
            normalized.append((value, bool(row.get("is_excluded", row.get("isExcluded", False))), bool(row.get("include_descendants", row.get("includeDescendants", False))), bool(row.get("include_mapped", row.get("includeMapped", False)))))
    else:
        ids = item.get("concept_ids") or item.get("conceptIds") or []
        if not ids or any(not isinstance(value, int) for value in ids):
            return None, "concept_ids_must_be_nonempty_integers"
        normalized = [(value, False, False, False) for value in ids]
    grouped: dict[tuple[bool, bool, bool], list[int]] = {}
    for value, excluded, descendants, mapped in normalized:
        grouped.setdefault((excluded, descendants, mapped), []).append(value)
    terms = []
    for (excluded, descendants, mapped), values in grouped.items():
        expression = ", ".join(f"{value}L" for value in values)
        if descendants:
            expression = f"descendants({expression})"
        if mapped:
            expression = f"mapped({expression})"
        if excluded:
            expression = f"exclude({expression})"
        terms.append(expression)
    return ", ".join(terms), None


def _era_days(scope: Dict[str, Any]) -> tuple[int | None, str | None]:
    try:
        value = int(scope.get("era_days", 0))
    except (TypeError, ValueError):
        return None, "era_days_must_be_an_integer"
    return (value, None) if value >= 0 else (None, "era_days_must_be_nonnegative")


def emit_capr(scope: Dict[str, Any], concept_sets: List[Dict[str, Any]]) -> Dict[str, Any]:
    if scope.get("visit_overlap"):
        by_domain = {str(row.get("domain") or row.get("domainId") or ""): row for row in concept_sets}
        condition, visit_set = by_domain.get("Condition"), by_domain.get("Visit")
        if len(concept_sets) != 2 or not condition or not visit_set:
            return {"status": "failed", "messages": ["visit_overlap_requires_condition_and_visit_concept_sets"]}
        condition_expression, condition_error = _concept_set_expression(condition)
        visit_expression, visit_error = _concept_set_expression(visit_set)
        if condition_error or visit_error:
            return {"status": "failed", "messages": [condition_error or visit_error]}
        limit = str(scope.get("entry_limit") or "All")
        exit_strategy = scope.get("exit_strategy") or {}
        if limit not in {"First", "All"} or not isinstance(exit_strategy, dict) or exit_strategy.get("type") != "fixed":
            return {"status": "failed", "messages": ["visit_overlap_requires_supported_limit_and_fixed_exit"]}
        offset = int(exit_strategy.get("offset_days", 0))
        cn, vn = _r_string(condition.get("name") or "Entry"), _r_string(visit_set.get("name") or "Visit")
        code = f'''library(Capr)
entryCs <- cs({condition_expression}, name = "{cn}")
visitCs <- cs({visit_expression}, name = "{vn}")
cohortDef <- cohort(
  entry = entry(conditionOccurrence(entryCs), observationWindow = continuousObservation(0L, 0L), primaryCriteriaLimit = "{limit}"),
  attrition = attrition("Visit overlaps index" = withAll(atLeast(1L, visit(visitCs), duringInterval(startWindow = eventStarts(-Inf, 0), endWindow = eventEnds(0, Inf)))), expressionLimit = "{limit}"),
  exit = exit(endStrategy = fixedExit(index = "endDate", offsetDays = {offset}L)), era = era(eraDays = 0L)
)
writeCohort(cohortDef, "cohort.json")
'''
        return {"status": "passed", "capr_code": code, "messages": []}
    if len(concept_sets) != 1:
        return {"status": "failed", "messages": ["v1_emitter_requires_exactly_one_concept_set"]}
    item = concept_sets[0]
    if str(item.get("domain") or item.get("domainId") or "") != "Condition":
        return {"status": "failed", "messages": ["v1_emitter_supports_condition_entry_only"]}
    if len(_member_domains(item)) > 1:
        return {"status": "failed", "messages": ["mixed_domain_concept_set_requires_explicit_multi_domain_plan"]}
    expression, error = _concept_set_expression(item)
    era_days, era_error = _era_days(scope)
    if error or era_error:
        return {"status": "failed", "messages": [error or era_error]}
    limit = str(scope.get("entry_limit") or "First")
    if limit not in {"First", "All"}:
        return {"status": "failed", "messages": ["unsupported_entry_limit"]}
    exit_strategy = scope.get("exit_strategy") or "observation"
    if isinstance(exit_strategy, dict) and exit_strategy.get("type") == "fixed":
        exit_code = f'fixedExit(index = "endDate", offsetDays = {int(exit_strategy.get("offset_days", 0))}L)'
    elif exit_strategy in {"observation", "end_of_observation"}:
        exit_code = "observationExit()"
    else:
        return {"status": "failed", "messages": ["unsupported_exit_strategy"]}
    name = _r_string(item.get("name") or "Entry concept set")
    code = f'''library(Capr)
# Scope check: index={scope.get("index_event", "")}; domain=conditionOccurrence; limit={limit}; exit={exit_strategy}; era_days={era_days}
entryCs <- cs({expression}, name = "{name}")
cohortDef <- cohort(
  entry = entry(conditionOccurrence(entryCs), observationWindow = continuousObservation(0L, 0L), primaryCriteriaLimit = "{limit}"),
  attrition = attrition(expressionLimit = "{limit}"),
  exit = exit(endStrategy = {exit_code}), era = era(eraDays = {era_days}L)
)
writeCohort(cohortDef, "cohort.json")
'''
    return {"status": "passed", "capr_code": code, "messages": []}


def register(mcp: object) -> None:
    @mcp.tool(name="phenotype_make_computable_emit")
    def phenotype_make_computable_emit_tool(scope: Dict[str, Any], concept_sets: List[Dict[str, Any]]) -> Dict[str, Any]:
        return with_meta(emit_capr(scope, concept_sets), "phenotype_make_computable_emit")
