Tool: cohort-critique-general-design
Output contract:
{
  "plan": "string <=300 chars",
  "findings": [Finding],
  "patches": [Patch],
  "risk_notes": ["string"]
}
Finding: { "id": "snake_case", "severity": "low|medium|high", "impact": "design|validity|portability|performance", "message": "<=220 chars", "evidence": [{"ref":"string","note":"<=160 chars"}] }
Patch: { "artifact": "string", "type": "jsonpatch", "ops": [ { "op": "note", "path": "/path", "value": { "summary": "<=160 chars", "details": "<=400 chars" } } ] }

### HEURISTICS/RULES

For `cohort-critique-general-design`

- test: *Missing or zero-day washout* in `/PrimaryCriteria/ObservationWindow.PriorDays` (`missing_washout`, medium, validity).
        - example: `/PrimaryCriteria/ObservationWindow.PriorDays` is missing of	is set to 0
        - patch: Add a `jsonpatch` note proposing a typical washout (e.g., 365 days)
        -  do *not* emit actions unless you see a specifically supported type for cohorts (if none given, leave `actions: []` and explain in `risk_notes`).

	
- test: *Inverted windows* in inclusion rules (`inverted_window_<index>`, high, validity).
	- example: inclusion rule specifies `start > end`
        - patch: Add a `jsonpatch` note clarifying window alignment
       -  do *not* emit actions unless you see a specifically supported type for cohorts (if none given, leave `actions: []` and explain in `risk_notes`).

- test: *Ambiguous time-at-risk*  (`unclear_time_at_risk`, low, validity).
	- example: time-at-risk if clearly absent in the cohort	definition
        - patch: Add a `jsonpatch` note explaining why time at risk could be important and suggesting common time at risk options
       -  do *not* emit actions unless you see a specifically supported type for cohorts (if none given, leave `actions: []` and explain in `risk_notes`).

- test: *Failure to use descendant concepts in the DRUG domain when the cohort definition specifies that the concept set will be used in a `drug_exposure` criterion*  (`suggest_descendants_concept_set`, severity: medium, impact: design)
        - example: concepts in the DRUG domain where the concept set uses only an ingredient concept without specifying `"includeDescendants:" true`
        - patch (action) An appropriate action would be to edit the concept set to set all ingredient concepts in the JSON concept set definition to have `"includeDescendants:" true`
        - Example:
```json
{
  "type": "cohort_definition_concept_set_include_descendants",
  "where": { "domainId": "Drug", "conceptClassId": "Ingredient", "includeDescendants": false },
  "value": true,
  "rationale": "Drug exposures are usually recorded as clinical drug codes; include descendants to capture forms/strengths.",
  "confidence": 0.8
}


Constraints: JSON only, no markdown. Keep output < 15 KB. If nothing to report, return empty arrays and a neutral plan.
