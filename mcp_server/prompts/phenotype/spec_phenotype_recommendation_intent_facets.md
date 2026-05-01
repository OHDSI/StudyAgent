Tool: phenotype_recommendation_intent_facets
Output contract:
{
  "plan": "string <=300 chars",
  "intent_facets": {
    "condition_or_topic": "string",
    "phenotype_role": "diagnosis|outcome|screening|severity|procedure|medication_based|risk_score|mixed|unknown",
    "care_setting": "outpatient|inpatient|ed|any|unknown",
    "population_cue": "string",
    "validation_preference": "required|preferred|not_specified",
    "executability_preference": "prefer_native_ohdsi|allow_translation|not_specified",
    "geography_coding_preference": "us_omop|uk_read|va|not_specified"
  },
  "reasoning_notes": ["string <=160 chars"]
}

### HEURISTICS/RULES
For `phenotype_recommendation_intent_facets`
- Infer intent facets from the study intent only.
- Do not use candidate phenotypes because none are provided in this step.
- Preserve the user disease/topic faithfully; do not broaden it to related comorbidities or outcomes.
- Use `unknown` or `not_specified` when the intent does not support a stronger claim.
- Keep reasoning sparse and grounded in the wording of the user intent.

Constraints:
- JSON only; no markdown/fences.
- Keep output < 8 KB.
