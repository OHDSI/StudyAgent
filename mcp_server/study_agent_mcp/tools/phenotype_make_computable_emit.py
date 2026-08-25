from __future__ import annotations

from typing import Any, Dict, List

from ._common import with_meta

ENTRY_POINT = "phenotype_make_computable_definition"


def _r_string(value: Any) -> str:
    return str(value or "").replace('"', "'")


def _member_domains(item: Dict[str, Any]) -> set[str]:
    rows = item.get("items") or item.get("concepts") or []
    return {str(row.get("domain") or row.get("domainId")) for row in rows if isinstance(row, dict) and (row.get("domain") or row.get("domainId"))}


def _concept_set_expression(item: Dict[str, Any]) -> tuple[str | None, str | None]:
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
            expression = f"Capr::descendants({expression})"
        if mapped:
            expression = f"Capr::mapped({expression})"
        if excluded:
            expression = f"Capr::exclude({expression})"
        terms.append(expression)
    return ", ".join(terms), None


def _era_days(scope: Dict[str, Any]) -> tuple[int | None, str | None]:
    try:
        value = int(scope.get("era_days", 0))
    except (TypeError, ValueError):
        return None, "era_days_must_be_an_integer"
    return (value, None) if value >= 0 else (None, "era_days_must_be_nonnegative")


def _prior_observation_days(scope: Dict[str, Any], default: int = 0) -> tuple[int | None, str | None]:
    value = scope.get("prior_observation", default)
    if isinstance(value, dict):
        value = value.get("days", default)
    try:
        days = int(value)
    except (TypeError, ValueError):
        return None, "prior_observation_must_be_nonnegative_integer_days"
    return (days, None) if days >= 0 else (None, "prior_observation_must_be_nonnegative_integer_days")

def _function_source(scope_comment: str, body: str) -> str:
    indented = "\n".join(f"  {line}" if line else "" for line in body.splitlines())
    return f'''# Scope check: {scope_comment}
# This file is pure: sourcing it creates no files or cohort definitions.
{ENTRY_POINT} <- function() {{
{indented}
}}
'''


