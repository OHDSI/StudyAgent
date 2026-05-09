# Cohort Methods Specifications Recommendation

This document describes an ACP recommendation flow that suggests analytic
settings from a free-text description.

The flow endpoint is:

```text
/flows/cohort_methods_specifications_recommendation
```

One available R wrapper is:

```r
OHDSIAssistant::suggestCohortMethodSpecs()
```

## Purpose

The flow converts a free-text analytic-settings description into a structured
analytic-settings recommendation.

## Data Flow

```text
free-text analytic-settings description
  -> ACP /flows/cohort_methods_specifications_recommendation
  -> MCP cohort_methods_prompt_bundle
  -> LLM response with cmAnalysis-shaped specifications
  -> validation and defaults backfill
  -> analytic-settings recommendation
```

## Request

The R wrapper sends a small snake_case request body:

```json
{
  "study_intent": "string",
  "study_description": "string",
  "analytic_settings_description": "string"
}
```

`analytic_settings_description` is required and must be non-empty.
`study_description` mirrors the same text for compatibility with other clients.

## Response

The endpoint returns:

```json
{
  "status": "ok",
  "recommendation": {
    "mode": "free_text",
    "input_method": "typed_text",
    "source": "acp_flow",
    "status": "received",
    "profile_name": "Recommended from free-text description",
    "raw_description": "free-text analytic settings",
    "study_population": {},
    "time_at_risk": {},
    "propensity_score_adjustment": {},
    "outcome_model": {},
    "deferred_inputs": {
      "function_argument_description": "implemented",
      "description_file_path": "implemented",
      "interactive_typed_description": "implemented"
    },
    "defaults_snapshot": {}
  },
  "cohort_methods_specifications": {},
  "section_rationales": {},
  "diagnostics": {}
}
```

`status` can be:

- `ok`
- `llm_parse_error`
- `schema_validation_error`

`recommendation.status` can be:

- `received`: the LLM output passed validation
- `backfilled`: at least one section was replaced with defaults

When ACP is not connected, the R wrapper returns a local stub with the same broad
shape and `recommendation$source = "local_stub_no_acp"`.

## Recommendation Shape

The `recommendation` object has four analytic sections:

- `study_population`
- `time_at_risk`
- `propensity_score_adjustment`
- `outcome_model`

Internally, the ACP flow asks the LLM for a cmAnalysis-shaped specification and
projects that object into the four recommendation sections:

- `study_population`: `createStudyPopArgs` without time-at-risk fields, plus
  `getDbCohortMethodDataArgs` nested as `cohortMethodDataArgs`
- `time_at_risk`: `startAnchor`, `riskWindowStart`, `endAnchor`, and
  `riskWindowEnd`
- `propensity_score_adjustment`: `trimByPsArgs`, `matchOnPsArgs`,
  `stratifyByPsArgs`, and `createPsArgs`
- `outcome_model`: `fitOutcomeModelArgs`

The full validated cmAnalysis-shaped object is returned as
`cohort_methods_specifications` for traceability.

## TODO

- Support projecting multiple cohort method analyses into the recommendation.
