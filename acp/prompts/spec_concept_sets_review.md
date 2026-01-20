Tool: concept-sets-review
Output contract:
{
  "plan": "string <=300 chars",
  "findings": [Finding],
  "patches": [Patch],
  "risk_notes": ["string"],
  "actions": [Action]  # optional if supported
}
Finding: { "id": "snake_case", "severity": "low|medium|high", "impact": "design|validity|portability|performance", "message": "<=220 chars", "evidence": [{"ref":"string","note":"<=160 chars"}] }
Patch: { "artifact": "string", "type": "jsonpatch", "ops": [ { "op": "note", "path": "/path", "value": { "summary": "<=160 chars", "details": "<=400 chars" } } ] }
Action (concept sets): { "type": "set_include_descendants", "where": { "domainId": "...", "conceptClassId": "...", "includeDescendants": true|false }, "value": true|false, "rationale": "<=160 chars", "confidence": 0-1 }

### HEURISTICS/RULES
For `concept-sets-review`

- test: *Failure to use descendant concepts in the DRUG domain when possibly relevant*  (`suggest_descendants_concept_set`, severity: medium, impact: design)
        - example: concepts in the DRUG domain where the concept set uses only an ingredient concept without specifying `"includeDescendants:" true`
        - patch (advisory): Add a `jsonpatch` note explaining to the user that the concept set would likely be sub-optimal if used in a cohort definition with drug_exposure criteria because record in that table tend to have clinical drug codes (i.e., codes that specify drug concepts with strengh and formulation). 
        - patch (action) An appropriate action would be to edit the concept set to set all ingredient concepts in the JSON concept set definition to have `"includeDescendants:" true`
       - Example:
```json
{
  "type": "set_include_descendants",
  "where": { "domainId": "Drug", "conceptClassId": "Ingredient", "includeDescendants": false },
  "value": true,
  "rationale": "Drug exposures are usually recorded as clinical drug codes; include descendants to capture forms/strengths.",
  "confidence": 0.8
}
```

Constraints: JSON only, no markdown. Keep output < 15 KB. If nothing to report, return empty arrays and a neutral plan.
