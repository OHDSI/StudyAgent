Tool: phenotype_recommendations
Output contract:
{
  "plan": "string <=300 chars",
  "phenotype_recommendations": [
    {
      "phenotype_id": "<string from allowed list>",
      "phenotype_name": "string",
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
- Use ONLY phenotype_ids from the allowed list provided.
- If no matches, return an empty phenotype_recommendations array.
- JSON only; no markdown/fences; keep output < 10 KB.
Example:
{
  "plan": "Rank phenotypes matching Parkinson’s treatment and outcomes.",
  "phenotype_recommendations": [
    { "phenotype_id": "ohdsi:33", "phenotype_name": "Parkinsons", "justification": "Captures PD diagnosis aligned with study intent.", "confidence": 0.78 },
    { "phenotype_id": "cipher:1197", "phenotype_name": "PD Meds", "justification": "Medication exposure conceptually linked to outcome comparisons.", "confidence": 0.64 }
  ]
}
