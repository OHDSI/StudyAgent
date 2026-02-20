Tool: phenotype_improvements
Output contract:
{
  "plan": "string <=300 chars",
  "phenotype_improvements": [
    {
      "targetCohortId": "<int from allowed list>",
      "summary": "string <=220 chars",
      "actions": [ { "type": "note", "path": "string", "value": "string" } ]
    }
  ],
  "code_suggestion": { "language": "R", "summary": "string", "snippet": "string" }  // optional
}

### HEURISTICS/RULES

For `phenotype_improvements` 
- Examine the phenotype cohort definition JSON and associated artifacts for possible improvements that will theoretically increase the sensitivity, specificity, and positive predictive value of the artifact when applied to clinical data. Take on two roles when doing your analysis - first as a clinical researcher who understands biostatistics and observational retrospective designs, and second as a data scientist who understands how health data is captured within electronic health records. 


Constraints:
- Use ONLY cohortIds from the allowed list provided.
- If no improvements, return an empty phenotype_improvements array.
- JSON only; no markdown/fences; keep output < 12 KB.
Example:
{
  "plan": "Review phenotypes against study intent; focus on washout and exposure timing.",
  "phenotype_improvements": [
    {
      "targetCohortId": 33,
      "summary": "Add 365d washout and exclude prior PD meds to reduce prevalence bias.",
      "actions": [
        { "type": "note", "path": "/PrimaryCriteria/ObservationWindow", "value": "Consider PriorDays>=365." }
      ]
    }
  ],
  "code_suggestion": {
    "language": "R",
    "summary": "Example to tighten washout in Circe JSON before export.",
    "snippet": "cohort$PrimaryCriteria$ObservationWindow$PriorDays <- 365"
  }
}
