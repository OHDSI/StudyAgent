# Phenotype Make Computable

`POST /flows/phenotype_make_computable` translates a confirmed, reviewed cohort scope into a pure function-form Capr R artifact and validated Circe JSON. It is a direct-narrative flow; integration from `phenotype_definition` is not implemented.

## Request lifecycle

1. Submit a narrative statement with `confirmed_scope: false` to receive the required scope checklist.
2. Submit a confirmed structured scope. With `concept_review_mode: required`, the flow returns vocabulary candidates for review.
3. Resubmit selected concept sets with `concept_review_mode: provided_only`. The flow emits Capr, invokes the generated function in controlled validation, and returns Circe JSON.

`propose` uses the configured LLM only to prepare a reviewable cohort-plan proposal. It does not bypass concept review or deterministic validation.

## Example

```json
{
  "narrative_statement": "Earliest event of cirrhosis of liver. Persons exit on end of observation period.",
  "confirmed_scope": true,
  "scope": {
    "index_event": "Cirrhosis of liver",
    "criterion_domains": {"Cirrhosis of liver": "Condition"},
    "entry_limit": "First",
    "prior_observation": 0,
    "index_day_boundary": "included",
    "windows": "none",
    "exit_strategy": "observation"
  },
  "concept_review_mode": "provided_only",
  "concept_sets": [{
    "name": "Cirrhosis of liver",
    "domain": "Condition",
    "items": [{"concept_id": 4064161, "domain": "Condition", "include_descendants": true, "include_mapped": false, "is_excluded": false}]
  }]
}
```

A successful response contains `capr.filename` (`phenotype_definition.R`), `capr.entry_point` (`phenotype_make_computable_definition`), `capr.source`, inline `circe_json`, and technical validation status. Sourcing the R file has no side effects; the function returns a Capr cohort object. The caller owns artifact persistence.

## Current supported surface

- One Condition-domain concept set, with first/all entry, configurable prior continuous observation, observation or fixed exit, and optional era collapse.
- Condition entry overlapping a reviewed Visit concept set, with explicit `visit_overlap_mode` (`entry` or `attrition`) and configurable fixed-exit anchor.
- The explicit `temporal_followup` pattern used by the corrected development variant of cohort 63: a direct diagnosis or trigger event followed by diagnosis, a clean window, continuous observation, fixed exit, and zero-day era padding.

Concept-item descendant, mapped, and exclusion policies are preserved in generated Circe concept sets.

## Clarification and failure states

The flow returns `needs_clarification` for an unconfirmed or incomplete scope. It also returns a mixed-domain clarification card when reviewed items span multiple event domains without `multi_domain_entry_policy`; the flow does not silently emit a Condition-only approximation.

Only `index_day_boundary: "included"` and `windows: "none"` are supported outside explicit emitter modes. Other values fail closed. Unsupported concept/domain combinations or temporal forms return structured emitter diagnostics rather than an approximate definition.

Reviewed concept sets must contain exactly one of `items` (each with `concept_id`/`conceptId` and descendant, mapped, and exclusion policies) or `concept_ids`/`conceptIds`. The flow also accepts `concepts` as an item-list alias and normalizes OMOP-style camelCase item fields. Malformed review input returns `needs_clarification` with `invalid_concept_sets` before emission.

## Live prompt-contract smoke test

Run the synthetic, non-PHI prompt smoke test with the same configuration loader used by service startup:

```bash
uv run --extra dev python scripts/smoke_phenotype_make_computable_llm.py --config ./config.yaml --profile native
```

It prints only transport, parse, and schema status; it does not write cohort artifacts.

## R library selection

Capr/Circe validation uses `R_LIBS_USER` when it is set. Otherwise it discovers the first project library under `renv/library/`. Deployments should set `R_LIBS_USER` explicitly to the validated Capr/Circe library, especially where more than one R version or platform library is available.

## Concurrent requests

The ACP service may accept concurrent HTTP requests, but `phenotype_make_computable` serializes its proposal LLM call per ACP process. Managed stdio MCP operations are serialized on their shared session, and Capr/Circe R compilation is serialized per MCP process. Requests can therefore queue under load; this v1 boundary prioritizes artifact isolation and deterministic validation over parallel R execution.

## Validation boundary

Validation confirms that generated R can be sourced, the known function returns a Capr cohort, Circe JSON is produced, and CirceR generates SQL. It is technical validation only: it does not establish clinical validity, patient-level behavior, or equivalence to a reference cohort. Generated R source is screened before execution, but deployment should still provide process-level isolation appropriate to its threat model.

## Capr roadmap

See [Capr Capability Gap](CAPR_FEATURE_GAP.md) for documented Capr features that are valuable but not yet implemented by this ACP flow. New capability work must add a typed scope variant, deterministic emitter support, validation, tests, and documentation together.
