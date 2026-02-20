**Overview**
This document defines the `phenotype_recommendation` capability in the ACP + MCP architecture. The MCP service owns the phenotype index on local disk and exposes read-only retrieval tools. ACP only orchestrates LLM calls and tool invocations, and core remains pure/deterministic for validation and filtering.

**Goals**
1. Move recall outside the LLM by using a hybrid retrieval index.
2. Send the LLM only a small candidate set for ranking and justification.
3. Keep index ownership inside MCP for air-gapped deployment.
4. Support regular updates from OHDSI Phenotype Library exports.

**Non-Goals**
1. No direct DB/OMOP access in MCP tools.
2. No write or edit operations exposed through MCP tools.
3. No heavy external infrastructure dependencies for sparse search.

**Components**
1. MCP Retrieval Layer
   - Owns index storage on local disk.
   - Exposes search and preview tools.
2. ACP Orchestration
   - Calls MCP tools to retrieve candidates.
   - Calls LLM to rank and justify.
   - Validates LLM output via core.
3. Core Validation
   - `phenotype_recommendations(...)` merges or filters LLM results against the candidate set.

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
Default root is `PHENOTYPE_INDEX_DIR` or `data/phenotype_index`.
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
5. Return top-K compact candidates to ACP/LLM.

**MCP Tools (Read-Only)**
1. `phenotype_search(query, top_k=20)`
2. `phenotype_fetch_summary(cohortId)`
3. `phenotype_fetch_definition(cohortId, truncate=true)`
4. `phenotype_list_similar(cohortId, top_k=10)`
5. `phenotype_prompt_bundle(task)` (returns overview/spec/output_schema)

**ACP Orchestration**
1. User submits study intent to ACP.
2. ACP calls `phenotype_search` to get top-K candidates.
3. ACP calls `phenotype_prompt_bundle` to fetch prompt assets.
4. ACP calls LLM with candidates for ranking and justification.
5. ACP validates with `core.phenotype_recommendations(...)`.

Candidate selection:
1. ACP truncates the candidate list before the LLM using `LLM_CANDIDATE_LIMIT` or per-request `candidate_limit`.

**Phenotype Improvements Scope**
1. The improvements flow reviews one phenotype definition at a time.
2. If multiple cohorts are provided, ACP uses the first cohort only.
3. If the cohort JSON has no `id`, ACP injects a synthetic `id` for validation only and does not write it back.

**LLM Formats**
1. Default: OpenAI Chat Completions payload (`/v1/chat/completions`-style).
2. Optional: OpenAI Responses payload (`/v1/responses`-style) enabled with `LLM_USE_RESPONSES=1`.
3. This setting only changes request/response formatting for the LLM API; it does not affect MCP tool usage.

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
11. `LLM_LOG` (default `0`)
12. `LLM_DRY_RUN` (default `0`)
13. `LLM_USE_RESPONSES` (default `0`) selects OpenAI Responses API format instead of Chat Completions. It does not affect MCP tool use.
14. `LLM_CANDIDATE_LIMIT` (default `10`)

**Risks and Mitigations**
1. Missing dependencies for FAISS
   - Mitigation: allow sparse-only mode with explicit warning.
2. Inconsistent or missing metadata fields
   - Mitigation: robust fallbacks when building catalog rows.
3. Large updates
   - Mitigation: incremental caching by text hash, batch embedding.
