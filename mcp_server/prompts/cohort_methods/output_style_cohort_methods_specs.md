<Output Style>
Return exactly one fenced JSON block with the shape:
```json
{
  "specifications": { ... full updated cmAnalysis spec ... },
  "sectionRationales": {
    "study_population":             { "rationale": "...", "confidence": "high|medium|low" },
    "time_at_risk":                 { "rationale": "...", "confidence": "high|medium|low" },
    "propensity_score_adjustment":  { "rationale": "...", "confidence": "high|medium|low" },
    "outcome_model":                { "rationale": "...", "confidence": "high|medium|low" }
  }
}
```
No text outside the fenced block.
</Output Style>
