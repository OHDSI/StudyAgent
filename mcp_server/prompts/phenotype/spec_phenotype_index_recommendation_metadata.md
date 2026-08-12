Output contract:
{
  "primary_clinical_topic": "string",
  "secondary_topics": ["string"],
  "phenotype_role": "diagnosis|outcome|complication|severity|screening|procedure|medication_based|risk_score|comorbidity_covariate|mixed|unknown",
  "care_setting_scope": "inpatient|outpatient|ed|mixed|unspecified",
  "population_scope": "string",
  "topic_mentions": {"primary_topics": ["string"], "context_only_topics": ["string"], "downstream_or_related_topics": ["string"]},
  "target_vs_context_conditions": {"target_conditions": ["string"], "context_conditions": ["string"]},
  "exclude_from_primary_topic_match": ["string"],
  "recommendation_summary": "string"
}

### HEURISTICS/RULES
For `phenotype_index_recommendation_metadata`
- Identify the narrow clinical topic represented by the supplied phenotype.
- Keep secondary and context topics distinct from the primary topic.
- Use `unknown` or `unspecified` when the source record does not support a stronger classification.
- Do not invent population, setting, code, validation, or outcome details.

Constraints:
- JSON only; no markdown/fences.
- Keep output compact.
