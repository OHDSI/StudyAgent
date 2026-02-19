Tool: phenotype_recommendations
Output contract:
{
  "plan": "string <=300 chars",
  "phenotype_recommendations": [
    {
      "cohortId": "<int from allowed list>",
      "cohortName": "string",
      "justification": "string <=200 chars",
      "confidence": "number 0-1 (optional)"
    }
  ]
}

### HEURISTICS/RULES

For `phenotype_recommendations`
- Select for the user only those phenotypes that make clinical sense when considering the user's stated study intent or what can be validly inferred from the intent statement. If none of the descriptions for the phenotypes logically aligns as an outcome or potential relevant covariate then do not return anything.

Constraints:
- Choose up to maxResults provided in the request.
- Use ONLY cohortIds from the allowed list provided.
- If no matches, return an empty phenotype_recommendations array.
- JSON only; no markdown/fences; keep output < 10 KB.
Example:
{
  "plan": "Rank phenotypes matching Parkinson’s treatment and outcomes.",
  "phenotype_recommendations": [
    { "cohortId": 33, "cohortName": "Parkinsons", "justification": "Captures PD diagnosis aligned with study intent.", "confidence": 0.78 },
    { "cohortId": 1197, "cohortName": "PD Meds", "justification": "Medication exposure conceptually linked to outcome comparisons.", "confidence": 0.64 }
  ]
}
