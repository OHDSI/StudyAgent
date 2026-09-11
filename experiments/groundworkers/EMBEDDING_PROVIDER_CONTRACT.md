# Proposed Groundworkers targeted-embedding contract v0

Status: design only. No embedding model, vector collection, ACP request mode, or
vocabulary-schema change is authorized by this document.

## Goal

Evaluate whether a small, reproducible, non-PHI concept corpus improves
review-candidate retrieval for held-out phenotype definitions. Embedding results
remain unreviewed retrieval evidence and cannot create concept-set policy or
cohort logic.

## Preconditions

1. Complete the DBA-owned query-plan and maintenance assessment in
   [HIERARCHY_PROVIDER_CONTRACT.md](HIERARCHY_PROVIDER_CONTRACT.md#vocabulary-query-performance-follow-up).
   Slow vocabulary queries must not be obscured by a new vector layer.
2. Freeze development and held-out phenotype cases before corpus selection.
   Held-out approved roots, reviewer decisions, and source artifacts cannot
   enter the development corpus.
3. Select a dedicated writable vector location outside the shared `vocabulary`
   schema. The current pilot may use a separately owned vector database or a
   dedicated writable scratch schema/table only after its owner approves it.
4. Record the embedding model identifier, immutable revision or digest,
   dimensions, metric, vector-store implementation/version, corpus manifest
   hash, and collection/table identifier. Mutable model labels are insufficient.

## Corpus v0

Create one immutable manifest validated by
`embedding-corpus-manifest.schema.json` before vectorization. Start with a small
development-only corpus containing only:

- candidates returned by baseline and Groundworkers lexical searches for frozen
  development cases;
- reviewer-approved roots from training cases;
- explicitly bounded ancestors, descendants, and standard mappings, with depth
  and source recorded; and
- phenotype-source code evidence only after deterministic vocabulary mapping.

Every row needs a provenance source and selection rule. Do not include full OMOP
vocabulary text, patient data, notes, row-level records, or unbounded graph
expansion. A changed model, rule, concept list, or vocabulary release creates a
new manifest hash and vector collection.

## Precision-first provider policy

The pinned Groundworkers service uses the intended precision-first tier order:
exact label/synonym, full-text label/synonym, embedding, then partial matching
when the search space is sufficiently narrowed. It stops at the first tier that
yields candidates. This is appropriate for review-gated phenotype work: a
terminology-aligned clinical term should first return its closest lexical
terminology evidence before semantic expansion is considered.

`include_embedding: true` therefore means "embedding is available as a semantic
rescue after lexical miss", not "embedding retrieval was performed". A lexical
hit must report `used_embedding: false`; an embedding-stage result must report
`used_embedding: true` and identify the corpus/model provenance.

The v0 embedding evaluation uses this lexical-miss fallback behavior. Predeclare
its held-out cases from lexical-only runs that returned zero candidates, then
compare the precision-first embedding-enabled result with the lexical-only
result. This evaluates the intended user benefit: a clinically meaningful term
that is poorly aligned to terminology labels may receive bounded semantic
candidates without broadening terminology-aligned requests.

An embedding-only or explicit tier-selection capability may be useful later for
provider diagnostics, but it is not required for the ACP pilot and must not
replace the precision-first production policy.

## Proposed ACP boundary after capability verification

A future top-level request may use:

```json
{
  "concept_build_mode": "groundworkers_embedding",
  "embedding_corpus": {
    "manifest_sha256": "<immutable manifest hash>",
    "collection_id": "<immutable vector collection identifier>",
    "model_identifier": "<model identifier>",
    "model_revision_or_digest": "<immutable revision or digest>"
  }
}
```

It must remain `concept_review_mode: "required"`, use empty `concept_sets`, cap
candidates at 20, and preserve the full lexical/embedding tier provenance. The
request must fail unavailable if its named corpus or model identity is missing,
mismatched, incomplete, or unavailable. It must not silently use a different
corpus, invoke embeddings for the lexical or hierarchy modes, or fall back to
an unrecorded retrieval mode.

## Evaluation and stop conditions

Evaluate lexical-only, hierarchy, and the chosen embedding mode separately on
the same held-out requests. Record recall and reciprocal rank at 1, 5, and 20,
domain/vocabulary/standard-status correctness, latency, candidate count,
provenance completeness, and reviewer burden.

Advance only when a predeclared held-out measure improves without increasing
unsafe domain/classification errors, obscuring provider availability, or
weakening explicit review gates. Otherwise retain lexical/hierarchy modes and
do not populate a larger corpus.
