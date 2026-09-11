# Groundworkers hierarchy contract probe v0.1.0

Date: 2026-09-11

## Purpose

Verify that the pinned, read-only Groundworkers MCP service exposes a bounded
hierarchy contract suitable for later evaluation. This is not an ACP hierarchy
mode, a concept-set policy, or a clinical validation exercise.

## Service contract observed

The live MCP `tools/list` response advertised:

| Tool | Required input | Bounded controls relevant to the pilot |
| --- | --- | --- |
| `concept_ground` | `query` | `limit`, `domain`, `vocabulary_id`, `parent_ids`, `standard_only`, `active_only`, `include_embedding` |
| `concept_ancestors` | `concept_id` | `max_depth` (default 5; server clamps bounds) |
| `concept_descendants` | `concept_id` | `max_depth` (default 3; server clamps bounds) |

`concept_ground.parent_ids` is an optional list of OMOP concept IDs. The
Groundworkers contract describes it as an ancestor constraint: returned
candidates must descend from at least one supplied ID. The live input schema
requires only `query`; no unsupported ACP scope fields were used.

## Bounded non-PHI probes

### Parent-constrained grounding

Request:

```json
{
  "query": "lisinopril",
  "domain": "Drug",
  "vocabulary_id": "RxNorm",
  "parent_ids": [21601784],
  "standard_only": true,
  "active_only": true,
  "include_embedding": false,
  "limit": 5
}
```

Response summary:

- one result: `1308216`, `lisinopril`, RxNorm Drug Ingredient;
- `match_kind: EXACT`; active and standard;
- `effective_parent_ids: [21601784]` and `parent_ids_source: explicit`;
- `used_embedding: false`.

### Ancestor verification

Request:

```json
{"concept_id": 1308216, "max_depth": 2}
```

The response included `21601784`, `ACE inhibitors, plain`, ATC 4th,
classification concept, at depth 1. It also included multiple classification
ancestors that are not intuitively the intended ACE-inhibitor frame, including
hydrochlorothiazide-combination and lipid-modifying classes.

## Outcome

The provider supports an explicit, bounded parent-constrained lexical query and
deterministic ancestor/descendant lookups in the read-only service. The
unexpected additional ancestors are material evidence that a future hierarchy
mode must:

- use an explicit relationship/classification allowlist and maximum depth;
- return paths, depth, and standard/classification flags as review evidence;
- never infer inclusion, descendant policy, or a class-to-drug expansion;
- treat a hierarchy path as unavailable or unsuitable when it is outside the
  confirmed retrieval frame.

No database writes, ACP behavior changes, concept-set selections, approvals, or
emissions occurred. Record the vocabulary release and schema identifier beside
any later evaluation run; they were not captured in this contract probe.
