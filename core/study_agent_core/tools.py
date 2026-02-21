import json
from typing import Any, Dict, List, Optional, Tuple

from .models import (
    CohortLintInput,
    CohortLintOutput,
    ConceptSetDiffInput,
    ConceptSetDiffOutput,
    PhenotypeImprovementsInput,
    PhenotypeImprovementsOutput,
    PhenotypeRecommendationAdviceInput,
    PhenotypeRecommendationAdviceOutput,
    PhenotypeRecommendationsInput,
    PhenotypeRecommendationsOutput,
)


def _model_dump(model):
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _truncate_text(text: str, limit: int) -> str:
    if not isinstance(text, str):
        return ""
    if limit and len(text) > limit:
        return text[:limit] + f"... [truncated {len(text) - limit} chars]"
    return text


def canonicalize_concept_items(concept_set: Any) -> Tuple[List[Dict[str, Any]], List[Any]]:
    src_items: List[Any]
    if isinstance(concept_set, dict):
        if "items" in concept_set:
            src_items = concept_set.get("items") or []
        elif isinstance(concept_set.get("expression"), dict) and "items" in concept_set["expression"]:
            src_items = concept_set["expression"].get("items") or []
        else:
            src_items = []
    elif isinstance(concept_set, list):
        src_items = concept_set
    else:
        src_items = []

    items = []
    for it in src_items:
        if not isinstance(it, dict):
            continue
        concept = it.get("concept") or {}
        items.append(
            {
                "conceptId": concept.get("conceptId") or concept.get("CONCEPT_ID"),
                "domainId": concept.get("domainId") or concept.get("DOMAIN_ID"),
                "conceptClassId": concept.get("conceptClassId") or concept.get("CONCEPT_CLASS_ID"),
                "includeDescendants": it.get("includeDescendants"),
                "raw": it,
            }
        )
    return items, src_items


def apply_set_include_descendants(
    concept_set: Any,
    where: Dict[str, Any],
    value: bool = True,
) -> Tuple[Any, List[Dict[str, Any]]]:
    cs_copy = json.loads(json.dumps(concept_set))
    items, src_items = canonicalize_concept_items(cs_copy)
    preview = []
    for idx, info in enumerate(items):
        if info.get("conceptId") is None:
            continue
        if where.get("domainId") and info.get("domainId") != where["domainId"]:
            continue
        if where.get("conceptClassId") and info.get("conceptClassId") != where["conceptClassId"]:
            continue
        if where.get("includeDescendants") is not None:
            inc = bool(info.get("includeDescendants") or False)
            if inc != bool(where["includeDescendants"]):
                continue
        preview.append(
            {
                "conceptId": info["conceptId"],
                "from": {"includeDescendants": bool(info.get("includeDescendants") or False)},
                "to": {"includeDescendants": bool(value)},
            }
        )
        raw_item = src_items[idx]
        if isinstance(raw_item, dict):
            raw_item["includeDescendants"] = bool(value)
    return cs_copy, preview


def _filter_catalog_recs(
    recs: List[Dict[str, Any]],
    catalog_rows: List[Dict[str, Any]],
    max_results: int,
) -> List[Dict[str, Any]]:
    allowed = {r.get("cohortId"): r for r in catalog_rows if r.get("cohortId") is not None}
    cleaned = []
    for rec in recs or []:
        cid = rec.get("cohortId")
        if cid not in allowed:
            continue
        info = allowed[cid]
        cleaned.append(
            {
                "cohortId": cid,
                "cohortName": rec.get("cohortName") or info.get("cohortName") or "",
                "justification": rec.get("justification") or "Model justification not provided.",
                "confidence": rec.get("confidence"),
            }
        )
        if len(cleaned) >= max_results:
            break
    return cleaned


