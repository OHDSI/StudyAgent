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

## Provider capability gap

The pinned Groundworkers service currently places `EmbeddingResolver` after the
exact-label and full-text tiers. It stops after the first tier yielding results.
Consequently, `include_embedding: true` means "embedding permitted after lexical
miss", not "embedding retrieval was performed"; a lexical hit will report
`used_embedding: false`.

Before ACP integration, choose and verify one of these evaluation modes:

1. **Embedding-required**: a provider-supported embedding-only/tier-selection
   request that cannot return lexical candidates; preferred for a direct
   lexical-versus-embedding comparison.
2. **Lexical-miss fallback**: retain the existing tier order, but evaluate only
   predeclared cases where the lexical-only run has zero candidates. Provenance
   must report `used_embedding: true` and the embedding tier/model/corpus.

Do not add `concept_build_mode: "groundworkers_embedding"` until the chosen mode
is supported by the pinned provider and represented in response provenance.

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
