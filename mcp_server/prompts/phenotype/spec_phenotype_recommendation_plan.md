Tool: phenotype_recommendation_plan
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
  "shortlist_ids": ["<string from allowed list>"],
  "needs_more_search": "boolean",
  "reasoning_notes": ["string <=160 chars"]
}

### HEURISTICS/RULES

For `phenotype_recommendation_plan`
- Pick a small shortlist of candidates that are most worth deeper inspection.
- Prefer candidates that match the phenotype role implied by the study intent.
- Do not finalize recommendations yet; this step is only for selecting candidates for evidence hydration.
- If both clinically relevant and executable candidates exist, include at least one executable OHDSI candidate when it plausibly matches the intent.
- Use `needs_more_search=true` only when the current candidates appear systematically mismatched.

Constraints:
- Choose up to `maxShortlist` ids provided in the request.
- Use ONLY phenotype_ids from the allowed list provided.
- If none are worth deeper review, return an empty `shortlist_ids` array.
- JSON only; no markdown/fences; keep output < 10 KB.
