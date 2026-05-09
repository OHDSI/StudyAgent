"""Pure validation, merge, and backfill helpers for cohort-method specs.

No IO. No network. Rule updates live in the section checkers only.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Tuple


COHORT_METHODS_SPEC_TOP_LEVEL_KEYS: List[str] = [
    "description",
    "getDbCohortMethodDataArgs",
    "createStudyPopArgs",
    "trimByPsArgs",
    "matchOnPsArgs",
    "stratifyByPsArgs",
    "createPsArgs",
    "fitOutcomeModelArgs",
]

LLM_FILLED_SECTIONS: List[str] = [
    "getDbCohortMethodDataArgs",
    "createStudyPopArgs",
    "propensityScoreAdjustment",
    "fitOutcomeModelArgs",
]

_REMOVE_DUP = {"keep all", "keep first", "remove all", "keep first, truncate to second"}
_ANCHOR = {"cohort start", "cohort end"}
_CALIPER_SCALE = {"propensity score", "standardized", "standardized logit"}
_BASE_SELECTION = {"all", "target", "comparator"}
_CV_TYPE = {"auto", "grid"}
_NOISE_LEVEL = {"silent", "quiet", "noisy"}
_MODEL_TYPE = {"logistic", "poisson", "cox"}


def validate_cohort_methods_spec(spec: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """Check top-level structural completeness.

    Returns (ok, missing_keys). Does not descend into section contents.
    """
    if not isinstance(spec, dict):
        return False, list(COHORT_METHODS_SPEC_TOP_LEVEL_KEYS)
    missing = [k for k in COHORT_METHODS_SPEC_TOP_LEVEL_KEYS if k not in spec]
    return (len(missing) == 0, missing)


def validate_section(section_name: str, value: Any) -> Tuple[bool, List[str]]:
    """Check enum values and numeric ranges for a single LLM-filled section.

    Returns (ok, violations) where violations is a list of human-readable strings.
    """
    if section_name not in LLM_FILLED_SECTIONS:
        return False, [f"unknown section: {section_name}"]
    checker = _SECTION_CHECKERS[section_name]
    violations: List[str] = []
    checker(value, violations)
    return (len(violations) == 0, violations)


def _require_object(section_name: str, value: Any, violations: List[str]) -> bool:
    if isinstance(value, dict):
        return True
    violations.append(f"{section_name} must be an object")
    return False


def _check_get_db_args(value: Any, violations: List[str]) -> None:
    if not _require_object("getDbCohortMethodDataArgs", value, violations):
        return
    max_size = value.get("maxCohortSize")
    if max_size is not None and isinstance(max_size, (int, float)) and max_size < 0:
        violations.append("maxCohortSize must be >= 0")
    washout = value.get("washoutPeriod")
    if isinstance(washout, (int, float)) and washout < 0:
        violations.append("washoutPeriod must be >= 0")
    dup = value.get("removeDuplicateSubjects")
    if dup is not None and dup not in _REMOVE_DUP:
        violations.append(f"removeDuplicateSubjects must be one of {sorted(_REMOVE_DUP)}")
    periods = value.get("studyPeriods")
    if periods is not None and not isinstance(periods, list):
        violations.append("studyPeriods must be a list")


def _check_study_pop(value: Any, violations: List[str]) -> None:
    if not _require_object("createStudyPopArgs", value, violations):
        return
    lookback = value.get("priorOutcomeLookback", value.get("priorOutcomeLookBack"))
    if isinstance(lookback, (int, float)) and lookback < 0:
        violations.append("priorOutcomeLookback must be >= 0")
    min_days = value.get("minDaysAtRisk")
    if isinstance(min_days, (int, float)) and min_days < 0:
        violations.append("minDaysAtRisk must be >= 0")
    start = value.get("startAnchor")
    end = value.get("endAnchor")
    if start is not None and start not in _ANCHOR:
        violations.append(f"startAnchor must be one of {sorted(_ANCHOR)}")
    if end is not None and end not in _ANCHOR:
        violations.append(f"endAnchor must be one of {sorted(_ANCHOR)}")
    tars = value.get("timeAtRisks")
    if tars is None:
        return
    if not isinstance(tars, list):
        violations.append("timeAtRisks must be a list")
        return
    for idx, tar in enumerate(tars):
        if not isinstance(tar, dict):
            violations.append(f"timeAtRisks[{idx}] must be an object")
            continue
        start = tar.get("startAnchor")
        end = tar.get("endAnchor")
        if start is not None and start not in _ANCHOR:
            violations.append(f"timeAtRisks[{idx}].startAnchor must be one of {sorted(_ANCHOR)}")
        if end is not None and end not in _ANCHOR:
            violations.append(f"timeAtRisks[{idx}].endAnchor must be one of {sorted(_ANCHOR)}")
        min_days = tar.get("minDaysAtRisk")
        if isinstance(min_days, (int, float)) and min_days < 1:
            violations.append(f"timeAtRisks[{idx}].minDaysAtRisk must be >= 1")


def _check_trim_by_ps(value: Any, violations: List[str]) -> None:
    if value is None:
        return
    if not _require_object("trimByPsArgs", value, violations):
        return
    trim = value.get("trimFraction")
    if isinstance(trim, (int, float)) and (trim < 0 or trim > 1):
        violations.append("trimFraction must be between 0 and 1")
    bounds = value.get("equipoiseBounds")
    if bounds is not None:
        if not isinstance(bounds, list) or len(bounds) != 2:
            violations.append("equipoiseBounds must be a two-item list or null")
        elif all(isinstance(x, (int, float)) for x in bounds):
            if bounds[0] < 0 or bounds[1] > 1 or bounds[0] >= bounds[1]:
                violations.append("equipoiseBounds must be ordered values between 0 and 1")


def _check_match_on_ps(value: Any, violations: List[str]) -> None:
    if value is None:
        return
    if not _require_object("matchOnPsArgs", value, violations):
        return
    ratio = value.get("maxRatio")
    if isinstance(ratio, (int, float)) and ratio < 0:
        violations.append("maxRatio must be >= 0")
    cal = value.get("caliper")
    if isinstance(cal, (int, float)) and cal < 0:
        violations.append("caliper must be >= 0")
    scale = value.get("caliperScale")
    if scale is not None and scale not in _CALIPER_SCALE:
        violations.append(f"caliperScale must be one of {sorted(_CALIPER_SCALE)}")


def _check_stratify_by_ps(value: Any, violations: List[str]) -> None:
    if value is None:
        return
    if not _require_object("stratifyByPsArgs", value, violations):
        return
    strata = value.get("numberOfStrata")
    if isinstance(strata, (int, float)) and strata < 1:
        violations.append("numberOfStrata must be >= 1")
    base = value.get("baseSelection")
    if base is not None and base not in _BASE_SELECTION:
        violations.append(f"baseSelection must be one of {sorted(_BASE_SELECTION)}")


def _check_create_ps(value: Any, violations: List[str]) -> None:
    if value is None:
        return
    if not _require_object("createPsArgs", value, violations):
        return
    max_fit = value.get("maxCohortSizeForFitting")
    if isinstance(max_fit, (int, float)) and max_fit < 0:
        violations.append("maxCohortSizeForFitting must be >= 0")
    control = value.get("control")
    if isinstance(control, dict):
        cv = control.get("cvType")
        if cv is not None and cv not in _CV_TYPE:
            violations.append(f"control.cvType must be one of {sorted(_CV_TYPE)}")
        noise = control.get("noiseLevel")
        if noise is not None and noise not in _NOISE_LEVEL:
            violations.append(f"control.noiseLevel must be one of {sorted(_NOISE_LEVEL)}")


def _check_ps_adjustment(value: Any, violations: List[str]) -> None:
    if value is None:
        value = {}
    if not isinstance(value, dict):
        violations.append("propensityScoreAdjustment must be an object or absent")
        return
    _check_trim_by_ps(value.get("trimByPsArgs"), violations)
    _check_match_on_ps(value.get("matchOnPsArgs"), violations)
    _check_stratify_by_ps(value.get("stratifyByPsArgs"), violations)
    _check_create_ps(value.get("createPsArgs"), violations)
    settings = value.get("psSettings")
    if settings is None:
        return
    if not isinstance(settings, list):
        violations.append("psSettings must be a list")
    else:
        for idx, ps in enumerate(settings):
            if not isinstance(ps, dict):
                violations.append(f"psSettings[{idx}] must be an object")
                continue
            match = ps.get("matchOnPsArgs")
            strat = ps.get("stratifyByPsArgs")
            if match is not None and isinstance(match, dict):
                ratio = match.get("maxRatio")
                if isinstance(ratio, (int, float)) and ratio < 0:
                    violations.append(f"psSettings[{idx}].matchOnPsArgs.maxRatio must be >= 0")
                cal = match.get("caliper")
                if isinstance(cal, (int, float)) and cal < 0:
                    violations.append(f"psSettings[{idx}].matchOnPsArgs.caliper must be >= 0")
                scale = match.get("caliperScale")
                if scale is not None and scale not in _CALIPER_SCALE:
                    violations.append(
                        f"psSettings[{idx}].matchOnPsArgs.caliperScale must be one of {sorted(_CALIPER_SCALE)}"
                    )
            if strat is not None and isinstance(strat, dict):
                strata = strat.get("numberOfStrata")
                if isinstance(strata, (int, float)) and strata < 2:
                    violations.append(f"psSettings[{idx}].stratifyByPsArgs.numberOfStrata must be >= 2")
                base = strat.get("baseSelection")
                if base is not None and base not in _BASE_SELECTION:
                    violations.append(
                        f"psSettings[{idx}].stratifyByPsArgs.baseSelection must be one of {sorted(_BASE_SELECTION)}"
                    )
    create_ps = value.get("createPsArgs")
    if isinstance(create_ps, dict):
        control = create_ps.get("control")
        if isinstance(control, dict):
            cv = control.get("cvType")
            if cv is not None and cv not in _CV_TYPE:
                violations.append(f"createPsArgs.control.cvType must be one of {sorted(_CV_TYPE)}")
            noise = control.get("noiseLevel")
            if noise is not None and noise not in _NOISE_LEVEL:
                violations.append(f"createPsArgs.control.noiseLevel must be one of {sorted(_NOISE_LEVEL)}")


def _check_outcome_model(value: Any, violations: List[str]) -> None:
    if not _require_object("fitOutcomeModelArgs", value, violations):
        return
    model_type = value.get("modelType")
    if model_type is not None and model_type not in _MODEL_TYPE:
        violations.append(f"modelType must be one of {sorted(_MODEL_TYPE)}")
    control = value.get("control")
    if isinstance(control, dict):
        cv = control.get("cvType")
        if cv is not None and cv not in _CV_TYPE:
            violations.append(f"control.cvType must be one of {sorted(_CV_TYPE)}")
        noise = control.get("noiseLevel")
        if noise is not None and noise not in _NOISE_LEVEL:
            violations.append(f"control.noiseLevel must be one of {sorted(_NOISE_LEVEL)}")


_SECTION_CHECKERS = {
    "getDbCohortMethodDataArgs": _check_get_db_args,
    "createStudyPopArgs": _check_study_pop,
    "propensityScoreAdjustment": _check_ps_adjustment,
    "fitOutcomeModelArgs": _check_outcome_model,
}


def merge_client_metadata(
    spec: Dict[str, Any],
    cohort_definitions: Dict[str, Any],
    negative_control: Dict[str, Any],
    covariate_selection: Dict[str, Any],
) -> Dict[str, Any]:
    """Return a deep copy of `spec` with client-carried metadata fields overwritten.

    Overwrites `cohortDefinitions`, `negativeControlConceptSet`, `covariateSelection`.
    Leaves `name` alone (LLM-supplied).
    """
    merged = deepcopy(spec) if isinstance(spec, dict) else {}
    if cohort_definitions:
        merged["cohortDefinitions"] = deepcopy(cohort_definitions)
    if negative_control:
        merged["negativeControlConceptSet"] = deepcopy(negative_control)
    if covariate_selection:
        merged["covariateSelection"] = deepcopy(covariate_selection)
    return merged


def backfill_section_from_defaults(
    spec: Dict[str, Any],
    defaults: Dict[str, Any],
    section_name: str,
) -> Dict[str, Any]:
    """Return a deep copy of `spec` with `section_name` replaced by the defaults value.

    Raises ValueError for sections outside LLM_FILLED_SECTIONS.
    """
    if section_name not in LLM_FILLED_SECTIONS:
        raise ValueError(f"cannot backfill unknown section: {section_name}")
    out = deepcopy(spec) if isinstance(spec, dict) else {}
    out[section_name] = deepcopy(defaults.get(section_name, {}))
    return out


_TAR_KEYS: Tuple[str, ...] = ("startAnchor", "riskWindowStart", "endAnchor", "riskWindowEnd")


def cohort_methods_spec_to_shell_recommendation(
    *,
    cohort_methods_spec: Dict[str, Any],
    raw_description: str,
    defaults_snapshot: Dict[str, Any],
    profile_name: str,
    input_method: str,
    rec_status: str,
) -> Dict[str, Any]:
    """Project a validated cohort-method spec into the 4-key recommendation shape the
    cohort-methods R shell expects.

    See docs/COHORT_METHODS_SPECIFICATIONS_RECOMMENDATION_DESIGN.md §6.
    """
    cspa = (cohort_methods_spec or {}).get("createStudyPopArgs") or {}
    cmda = (cohort_methods_spec or {}).get("getDbCohortMethodDataArgs") or {}
    if "propensityScoreAdjustment" in (cohort_methods_spec or {}):
        psadj = (cohort_methods_spec or {}).get("propensityScoreAdjustment") or {}
    else:
        psadj = {
            "trimByPsArgs": deepcopy((cohort_methods_spec or {}).get("trimByPsArgs")),
            "matchOnPsArgs": deepcopy((cohort_methods_spec or {}).get("matchOnPsArgs")),
            "stratifyByPsArgs": deepcopy((cohort_methods_spec or {}).get("stratifyByPsArgs")),
            "createPsArgs": deepcopy((cohort_methods_spec or {}).get("createPsArgs")),
        }
    fmod = (cohort_methods_spec or {}).get("fitOutcomeModelArgs") or {}

    study_population: Dict[str, Any] = {
        k: deepcopy(v) for k, v in cspa.items() if k not in _TAR_KEYS
    }
    if cmda:
        study_population["cohortMethodDataArgs"] = deepcopy(cmda)

    time_at_risk: Dict[str, Any] = {
        k: deepcopy(cspa[k]) for k in _TAR_KEYS if k in cspa
    }

    return {
        "mode": "free_text",
        "input_method": input_method,
        "source": "acp_flow",
        "status": rec_status,
        "profile_name": profile_name,
        "raw_description": raw_description,
        "study_population": study_population,
        "time_at_risk": time_at_risk,
        "propensity_score_adjustment": deepcopy(psadj),
        "outcome_model": deepcopy(fmod),
        "deferred_inputs": {
            "function_argument_description": "implemented",
            "description_file_path": "implemented",
            "interactive_typed_description": "implemented",
        },
        "defaults_snapshot": deepcopy(defaults_snapshot or {}),
    }
