# Groundworkers candidate-provider evaluation plan

## Status and fixed lexical checkpoint

The lexical pilot is complete enough to freeze as a comparison checkpoint. It
runs in the dedicated Groundworkers environment and is invoked only by the
review-gated `phenotype_make_computable` request mode
`concept_build_mode: "groundworkers"`. The current ACP integration always
sends `include_embedding: false`, `standard_only: true`, and `active_only: true`
to `concept_ground`.

This mode returns retrieval evidence only. Scope confirmation, policy approval,
Capr/Circe emission, and technical validation remain in StudyAgent. No result
below is clinical validation or an approved concept set.

Record the following with every later comparison run:

- StudyAgent pilot commit and Groundworkers skill commit;
- `requirements-resolved.txt`, wheel-hash file, and Groundworkers configuration
  hash (never credential values);
- OMOP vocabulary release/version and vocabulary schema identifier;
- request JSON, raw ACP response, and any downloaded review artifacts;
- ACP and Groundworkers service versions, endpoint configuration, and timeout.

## Observed lexical comparison matrix

All rows used the same narrative and supported confirmed-scope fields on the
baseline ACP and the pilot ACP. Both paths stopped before policy approval or
emission.

| Scenario | Baseline retrieval | Groundworkers lexical retrieval | Interpretation |
| --- | --- | --- | --- |
| Type 2 diabetes mellitus, Condition | No candidates | 2 active standard SNOMED candidates | Different retrieval behavior against the same vocabulary is demonstrated. |
| Acute kidney injury plus supporting Organ failure, Condition | 16 AKI and 7 Organ-failure candidates | 1 AKI and 7 Organ-failure candidates | Groundworkers was narrower for the index lane; both retained the two-lane clinical structure. |
| Chronic kidney disease, Condition | 20 returned of 102 exact lexical matches | 1 active standard SNOMED candidate | Broad baseline slice versus exact lexical root; Groundworkers did not report completeness. |
| ACE inhibitor, Drug class | 14 classification-ancestor fallback candidates | 0 candidates | Expected: class expansion is outside the lexical-only Groundworkers mode. |
| Lisinopril, RxNorm Drug ingredient | 20 returned of 77 exact RxNorm matches | 1 active standard RxNorm Ingredient, concept 1308216 | Exact ingredient control shows the intended precision-oriented contrast. |

The medication frame is a required conversational scope decision for Drug
terms, but is not an ACP `scope` field. It must not be serialized as
`medication_frame` or another invented attribute.

## Phase 2: explicit hierarchy evaluation

Do not alter the lexical mode. Add a separate opt-in mode only after confirming
the Groundworkers tool contract for controlled hierarchy traversal.

### Required design boundary

- Proposed request mode: `concept_build_mode: "groundworkers_hierarchy"`.
- Keep `concept_build_mode: "groundworkers"` lexical-only forever for this
  experiment line.
- Require an explicit user-confirmed retrieval frame for a class term, such as
  `drug_class`; retain it as review context rather than an ACP scope field.
- Return classification or ancestor candidates as review evidence with their
  relationship path, depth, vocabulary, and standard/classification status.
- Never convert a hierarchy result into `include_descendants`, an inclusion, or
  an exclusion policy automatically.

### Preflight before implementation

1. Capture `concept_ground` and any hierarchy-tool schemas from the pinned
   Groundworkers service, including supported parent/ancestor arguments,
   relationship types, depth limits, and provider response fields.
2. Select an allowlist of OMOP relationships and a maximum traversal depth.
   Record both in provider provenance.
3. Establish bounded timeouts, candidate limits, and a structured unavailable
   response. A provider timeout must never become an apparent zero-result.
4. Confirm that the read-only vocabulary identity can serve the required
   `concept_ancestor` / relationship evidence without new writes.

### Held-out hierarchy cases

Use a small frozen set with curator-approved roots and expected evidence type:

- drug class (`ACE inhibitor`) where ancestor/classification evidence is
  expected;
- Condition parent/child term with a documented descendant relationship;
- a negative control whose lexical match must not be promoted through a broad
  parent.

For each case, compare baseline fallback and hierarchy mode on: reviewer-
approved root recall at 20, rank, relationship-path accuracy, standard/domain
status, candidate count, latency, and reviewer actions needed. A case fails if
path evidence is missing, out of the bounded relationship policy, or silently
becomes a concept-set policy.

## Phase 3: targeted embedding evaluation

Embeddings are a separate provider mode, not a fallback enabled in lexical or
hierarchy tests.

### Required design boundary

- Proposed request mode: `concept_build_mode: "groundworkers_embedding"`.
- The mode uses a dedicated vector schema/table or dedicated vector database;
  it never writes vectors into the shared vocabulary schema.
- The embedding model identifier and immutable revision/digest are mandatory.
  Mutable labels such as `latest` are not reproducible provenance.
- No PHI, row-level data, or free-text clinical records enter the corpus.
- A timeout or unavailable vector store returns structured provider-unavailable
  provenance; it must not silently fall back to a different retrieval mode.

### Corpus construction

Create and validate one manifest using
`embedding-corpus-manifest.schema.json` before vectorization. The initial
corpus is deliberately small and may include only:

1. candidate concepts returned by baseline and lexical Groundworkers searches
   for the frozen evaluation cases;
2. approved reference-set roots from training cases, never held-out answers;
3. bounded ancestors/descendants and standard mappings with recorded depth;
4. selected CIPHER/OHDSI phenotype-source code evidence after deterministic
   vocabulary mapping;
5. clinically adjacent concepts admitted by a written, case-specific rule.

Every manifest concept requires a source label. A corpus revision is immutable:
new concepts, a different model, or altered selection rules produce a new
manifest hash and vector collection.

### Evaluation protocol

Split definitions before corpus selection into development and held-out sets.
Do not use held-out approved concept roots, reviewer decisions, or source
artifacts to construct the development corpus. Evaluate lexical, hierarchy, and
embedding modes independently on the same held-out requests.

Primary measures:

- recall and reciprocal rank of reviewer-approved concept roots at 1, 5, and
  20;
- domain, vocabulary, active-status, and standard/classification correctness;
- retrieval provenance completeness and latency;
- reviewer burden: candidates inspected and review actions required;
- downstream technical Capr/Circe validation only after a separate explicit
  human policy approval.

Embeddings advance beyond evaluation only if they improve a predeclared measure
on held-out cases without increasing unsafe domain/classification errors or
weakening the review gate.

## Next executable decision

The next implementation task is a read-only hierarchy contract probe against
Groundworkers, not an ACP behavior change. It should produce a versioned tool
schema snapshot and one bounded non-PHI hierarchy response. Only then should a
separate hierarchy provider mode be designed in code.
