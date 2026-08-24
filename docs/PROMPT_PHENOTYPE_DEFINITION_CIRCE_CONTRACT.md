# Implementation prompt: executable phenotype-definition service

Implement the ACP contract below so the R package
`slashOhdsiStrategusAssistant` can obtain an executable cohort definition only
after a user selects a candidate returned by `phenotype_recommendation`.

## Scope and architecture

The ACP server already advertises and routes `POST /flows/phenotype_definition`
through `run_phenotype_definition_flow()`. It currently assembles an indexed
`document` using `phenotype_fetch_summary` and `phenotype_fetch_definition`.
Evolve that existing endpoint into the executable-definition boundary described
here. Do not require the R client to access `catalog.jsonl`, `definitions/`, the
PhenotypeLibrary installation, or an ACP filesystem path.

The endpoint must support two internal paths:

1. **Already computable:** retrieve the selected phenotype's computable Circe
   JSON from ACP/MCP-owned artifacts and return it.
2. **Not computable:** orchestrate a new internal ACP flow named
   `phenotype_make_computable`. That flow converts the selected phenotype into a
   computable definition, validates the result, and returns Circe JSON. The
   public `phenotype_definition` endpoint then returns that same validated JSON
   to the client.

`phenotype_recommendation` remains a lightweight selection service. It must not
embed full cohort JSON in every candidate response.

## Recommendation response changes

Each item in `recommendations.phenotype_recommendations` must include:

```json
{
  "phenotype_id": "ohdsi:123",
  "phenotype_name": "Type 2 diabetes mellitus",
  "justification": "Matches the requested target population.",
  "computability_status": "circe_available"
}
```

`phenotype_id` is the stable ACP/index identifier to pass to
`phenotype_definition`; it may be an OHDSI or CIPHER identifier. It is not
itself an executable-definition contract. `computability_status` must be one
of:

- `circe_available`: ACP can return validated Circe JSON without conversion.
- `conversion_required`: the item is eligible for `phenotype_make_computable`.
- `not_computable`: ACP cannot currently produce an executable definition.

Keep recommendation rank, confidence, source metadata, and other display fields
if useful. Do not claim `circe_available` unless the definition can actually be
returned and validated.

## Public request contract

`POST /flows/phenotype_definition`

```json
{
  "phenotype_id": "ohdsi:123",
  "allow_make_computable": true,
  "recommendation_context": {
    "recommendation_role": "target",
    "workflow_type": "cohort_methods"
  }
}
```

Required:

- `phenotype_id`: nonempty identifier selected from
  `phenotype_recommendation`.

Optional:

- `allow_make_computable`: boolean; default `true`. If false, ACP must not
  invoke conversion and must return `conversion_required` for a non-computable
  source.
- `recommendation_context`: optional metadata for audit and conversion context.
  It must not be required for stable retrieval.

The service must not rely on server-side conversational state, an ephemeral
recommendation token, or the caller having the same PhenotypeLibrary version.
A request containing the selected `phenotype_id` must be sufficient.

## Successful response contract

For HTTP 200 and `status: "ok"`, return this shape:

```json
{
  "status": "ok",
  "phenotype_id": "ohdsi:123",
  "phenotype_name": "Type 2 diabetes mellitus",
  "computability_status": "circe_available",
  "definition_source": "phenotype_library",
  "definition_revision": "<stable source revision, release, or content version>",
  "definition_sha256": "<SHA-256 of canonical Circe JSON>",
  "conversion": {
    "performed": false,
    "source_phenotype_id": "ohdsi:123",
    "capr_code": null,
    "validation": {
      "status": "passed",
      "messages": []
    }
  },
  "circe_json": {
    "PrimaryCriteria": {},
    "ConceptSets": []
  }
}
```

Requirements:

- `circe_json` is required and must be a JSON object, not a path, URL, source
  ID, escaped JSON string, Capr source, CIPHER document, or a nested generic
  `document.definition` object.
- It must be a complete executable OHDSI Circe `SIMPLE_EXPRESSION` definition.
  At minimum the parsed object must have `PrimaryCriteria` and `ConceptSets`.
  Validate it with the project's Circe/Capr tooling before returning it.
- `definition_sha256` is calculated from a documented canonical JSON
  serialization and is used for provenance/integrity. ACP must return the hash
  that corresponds to exactly the returned `circe_json`.
- `definition_source` identifies the actual origin, for example
  `phenotype_library`, `acp_conversion`, or another precise provider label.
- `definition_revision` must identify the source artifact/version used. It is
  not an ACP server timestamp alone.
- Preserve the selected `phenotype_id` exactly in the response.

The R package will validate and immediately save `circe_json` as a
workflow-local artifact. It will execute that saved artifact and will not later
resolve the definition through ACP or PhenotypeLibrary.

## Conversion path

When the selected phenotype has `computability_status: "conversion_required"`
and `allow_make_computable` is true, `phenotype_definition` must call the new
internal `phenotype_make_computable` flow.

That flow must:

1. accept the selected `phenotype_id` and optional safe context;
2. obtain the source phenotype metadata/definition needed for conversion;
3. produce Capr code when Capr is the conversion representation;
4. compile/convert it to Circe JSON;
5. validate the resulting Circe JSON; and
6. return the validated JSON plus conversion provenance to
   `phenotype_definition`.

For a converted definition, the successful public response is still the exact
`status: "ok"` contract above, with:

```json
"definition_source": "acp_conversion",
"conversion": {
  "performed": true,
  "source_phenotype_id": "cipher:1197",
  "capr_code": "<Capr source used for conversion>",
  "validation": { "status": "passed", "messages": [] }
}
```

Do not return unvalidated LLM-generated code or JSON as successful. A failed
conversion must never yield `status: "ok"` or a `circe_available` result.

## Unavailable and error responses

Use a structured non-success response when no executable definition can be
returned:

```json
{
  "status": "unavailable",
  "phenotype_id": "cipher:1197",
  "computability_status": "not_computable",
  "error": "conversion_not_available",
  "message": "ACP could not produce a validated Circe definition.",
  "conversion": {
    "performed": true,
    "validation": { "status": "failed", "messages": ["..."] }
  }
}
```

Use HTTP 4xx for invalid requests and HTTP 5xx for unexpected ACP/MCP failures.
A known phenotype that cannot be made computable is an expected domain outcome:
return HTTP 200 with `status: "unavailable"`, never partial JSON.

## Required implementation and test updates

- Update `docs/SERVICE_REGISTRY.yaml` to document `phenotype_definition` and
  new `phenotype_make_computable` as planned/implemented accurately; do not
  mark conversion implemented until it is tested.
- Update the ACP `/services` inventory and endpoint validation/documentation to
  match the public contract.
- Retain `phenotype_fetch_definition` as an MCP retrieval primitive if useful,
  but do not expose its provider-shaped payload as the public ACP contract.
- Add tests for:
  - directly computable definition retrieval;
  - `conversion_required` invoking the conversion flow;
  - `allow_make_computable: false` preventing conversion;
  - failed validation/conversion producing `status: "unavailable"` and no
    `circe_json`;
  - hash matching the returned canonical JSON; and
  - malformed/non-Circe provider data being rejected.
- Update `WORKFLOW_PHENOTYPE_RECOMMENDATION.md` and the recommendation output
  schema to include `computability_status` and document the follow-up call.

## Acceptance criterion

A Strategus shell can present the lightweight recommendation list, send exactly
one selected `phenotype_id` to `phenotype_definition`, receive a validated
`circe_json` object, save it locally, and generate cohorts without a local ACP
phenotype-index directory or a runtime dependency on PhenotypeLibrary.
