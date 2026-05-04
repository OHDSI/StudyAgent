**Overview**
This document defines the `phenotype_recommendation` capability in the ACP + MCP architecture. The MCP service owns the phenotype index on local disk and exposes read-only retrieval tools. ACP orchestrates retrieval, multiple LLM calls, deterministic shortlist enforcement, and final response assembly. Core remains pure and deterministic for schema validation and final filtering.

**Goals**
1. Move initial recall outside the LLM by using a hybrid retrieval index.
2. Keep the LLM focused on intent interpretation, shortlist planning, and explanation generation rather than open-ended search.
3. Keep index ownership inside MCP for air-gapped deployment.
4. Preserve deterministic safeguards in ACP when LLM outputs are incomplete, stale, or inconsistent with candidate constraints.
5. Support regular updates from OHDSI Phenotype Library exports and CIPHER-derived phenotype catalogs.

**Non-Goals**
1. No direct DB/OMOP access in MCP tools.
2. No write or edit operations exposed through MCP tools.
3. No heavy external infrastructure dependencies for sparse search.
4. No unrestricted LLM authority to invent phenotype ids or override ACP shortlist constraints.

**Components**
1. MCP Retrieval Layer
   - Owns index storage on local disk.
   - Exposes search and preview tools.
   - Serves prompt bundles for phenotype recommendation tasks.
2. ACP Orchestration
   - Calls MCP retrieval tools.
   - Calls the LLM in staged interactions.
   - Applies deterministic rerank, gating, shortlist enforcement, and final selection.
3. Core Validation
   - `phenotype_recommendations(...)` validates final response shape and candidate grounding.
   - `phenotype_recommendation_plan(...)` validates planner outputs.
4. LLM Interaction Layer
   - Produces intent facets.
   - Produces shortlist planning rationales.
   - Produces final plan/explanations for deterministic selections.

**Index Data Model**
Each phenotype is stored as a compact JSON document (one line per document):
1. `cohortId`
2. `name`
3. `short_description`
4. `tags`
5. `ontology_keys`
6. `signals`
7. `logic_features`
8. `pop_keywords`
9. `source_meta`

**Index Directory Layout**
Default root is `PHENOTYPE_INDEX_DIR` or repo-relative `data/phenotype_index` (resolved from the MCP package location).
1. `catalog.jsonl` (compact phenotype docs)
2. `sparse_index.pkl` (pure-Python BM25-style index)
3. `dense.index` (FAISS index)
4. `meta.json` (index metadata)
5. `definitions/` (optional raw cohort JSON by `cohortId.json`)

**Embedding Strategy**
1. Embed only `name + short_description + pop_keywords`.
2. Use the local embedding API:
   - URL: `EMBED_URL` (default `http://localhost:3000/ollama/api/embed`)
   - Model: `EMBED_MODEL` (default `qwen3-embedding:4b`)
   - Key: `EMBED_API_KEY` (optional)
3. Cache embeddings by `(cohortId, input_text_hash)` to avoid recompute.

**Sparse Retrieval Strategy**
1. Tokenize text using a simple regex tokenizer.
2. Build an inverted index with term frequencies.
3. Score with a lightweight BM25-style formula.
4. Store postings and doc lengths in `sparse_index.pkl`.

**Hybrid Retrieval Flow**
1. Embed the query text (dense).
2. Run dense search (FAISS) for top-N.
3. Run sparse search (BM25) for top-N.
4. Merge scores using weighted sum or RRF.
5. Return top-K compact candidates to ACP.

**MCP Tools (Read-Only)**
1. `phenotype_search(query, top_k=20)`
2. `phenotype_fetch_summary(cohortId)`
3. `phenotype_fetch_definition(cohortId, truncate=true)`
4. `phenotype_list_similar(cohortId, top_k=10)`
5. `phenotype_prompt_bundle(task)` (returns overview/spec/output_schema)
6. `phenotype_index_status()` (returns index path + file existence for preflight checks)

**ACP Orchestration**
The phenotype recommendation flow is staged.

1. Candidate retrieval
   - ACP receives `study_intent`.
   - ACP calls `phenotype_search` to get top-K candidates.
   - ACP truncates the candidate list before LLM use with `LLM_CANDIDATE_LIMIT` or request-level `candidate_limit`.
   - ACP supports `candidate_offset` to request later windows from MCP `phenotype_search`.