def emit_capr(scope: Dict[str, Any], concept_sets: List[Dict[str, Any]]) -> Dict[str, Any]:
    temporal = scope.get("temporal_followup") or {}
    if temporal:
        index_name, trigger_name = temporal.get("index_concept_set"), temporal.get("trigger_concept_set")
        by_name = {row.get("name"): row for row in concept_sets}
        index_set, trigger_set = by_name.get(index_name), by_name.get(trigger_name)
        if len(concept_sets) != 2 or not index_set or not trigger_set or str(index_set.get("domain")) != "Condition" or str(trigger_set.get("domain")) != "Condition":
            return {"status": "failed", "messages": ["temporal_followup_requires_two_named_condition_concept_sets"]}
        index_expression, index_error = _concept_set_expression(index_set)
        trigger_expression, trigger_error = _concept_set_expression(trigger_set)
        if index_error or trigger_error:
            return {"status": "failed", "messages": [index_error or trigger_error]}
        followup_days, washout_days = int(temporal.get("followup_days", 30)), int(temporal.get("washout_days", 365))
        if followup_days < 0 or washout_days < 1:
            return {"status": "failed", "messages": ["temporal_followup_days_invalid"]}
        prior_days, prior_error = _prior_observation_days(scope, default=washout_days)
        if prior_error:
            return {"status": "failed", "messages": [prior_error]}
        if prior_days != washout_days:
            return {"status": "failed", "messages": ["temporal_followup_prior_observation_must_equal_washout_days"]}
        limit = str(scope.get("entry_limit") or "All")
        if limit not in {"First", "All"}:
            return {"status": "failed", "messages": ["unsupported_entry_limit"]}
        iname, tname = _r_string(index_name), _r_string(trigger_name)
        qualified_trigger = f"Capr::conditionOccurrence(triggerCs, Capr::nestedWithAll(Capr::atLeast(1L, Capr::conditionOccurrence(indexCs), aperture = Capr::duringInterval(startWindow = Capr::eventStarts(0, {followup_days}, index = 'startDate')))))"
        body = f'''indexCs <- Capr::cs({index_expression}, name = "{iname}")
triggerCs <- Capr::cs({trigger_expression}, name = "{tname}")
qualifiedTrigger <- {qualified_trigger}
Capr::cohort(
  entry = Capr::entry(Capr::conditionOccurrence(indexCs), qualifiedTrigger, observationWindow = Capr::continuousObservation({washout_days}L, 0L), primaryCriteriaLimit = "{limit}"),
  attrition = Capr::attrition("No qualifying event in clean window" = Capr::withAll(
    Capr::exactly(0L, Capr::conditionOccurrence(indexCs), aperture = Capr::duringInterval(startWindow = Capr::eventStarts(-{washout_days}, -1, index = "startDate"))),
    Capr::exactly(0L, qualifiedTrigger, aperture = Capr::duringInterval(startWindow = Capr::eventStarts(-{washout_days}, -1, index = "startDate")))
  ), expressionLimit = "{limit}"),
  exit = Capr::exit(endStrategy = Capr::fixedExit(index = "startDate", offsetDays = 1L)), era = Capr::era(eraDays = 0L)
)'''
        comment = f"index paths: {iname} OR {tname} followed by {iname} within {followup_days} days; continuous observation and clean window: {washout_days} days; exit=startDate+1"
        return {"status": "passed", "capr_code": _function_source(comment, body), "entry_point": ENTRY_POINT, "messages": []}
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
        overlap_mode = str(scope.get("visit_overlap_mode") or "attrition")
        if limit not in {"First", "All"} or not isinstance(exit_strategy, dict) or exit_strategy.get("type") != "fixed" or overlap_mode not in {"entry", "attrition"}:
            return {"status": "failed", "messages": ["visit_overlap_requires_supported_limit_mode_and_fixed_exit"]}
        offset = int(exit_strategy.get("offset_days", 0))
        exit_index = str(exit_strategy.get("index") or "endDate")
        if exit_index not in {"startDate", "endDate"}:
            return {"status": "failed", "messages": ["unsupported_fixed_exit_index"]}
        cn, vn = _r_string(condition.get("name") or "Entry"), _r_string(visit_set.get("name") or "Visit")
        prior_days, prior_error = _prior_observation_days(scope)
        if prior_error:
            return {"status": "failed", "messages": [prior_error]}
        visit_group = "Capr::atLeast(1L, Capr::visit(visitCs), Capr::duringInterval(startWindow = Capr::eventStarts(-Inf, 0), endWindow = Capr::eventEnds(0, Inf)))"
        entry_query = f"Capr::conditionOccurrence(entryCs, Capr::nestedWithAll({visit_group}))" if overlap_mode == "entry" else "Capr::conditionOccurrence(entryCs)"
        attrition = f'Capr::attrition(expressionLimit = "{limit}")' if overlap_mode == "entry" else f'Capr::attrition("Visit overlaps index" = Capr::withAll({visit_group}), expressionLimit = "{limit}")'
        body = f'''entryCs <- Capr::cs({condition_expression}, name = "{cn}")
visitCs <- Capr::cs({visit_expression}, name = "{vn}")
Capr::cohort(
  entry = Capr::entry({entry_query}, observationWindow = Capr::continuousObservation({prior_days}L, 0L), primaryCriteriaLimit = "{limit}"),
  attrition = {attrition},
  exit = Capr::exit(endStrategy = Capr::fixedExit(index = "{exit_index}", offsetDays = {offset}L)), era = Capr::era(eraDays = 0L)
)'''
        return {"status": "passed", "capr_code": _function_source(f"index={scope.get('index_event', '')}; condition overlaps visit in {overlap_mode}; limit={limit}; fixed_exit={exit_index}+{offset}", body), "entry_point": ENTRY_POINT, "messages": []}
    if len(concept_sets) != 1:
        return {"status": "failed", "messages": ["v1_emitter_requires_exactly_one_concept_set"]}
    item = concept_sets[0]
    if str(item.get("domain") or item.get("domainId") or "") != "Condition":
        return {"status": "failed", "messages": ["v1_emitter_supports_condition_entry_only"]}
    if len(_member_domains(item)) > 1:
        return {"status": "failed", "messages": ["mixed_domain_concept_set_requires_explicit_multi_domain_plan"]}
    expression, error = _concept_set_expression(item)
    era_days, era_error = _era_days(scope)
    prior_days, prior_error = _prior_observation_days(scope)
    if error or era_error or prior_error:
        return {"status": "failed", "messages": [error or era_error or prior_error]}
    if error or era_error:
        return {"status": "failed", "messages": [error or era_error]}
    limit = str(scope.get("entry_limit") or "First")
    if limit not in {"First", "All"}:
        return {"status": "failed", "messages": ["unsupported_entry_limit"]}
    exit_strategy = scope.get("exit_strategy") or "observation"
    if isinstance(exit_strategy, dict) and exit_strategy.get("type") == "fixed":
        exit_index = str(exit_strategy.get("index") or "endDate")
        if exit_index not in {"startDate", "endDate"}:
            return {"status": "failed", "messages": ["unsupported_fixed_exit_index"]}
        exit_code = f'Capr::fixedExit(index = "{exit_index}", offsetDays = {int(exit_strategy.get("offset_days", 0))}L)'
    elif exit_strategy in {"observation", "end_of_observation"}:
        exit_code = "Capr::observationExit()"
    else:
        return {"status": "failed", "messages": ["unsupported_exit_strategy"]}
    name = _r_string(item.get("name") or "Entry concept set")
    body = f'''entryCs <- Capr::cs({expression}, name = "{name}")
Capr::cohort(
  entry = Capr::entry(Capr::conditionOccurrence(entryCs), observationWindow = Capr::continuousObservation({prior_days}L, 0L), primaryCriteriaLimit = "{limit}"),
  attrition = Capr::attrition(expressionLimit = "{limit}"),
  exit = Capr::exit(endStrategy = {exit_code}), era = Capr::era(eraDays = {era_days}L)
)'''
    comment = f"index={scope.get('index_event', '')}; domain=conditionOccurrence; limit={limit}; exit={exit_strategy}; era_days={era_days}"
    return {"status": "passed", "capr_code": _function_source(comment, body), "entry_point": ENTRY_POINT, "messages": []}


def register(mcp: object) -> None:
    @mcp.tool(name="phenotype_make_computable_emit")
    def phenotype_make_computable_emit_tool(scope: Dict[str, Any], concept_sets: List[Dict[str, Any]]) -> Dict[str, Any]:
        return with_meta(emit_capr(scope, concept_sets), "phenotype_make_computable_emit")
