Tool: phenotype_recommendation_intent_facets
Output contract:
{
  "plan": "string <=300 chars",
  "intent_facets": {
    "condition_or_topic": "string",
    "clinical_topic_aliases": ["string <=60 chars"],
    "phenotype_role": "diagnosis|outcome|screening|severity|procedure|medication_based|risk_score|mixed|unknown",
    "care_setting": "outpatient|inpatient|ed|any|unknown",
    "population_cue": "string",
    "validation_preference": "required|preferred|not_specified",
    "executability_preference": "prefer_native_ohdsi|allow_translation|not_specified",
    "geography_coding_preference": "us_omop|uk_read|va|not_specified",
    "role_cues": ["string <=40 chars"],
    "care_setting_cues": ["string <=40 chars"],
    "population_cues": ["string <=40 chars"]
  },
  "reasoning_notes": ["string <=160 chars"]
}

### HEURISTICS/RULES
For `phenotype_recommendation_intent_facets`
- Infer intent facets from the study intent only.
- Do not use candidate phenotypes because none are provided in this step.
- Preserve the user disease/topic faithfully; do not broaden it to related comorbidities or outcomes.
- Normalize specific wording into the canonical facet categories when the user intent clearly implies them.
- Collapse narrow lexical items into broader semantic cues when appropriate.
- Examples: insulin, metformin, GLP-1 agonist, sulfonylurea -> medication/drug cue; clinic, office, ambulatory -> outpatient cue; CABG, repair, postoperative -> procedure cue.
- Populate `role_cues`, `care_setting_cues`, and `population_cues` with short normalized cue labels that explain why the canonical facet was chosen.
- Prefer broad semantic cue labels over copying raw surface forms verbatim.
- Inside `intent_facets`, include optional `clinical_topic_aliases` when the study intent uses an abbreviation, acronym, shorthand, colloquial clinical phrase, or alternate wording that could map to a more standard disease/topic name.
- `clinical_topic_aliases` must be a short array of strings with at most 5 items.
- Include only exact abbreviation expansions or near-synonymous phrasings of the same main condition/topic.
- Do not include broader diseases, narrower complications, procedures, treatments, biomarkers, or speculative related concepts in `clinical_topic_aliases`.
- If the topic is already standard and unambiguous, `clinical_topic_aliases` may be empty.
- Good examples: ADRD -> Alzheimer's disease, Dementia; GI bleed -> Gastrointestinal bleeding, Gastrointestinal hemorrhage; COPD -> Chronic obstructive pulmonary disease.
- Use `unknown` or `not_specified` when the intent does not support a stronger claim.
- Keep reasoning sparse and grounded in the wording of the user intent.

Constraints:
- JSON only; no markdown/fences.
- Keep output < 8 KB.