2. Intent interpretation
   - ACP fetches the prompt bundle for `phenotype_recommendation_intent_facets`.
   - ACP calls the LLM to produce structured `intent_facets`.
   - ACP normalizes the result in `_effective_intent_facets(...)`.
   - ACP may normalize optional `clinical_topic_aliases` and alternate alias fields if present.
   - In practice, the LLM may either emit aliases or rewrite `condition_or_topic` into more standard clinical phrasing directly.

3. Deterministic planning rerank
   - ACP hydrates planning candidates with phenotype summaries.
   - ACP computes metadata-based rerank priorities in `_candidate_metadata_priority(...)`.
   - Rerank considers topic alignment, context alignment, and validated alias overlap.
   - Rerank reasons may include:
     - `topic_primary`
     - `topic_context`
     - `dynamic_clinical_alias_match`
     - `dynamic_clinical_alias_context`
     - `context_without_primary`
     - `topic_mismatch`

4. LLM shortlist planning
   - ACP fetches the prompt bundle for `phenotype_recommendation_plan`.
   - ACP sends a compact, reranked planning candidate set to the LLM.
   - The planner may suggest shortlist ids and reasoning notes.
   - Planner output is validated through `phenotype_recommendation_plan(...)`.

5. Deterministic shortlist enforcement
   - ACP enforces the shortlist against the reranked pool in `_enforce_shortlist_against_rerank(...)`.
   - This is the main safety layer between planner output and final recommendations.

6. Final deterministic recommendation selection
   - ACP hydrates the enforced shortlist.
   - Final phenotype ids are selected deterministically from the enforced shortlist.
   - ACP fetches the prompt bundle for `phenotype_recommendations`.
   - The final LLM no longer chooses ids; it only contributes plan/explanations/confidence for already-selected rows.
   - ACP validates and then merges LLM explanations with deterministic defaults.

7. Core validation and response assembly
   - ACP validates the final response through `phenotype_recommendations(...)`.
   - ACP includes diagnostics showing retrieval, LLM, rerank, shortlist enforcement, and deterministic final-selection details.

**Shortlist Enforcement Rules**
Shortlist enforcement is intentionally stricter than raw retrieval or planner output.

1. Candidate pool narrowing
   - ACP defines a strict rerank pool near the top of the reranked list.
   - Planner-chosen ids outside the strict pool are dropped.

2. Diagnosis-intent gating
   - Withdrawn phenotypes are blocked.
   - Procedure/surgery/repair/post-op phenotypes are blocked for non-procedure diagnosis intents.
   - Narrow hospitalization/exacerbation subtypes are blocked for plain diagnosis intents unless hospitalization is explicitly requested.

3. Quality-threshold fill behavior
   - Once at least one defensible candidate exists, later candidates are skipped if they are only `topic_mismatch` or `context_without_primary` without a primary-topic match.
   - This allows ACP to return fewer than `max_results` when only one or two candidates are trustworthy.

4. Plain diagnosis fill guard
   - For non-hospitalization, non-procedure diagnosis intents, weaker non-diagnosis-class candidates are suppressed in later slots.

5. Dedupe behavior
   - Dedupe is intentionally narrow and currently applies only to a subset of diagnosis-intent scenarios.
   - Dedupe backfill is allowed only when dedupe itself removed a duplicate.
   - Blocked candidates are never reintroduced merely to fill the shortlist.

6. Empty-shortlist behavior
   - If all top strict-pool candidates are blocked or unsafe, ACP may return an empty shortlist and therefore no final recommendations.
   - This is preferred over returning known-bad procedure or mismatch fallbacks.

**Planning Notes and Explanations**
1. `planning.reasoning_notes` are rebuilt from the enforced shortlist rather than copied directly from the planner.
2. This prevents stale notes from mentioning candidates that were later dropped or blocked.
3. Final explanations are partly LLM-supplied and partly defaulted when the final LLM omits or mishandles some selected ids.

**Deterministic Final Selection**
1. Final recommendation ids come only from the enforced shortlist.
2. The final LLM cannot add ids outside the shortlist.
3. ACP records final-selection diagnostics including:
   - matched LLM ids
   - invalid LLM ids
   - duplicate LLM ids
   - ids that fell back to deterministic default justification
4. This makes the final output stable even when the final LLM response is partial or malformed.

**Phenotype Improvements Scope**
1. The improvements flow reviews one phenotype definition at a time.
2. If multiple cohorts are provided, ACP uses the first cohort only.
3. If the cohort JSON has no `id`, ACP injects a synthetic `id` for validation only and does not write it back.

**Prompt Assets and LLM Formats**
1. Prompt content is served via MCP prompt bundles by task.
2. The phenotype recommendation flow currently uses separate prompt assets for:
   - `phenotype_recommendation_intent_facets`
   - `phenotype_recommendation_plan`
   - `phenotype_recommendations`