def propose_concept_set_diff(
    concept_set: Any,
    study_intent: str = "",
    llm_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = ConceptSetDiffInput(concept_set=concept_set, study_intent=study_intent, llm_result=llm_result)

    items, _src = canonicalize_concept_items(payload.concept_set)
    findings: List[Dict[str, Any]] = []
    patches: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    risk_notes: List[Dict[str, Any]] = []

    plan = (
        "Review concept set for gaps and inconsistencies given the study intent: "
        f"{_truncate_text(payload.study_intent, 160)}..."
    )

    concept_ids = [x.get("conceptId") for x in items if x.get("conceptId") is not None]
    duplicates = [cid for cid in concept_ids if concept_ids.count(cid) > 1]
    if len(items) == 0:
        findings.append(
            {
                "id": "empty_concept_set",
                "severity": "high",
                "impact": "design",
                "message": "Concept set is empty.",
            }
        )
    if duplicates:
        findings.append(
            {
                "id": "duplicate_concepts",
                "severity": "medium",
                "impact": "design",
                "message": f"Duplicate conceptIds: {sorted(set(duplicates))}",
            }
        )

    domains = {x.get("domainId") for x in items if x.get("domainId")}
    if len(domains) > 1:
        findings.append(
            {
                "id": "mixed_domains",
                "severity": "low",
                "impact": "portability",
                "message": f"Multiple domains detected: {sorted(domains)}",
            }
        )

    no_desc = [
        it
        for it in items
        if (it.get("domainId") or "").lower() == "drug"
        and (it.get("conceptClassId") or "").lower() == "ingredient"
        and not bool(it.get("includeDescendants") or False)
    ]
    if no_desc:
        findings.append(
            {
                "id": "suggest_descendants_concept_set",
                "severity": "medium",
                "impact": "design",
                "message": "Drug ingredient concepts missing includeDescendants; consider enabling for coverage.",
            }
        )
        actions.append(
            {
                "type": "set_include_descendants",
                "where": {"domainId": "Drug", "conceptClassId": "Ingredient", "includeDescendants": False},
                "value": True,
            }
        )

    if payload.llm_result:
        for f in payload.llm_result.get("findings", []):
            if f not in findings:
                findings.append(f)
        for p in payload.llm_result.get("patches", []):
            if p not in patches:
                patches.append(p)
        if isinstance(payload.llm_result.get("actions"), list):
            actions = payload.llm_result["actions"]
        if payload.llm_result.get("plan"):
            plan = payload.llm_result["plan"]

    output = ConceptSetDiffOutput(
        plan=plan,
        findings=findings,
        patches=patches,
        actions=actions,
        risk_notes=risk_notes,
    )
    return _model_dump(output)


def cohort_lint(
    cohort: Dict[str, Any],
    llm_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = CohortLintInput(cohort=cohort, llm_result=llm_result)

    plan = "Review cohort JSON for general design issues (washout/time-at-risk, inverted windows, empty or conflicting criteria)."
    findings: List[Dict[str, Any]] = []
    patches: List[Dict[str, Any]] = []
    actions: List[Dict[str, Any]] = []
    risk_notes: List[Dict[str, Any]] = []

    pc = payload.cohort.get("PrimaryCriteria", {}) if isinstance(payload.cohort, dict) else {}
    washout = pc.get("ObservationWindow", {}) if isinstance(pc, dict) else {}

    if not washout or washout.get("PriorDays") in (None, 0):
        findings.append(
            {
                "id": "missing_washout",
                "severity": "medium",
                "impact": "validity",
                "message": "No or zero-day washout; consider >= 365 days.",
            }
        )
        patches.append(
            {
                "type": "jsonpatch",
                "ops": [
                    {
                        "op": "note",
                        "path": "/PrimaryCriteria/ObservationWindow",
                        "value": {"ProposedPriorDays": 365},
                    }
                ],
            }
        )

    irules = payload.cohort.get("InclusionRules", []) if isinstance(payload.cohort, dict) else []
    for i, rule in enumerate(irules):
        if not isinstance(rule, dict):
            continue
        window = rule.get("window", {}) if isinstance(rule, dict) else {}
        start = window.get("start", 0)
        end = window.get("end", 0)
        if window and isinstance(start, (int, float)) and isinstance(end, (int, float)) and start > end:
            findings.append(
                {
                    "id": f"inverted_window_{i}",
                    "severity": "high",
                    "impact": "validity",
                    "message": f"InclusionRule[{i}] has inverted window (start > end).",
                }
            )

    if payload.llm_result:
        for f in payload.llm_result.get("findings", []):
            if f not in findings:
                findings.append(f)
        for p in payload.llm_result.get("patches", []):
            if p not in patches:
                patches.append(p)
        if isinstance(payload.llm_result.get("actions"), list):
            actions = payload.llm_result["actions"]
        if payload.llm_result.get("plan"):
            plan = payload.llm_result["plan"]

    output = CohortLintOutput(
        plan=plan,
        findings=findings,
        patches=patches,
        actions=actions,
        risk_notes=risk_notes,
    )
    return _model_dump(output)


def phenotype_recommendations(
    protocol_text: str,
    catalog_rows: List[Dict[str, Any]],
    max_results: int = 5,
    llm_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = PhenotypeRecommendationsInput(
        protocol_text=protocol_text,
        catalog_rows=catalog_rows,
        max_results=max_results,
        llm_result=llm_result,
    )

    allowed_ids = [r.get("cohortId") for r in payload.catalog_rows if r.get("cohortId") is not None]
    allowed_set = {cid for cid in allowed_ids}
    max_results = max(0, min(payload.max_results, len(allowed_ids)))

    plan = "Suggest relevant phenotypes from catalog for the study intent (stub if no LLM)."
    recs: List[Dict[str, Any]] = []
    invalid_ids: List[int] = []
    mode = "llm"

    if payload.llm_result and isinstance(payload.llm_result.get("phenotype_recommendations"), list):
        raw_recs = payload.llm_result.get("phenotype_recommendations") or []
        invalid_ids = sorted(
            {
                rec.get("cohortId")
                for rec in raw_recs
                if rec.get("cohortId") not in allowed_set and rec.get("cohortId") is not None
            }
        )
        recs = _filter_catalog_recs(raw_recs, payload.catalog_rows, max_results)
        if payload.llm_result.get("plan"):
            plan = payload.llm_result["plan"]
    else:
        mode = "stub"
        for row in payload.catalog_rows[:max_results]:
            recs.append(
                {
                    "cohortId": row.get("cohortId"),
                    "cohortName": row.get("cohortName") or row.get("name") or "",
                    "justification": "Stub recommendation from deterministic fallback (no LLM).",
                    "confidence": None,
                }
            )

    output = PhenotypeRecommendationsOutput(
        plan=plan,
        phenotype_recommendations=recs,
        mode=mode,
        catalog_stats={
            "total_rows": len(payload.catalog_rows),
            "preview_rows": min(len(payload.catalog_rows), max_results),
            "allowed_ids": len(allowed_ids),
        },
        invalid_ids_filtered=invalid_ids,
    )
    return _model_dump(output)


def phenotype_improvements(
    protocol_text: str,
    cohorts: List[Dict[str, Any]],
    characterization_previews: Optional[List[Dict[str, Any]]] = None,
    llm_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = PhenotypeImprovementsInput(
        protocol_text=protocol_text,
        cohorts=cohorts,
        characterization_previews=characterization_previews or [],
        llm_result=llm_result,
    )

    allowed_ids = []
    for cohort in payload.cohorts:
        if not isinstance(cohort, dict):
            continue
        cid = cohort.get("id")
        if isinstance(cid, (int, float)):
            allowed_ids.append(int(cid))
    allowed_ids = sorted(set(allowed_ids))
    if not allowed_ids:
        return {
            "error": "No cohortIds found; include an 'id' field in each cohort object.",
        }

    plan = "Review selected phenotypes for improvements against study intent (stub if no LLM)."
    improvements: List[Dict[str, Any]] = []
    code_suggestion = None
    invalid_targets: List[int] = []
    mode = "llm"

    if payload.llm_result:
        raw_improvements = payload.llm_result.get("phenotype_improvements") or []
        if len(allowed_ids) == 1:
            only_id = allowed_ids[0]
            for imp in raw_improvements:
                if not isinstance(imp, dict):
                    continue
                target_id = imp.get("targetCohortId")
                if target_id is not None and target_id != only_id:
                    imp["targetCohortId"] = only_id
        invalid_targets = sorted(
            {
                imp.get("targetCohortId")
                for imp in raw_improvements
                if imp.get("targetCohortId") not in allowed_ids and imp.get("targetCohortId") is not None
            }
        )
        improvements = [imp for imp in raw_improvements if imp.get("targetCohortId") in allowed_ids]
        code_suggestion = payload.llm_result.get("code_suggestion")
        if payload.llm_result.get("plan"):
            plan = payload.llm_result["plan"]
    else:
        mode = "stub"
        improvements = []

    output = PhenotypeImprovementsOutput(
        plan=plan,
        phenotype_improvements=improvements,
        code_suggestion=code_suggestion,
        mode=mode,
        invalid_targets_filtered=invalid_targets,
    )
    return _model_dump(output)


def phenotype_recommendation_advice(
    study_intent: str,
    llm_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload = PhenotypeRecommendationAdviceInput(
        study_intent=study_intent,
        llm_result=llm_result,
    )

    plan = "Provide next-step guidance when phenotype recommendations are insufficient."
    advice = ""
    next_steps: List[str] = []
    questions: List[str] = []
    mode = "llm"

    if payload.llm_result:
        if payload.llm_result.get("plan"):
            plan = payload.llm_result["plan"]
        advice = payload.llm_result.get("advice") or ""
        if isinstance(payload.llm_result.get("next_steps"), list):
            next_steps = [str(s) for s in payload.llm_result["next_steps"]]
        if isinstance(payload.llm_result.get("questions"), list):
            questions = [str(s) for s in payload.llm_result["questions"]]
    else:
        mode = "stub"
        advice = "No LLM response available. Refine the study intent and retry phenotype recommendations."
        next_steps = [
            "Clarify the population and outcome definitions in the study intent.",
            "Try alternate terms for the outcome or exposure.",
            "Review existing OHDSI phenotype library for similar cohorts.",
        ]

    output = PhenotypeRecommendationAdviceOutput(
        plan=plan,
        advice=advice,
        next_steps=next_steps,
        questions=questions,
        mode=mode,
    )
    return _model_dump(output)
