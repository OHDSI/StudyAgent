# Groundworkers pilot handoff — 2026-09-11

## Current checkpoint

The review-gated Groundworkers pilot is on `experiment/groundworkers-pilot`.
It has three intentionally separate candidate-retrieval modes:

| Mode | Purpose | Embeddings |
| --- | --- | --- |
| `groundworkers` | Precision-oriented lexical grounding | Disabled |
| `groundworkers_hierarchy` | Explicit-anchor, depth-one hierarchy evidence | Disabled |
| `groundworkers_embedding` | Proposed lexical-miss semantic fallback | Not implemented |

All modes preserve the `phenotype_make_computable` review boundary: no scope
inference, concept-set policy, approval, or Capr/Circe emission occurs during
retrieval.

The lexical comparison is frozen at tag
`groundworkers-lexical-pilot-v0.1.0`; the hierarchy checkpoint is frozen at
`groundworkers-hierarchy-pilot-v0.2.0`. The latter tag predates the final
embedding design notes listed below.

## Evidence recorded so far

- Lexical Groundworkers grounding returned narrow active, standard concepts for
  type 2 diabetes, chronic kidney disease, and RxNorm lisinopril, where the
  baseline retrieval returned no candidates or broad bounded slices.
- Lexical mode intentionally returned no candidates for the `ACE inhibitor`
  drug-class query. Baseline class fallback produced ATC/EphMRA classification
  candidates; that is the motivation for the separately opt-in hierarchy mode.
- Hierarchy mode passed a positive cystitis control: a `Disorder of bladder`
  anchor (`201337`) produced cystitis (`195588`) with explicit parent ID and
  independently verified depth-one ancestor evidence.
- An invalid domain/vocabulary anchor failed closed. A semantic negative using
  the acute-myocardial-infarction anchor eventually returned zero candidates,
  but took several minutes through the vocabulary graph.

These are retrieval observations, not clinical validation or approved concept
sets.

## Immediate next gate: vocabulary-query performance

Do this before creating vectors, enabling embeddings, or broadening hierarchy
testing. It needs the vocabulary database owner/DBA; the pilot account must
not change the shared `vocabulary` schema.

1. Capture representative `EXPLAIN (ANALYZE, BUFFERS)` plans for lexical
   concept/synonym searches and the slow hierarchy-negative request.
2. Record vocabulary release, PostgreSQL version, table sizes, existing
   indexes, relevant statistics freshness, and service/ACP timeouts.
3. Have the DBA assess targeted index/selectivity opportunities for
   `concept`, `concept_synonym`, and `concept_ancestor`, plus required
   `VACUUM`/`ANALYZE` maintenance.
4. Re-run the positive and semantic-negative hierarchy controls and preserve
   latency plus full ACP provenance. A timeout or transport failure remains
   `unavailable`, never a zero-result.
5. Document any DBA-owned changes and establish a bounded latency budget before
   the embedding phase.

See `experiments/groundworkers/HIERARCHY_PROVIDER_CONTRACT.md` for the detailed
performance boundary.

## Embedding evaluation plan, in order

The product policy is precision-first: exact label/synonym, full-text
label/synonym, embedding only after lexical miss, then constrained partial
matching. `include_embedding: true` permits the semantic rescue tier; it does
not mean vectors were used. Every lexical result must say
`used_embedding: false`; every embedding result must say `used_embedding: true`
and identify the corpus and model.

1. Freeze development and held-out phenotype cases *before* selecting corpus
   members. Predeclare held-out lexical-miss cases from the lexical-only
   comparison; their approved roots, review decisions, and source artifacts
   must never enter the development corpus.
2. Select the vector location and owner. Use an approved dedicated vector
   database or dedicated writable scratch schema/table, never the shared
   `vocabulary` schema. Confirm backup, access, and reset/retention handling.
3. Select the embedding model and immutable identity: model name, revision or
   digest, vector dimensions, distance metric, serving implementation/version,
   and inference settings. Do not use a mutable `latest` reference.
4. Instantiate a small development-only corpus manifest. Include only
   development lexical candidates, approved training roots, explicitly bounded
   ancestors/descendants/mappings, and deterministically mapped phenotype-source
   evidence. Every row needs a provenance source and selection rule. Exclude
   full-vocabulary text, PHI, notes, row-level data, and unbounded expansions.
5. Validate and freeze the manifest. Its hash, collection/table identifier,
   vocabulary version, model identity, and vector-store version define one
   immutable corpus revision. Any change creates a new collection and hash.
6. Bootstrap vectors only for that manifest and run provider-level smoke tests:
   lexical hit (must not use embeddings), lexical miss with semantic candidate,
   missing/mismatched corpus, vector-store unavailable, and timeout. All error
   states must fail closed with structured provenance.
7. Add the proposed review-only ACP mode
   `concept_build_mode: "groundworkers_embedding"`. Require an explicit
   `embedding_corpus` identity, `concept_review_mode: "required"`, empty
   `concept_sets`, and candidate cap 20. Never silently substitute a corpus or
   enable embeddings in existing lexical/hierarchy modes.
8. Evaluate on the frozen held-out set against lexical-only and hierarchy modes.
   Record root recall and reciprocal rank at 1/5/20, domain/vocabulary/standard
   correctness, candidate count, latency, provenance completeness, and reviewer
   burden. Technical Capr/Circe validation remains a later, separately approved
   step.
9. Advance only if a predeclared held-out measure improves without unsafe
   domain/classification errors, hidden availability failures, or weakened
   review gates. Otherwise retain lexical/hierarchy modes and do not enlarge the
   corpus.

The detailed capability contract is
`experiments/groundworkers/EMBEDDING_PROVIDER_CONTRACT.md`. The broader matrix
and evidence are in `experiments/groundworkers/EVALUATION_PLAN.md`.

## Decisions still needed before implementation

- The DBA-approved vector-store location (dedicated database versus approved
  scratch schema/table) and its owning account.
- The embedding model and immutable revision/digest.
- The frozen development/held-out case lists and evaluation labels.
- The corpus-manifest schema fields and its first bounded selection rules.
- Latency/availability thresholds for accepting the vector and hierarchy paths.

Do not start vectorization until these decisions and the performance gate are
recorded.