3. Default API format: OpenAI Chat Completions payload (`/v1/chat/completions`-style).
4. Optional API format: OpenAI Responses payload (`/v1/responses`-style) enabled with `LLM_USE_RESPONSES=1`.
5. This setting changes LLM API formatting only; it does not affect MCP tool usage.

**Diagnostics**
Diagnostics are part of the implementation, not just debugging convenience.

1. Retrieval and MCP timing
   - tool timings and candidate counts
2. LLM diagnostics
   - request/response status, schema checks, missing keys, parse stage
3. Planning rerank diagnostics
   - normalized intent facets
   - reranked candidates with per-row reasons
   - shortlist enforcement decisions
4. Final deterministic diagnostics
   - selected ids
   - matched/defaulted ids
   - invalid or duplicate LLM ids

These diagnostics are used both for development and for evaluating recommendation quality regressions.

**Update and Reindex**
1. MCP exposes `POST /phenotypes/reindex` for manual refresh.
2. Index build script accepts CSV metadata + JSON cohort definitions.
3. Regular updates are expected; rebuild is safe and idempotent.

**Configuration**
1. `PHENOTYPE_INDEX_DIR` (default `data/phenotype_index`)
2. `EMBED_URL` (default `http://localhost:3000/ollama/api/embed`)
3. `EMBED_MODEL` (default `qwen3-embedding:4b`)
4. `EMBED_API_KEY` (optional)
5. `PHENOTYPE_DENSE_WEIGHT` (default `0.6`)
6. `PHENOTYPE_SPARSE_WEIGHT` (default `0.4`)
7. `LLM_API_URL` (default `http://localhost:3000/api/chat/completions`)
8. `LLM_API_KEY` (required for LLM calls)
9. `LLM_MODEL` (default `agentstudyassistant`)
10. `LLM_TIMEOUT` (default `180`)
11. `LLM_LOG` (default `0`) enables verbose LLM logging in the ACP logger (config, prompt, raw response).
12. `LLM_DRY_RUN` (default `0`)
13. `LLM_USE_RESPONSES` (default `0`) selects OpenAI Responses API format instead of Chat Completions. It does not affect MCP tool use.
14. `LLM_CANDIDATE_LIMIT` (default `10`)
15. `STUDY_AGENT_MCP_ONESHOT` (default `0`, forced on Windows) runs MCP in per-request oneshot mode to avoid stdio lockups.
16. `STUDY_AGENT_BASE_DIR` (optional) base directory for resolving relative paths (index dir, banner, outputs).
17. `STUDY_AGENT_THREADING` (default `1`) uses a threaded HTTP server for ACP. Set to `0` to disable.
18. `STUDY_AGENT_HOST` (default `127.0.0.1`)
19. `STUDY_AGENT_PORT` (default `8765`)
20. `STUDY_AGENT_MCP_CWD` (optional) working directory passed to MCP subprocesses. Use for stable relative paths.
21. `MCP_LOG_LEVEL` (default `INFO`) controls MCP logger verbosity (`DEBUG|INFO|WARN|ERROR|OFF`).
22. `STUDY_AGENT_MCP_URL` (optional) HTTP MCP endpoint. When set, ACP uses HTTP and ignores `STUDY_AGENT_MCP_COMMAND`.
23. `STUDY_AGENT_MCP_TOKEN` (optional) bearer token passed to MCP over HTTP.
24. `STUDY_AGENT_MCP_TIMEOUT` (default `30`) HTTP MCP request timeout in seconds.

**Known Current Limitations**
1. Sparse vs dense retrieval contribution is still under evaluation.
2. Some rare or molecularly specific oncology intents may have only blocked or context-only candidates in the strict pool.
3. Some medication-exposure intents still need stronger same-drug discrimination when multiple exposure phenotypes are nearby.
4. Some outpatient diagnosis cases can still surface weaker same-topic variants in later shortlist slots.

**Risks and Mitigations**
1. Missing dependencies for FAISS
   - Mitigation: allow sparse-only mode with explicit warning.
2. Inconsistent or missing metadata fields
   - Mitigation: robust fallbacks when building catalog rows.
3. Large updates
   - Mitigation: incremental caching by text hash, batch embedding.
4. LLM planner drift or malformed outputs
   - Mitigation: deterministic shortlist enforcement and deterministic final id selection.
5. Sparse candidate pools for niche intents
   - Mitigation: allow fewer recommendations rather than unsafe filler results.
