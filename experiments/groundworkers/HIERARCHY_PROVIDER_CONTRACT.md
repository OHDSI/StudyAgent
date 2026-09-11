# Groundworkers hierarchy provider contract v0

Status: approved and implemented in the experimental `groundworkers_hierarchy`
required-review mode. It remains separate from the lexical `groundworkers` mode.

## Goal

Test whether a human-confirmed hierarchy anchor can narrow candidate retrieval
without turning hierarchy evidence into a concept-set policy. This is an
additional, opt-in evaluation mode; the existing `groundworkers` mode remains
lexical-only.

## Non-goals

This mode must not:

- infer an anchor from free text or select an anchor for the user;
- create, approve, include, exclude, or set descendant/mapped policy for a
  concept set;
- enable embeddings or broaden a no-result into a different retrieval mode;
- replace an executable OHDSI definition or modify vocabulary data.

## Proposed request contract

Add a future top-level request field, outside `scope`, after explicit human
confirmation:

```json
{
  "concept_build_mode": "groundworkers_hierarchy",
  "hierarchy_anchors": [
    {
      "concept_set_name": "ACE inhibitor",
      "concept_id": 21601784,
      "domain": "Drug",
      "vocabulary_id": "ATC",
      "anchor_role": "descendant_constraint"
    }
  ]
}
```

`hierarchy_anchors` is retrieval context, not an approved concept-set object.
The anchor must be selected from supplied Atlas/OHDSI evidence, a prior reviewed
candidate table, or explicitly supplied by the user. A class name alone is not
a valid anchor. The implementation rejects unknown, inactive, non-matching-
domain, or duplicate anchor IDs before contacting Groundworkers.

One confirmed anchor per concept-set lane is permitted in v0. Multiple anchors,
negative ancestor constraints, and automatic anchor discovery are out of scope.

## Provider behavior

For every lane with a confirmed anchor, the provider calls:

```json
{
  "query": "<existing confirmed lane term>",
  "domain": "<existing confirmed OMOP domain>",
  "vocabulary_id": "<existing confirmed vocabulary, if any>",
  "parent_ids": ["<confirmed anchor concept_id>"],
  "standard_only": true,
  "active_only": true,
  "include_embedding": false,
  "limit": 20
}
```

It then verifies ancestor membership with `concept_ancestors` at maximum depth
1. The resulting provenance must include the anchor as supplied, its returned
candidate count, provider limit, parent constraint, depth bound, candidate
standard/classification flags, and the grounding explanation.

The current tool contract reports ancestor membership and depth but does not
supply a per-result relationship ID/path. Therefore v0 labels the evidence
`provider_hierarchy_membership`; it must not claim a particular OMOP
relationship subtype. The unexpected ancestor associations in the initial probe
remain visible review context rather than being filtered or reinterpreted.

## Bounds and failure behavior

- Candidate limit: at most 20 per lane.
- Parent constraint: one positive anchor ID per lane.
- Ancestor verification depth: 1.
- Embedding fallback: disabled.
- Timeout: use the configured Groundworkers MCP timeout; preserve the provider
  exception verbatim in the run provenance.
- A timeout, malformed provider response, missing anchor, or failed ancestor
  verification yields `tool_status: "unavailable"` or `status: "error"`, not a
  successful empty candidate list.

## Human-review boundary

Every candidate remains unreviewed. The response must clearly distinguish:

- the user-confirmed retrieval anchor (classification/ancestor context);
- a returned active standard candidate; and
- a later, separately approved concept-set policy.

No result permits the system to set `include_descendants`, `include_mapped`, or
any inclusion/exclusion field. If the user rejects the anchor or candidates,
the workflow returns to scope/anchor selection rather than widening traversal.

## Implemented decision

This v0 boundary was approved for the experimental pilot: one explicitly
human-confirmed anchor per scope lane, lexical-only retrieval, depth-one provider
ancestry evidence, and no claim of a specific OMOP relationship subtype.

## Evaluation set and success criteria

For the next evaluation phase, freeze three held-out cases with reviewer-approved roots:

1. ACE-inhibitor class anchored to a specified ATC class;
2. one Condition parent/child case with an explicit known anchor; and
3. one negative control where a broad anchor must not make an unrelated concept
   eligible.

Compare this provider only against the baseline classification-fallback route.
For each case record root recall and reciprocal rank at 1, 5, and 20; anchor and
domain correctness; provider evidence; latency; candidate count; and reviewer
work. A run fails when its anchor is not reproduced in provenance, a candidate
is outside the confirmed domain, an unavailable provider appears as a zero
result, or any hierarchy evidence becomes policy without explicit approval.

## Required implementation tests

1. Model validation rejects hierarchy mode without a confirmed anchor.
2. Provider arguments include exactly the confirmed anchor and lexical-only
   filters.
3. Returned candidates retain hierarchy provenance but no policy fields.
4. Provider exceptions produce unavailable/error provenance, never an implicit
   lexical fallback.
5. Existing `groundworkers` lexical mode retains `include_embedding: false` and
   sends no `parent_ids`.

## Implementation status

The request model, bounded provider path, and regression coverage are in place.
The next evaluation step is a small held-out hierarchy comparison using the
three cases above; it remains review-only and requires explicit candidate policy
approval before any cohort definition can be emitted.
