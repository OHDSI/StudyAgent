# Coding Agent Summary (OHDSI-Study-Agent)

This file is a concise handoff for future coding-agent sessions.

## Project Goal
Build an OHDSI Study Design Assistant that provides a “coding agent” experience for designing and executing observational studies. The system uses ACP for orchestration/UX and MCP for tool contracts, retrieval, and prompt assets. ACP can be used by R, Python, CLI, or other environments.

## Architecture
- **ACP (Agent Client Protocol)**
  - Provides interaction policy, confirmations, and safe summaries.
  - Orchestrates MCP tool calls and remote LLM calls.
  - Located in `acp_agent/`.
- **MCP (Model Context Protocol)**
  - Owns tool contracts, retrieval, prompt bundles, and deterministic tool outputs.
  - Runs locally (stdio or HTTP) and can be reused outside ACP.
  - Located in `mcp_server/`.
- **Core**
  - Pure/deterministic logic and schema validation.
  - Located in `core/`.

## Key Decisions
- **No PHI/PII to LLMs.**
  - Row-level data must never be sent to remote LLMs.
  - For Keeper review, MCP sanitizes and fail‑closes if PHI is detected.
- **MCP owns phenotype index** (FAISS + sparse). ACP does not manage index.
- **Embeddings use OpenAI-compatible endpoint**
  - Env: `EMBED_URL`, `EMBED_MODEL`, `EMBED_API_KEY`.
  - Previously “OLLAMA” names were generalized.
- **LLM API is OpenAI-compatible**
  - Env: `LLM_API_URL`, `LLM_API_KEY`, `LLM_MODEL`.
  - `LLM_USE_RESPONSES=1` uses Responses API payload (not related to MCP tool use).
- **ACP server host/port configurable**
  - `STUDY_AGENT_HOST`, `STUDY_AGENT_PORT`.
- **Signal handling**
  - ACP handles SIGINT/SIGTERM and closes MCP to avoid zombies.

## Implemented ACP Flows
- `phenotype_recommendation`
- `phenotype_recommendation_advice`
- `phenotype_improvements` (one cohort at a time; ACP injects ids)
- `concept-sets-review`
- `cohort-critique-general-design`
- `phenotype_validation_review`

ACP also exposes `/services` endpoint (hybrid: registry + ACP runtime list).

## New Advisory Flow
- `phenotype_recommendation_advice` is used when initial candidates are not acceptable.
- Prompt bundle stored in MCP; ACP uses LLM to return advice, next steps, questions.

## Phenotype Indexing
- Built with `mcp_server/scripts/build_phenotype_index.py`.
- Index stored locally and accessed by MCP.
- Metadata from CSV; cohort JSON from OHDSI cohort definitions.
- Docs: `docs/PHENOTYPE_INDEXING.md`.

## Strategus Shell (R)
- Entry: `OHDSIAssistant::runStrategusIncidenceShell()`.
- Interactive “shell” UX, not just a batch script.
- Writes outputs and scripts under `demo-strategus-cohort-incidence/`.
- Can apply phenotype improvements interactively (per cohort).
- Uses candidate windowing (offset) if no acceptable recommendations.
- Falls back to advisory flow if still no acceptable candidates.
- Outputs a session summary and saves `outputs/study_agent_state.json`.
- Docs: `docs/STRATEGUS_SHELL.md`.

### Generated Scripts
- `03_generate_cohorts.R`
- `04_keeper_review.R`
- `05_diagnostics.R`
- `06_incidence_spec.R`

Each script includes a DB config loader from `strategus-db-details.json` in the working directory:
```json
{
  "DB_USER": "",
  "DB_PASS": "",
  "DB_SERVER": "",
  "DB_PORT": "",
  "DB_DRIVER_PATH": "",
  "extraSettings": ""
}
```

## Service Registry
- `docs/SERVICE_REGISTRY.yaml` is used by `/services`.
- ACP marks entries as implemented and appends missing ACP flows.

## Testing & Tasks
- Pytest markers: `core`, `acp`, `mcp`.
- `doit list_services` auto-starts ACP if not running.
- Smoke tests start ACP + MCP automatically.
- `doit smoke_phenotype_recommend_flow` and others.

## Notable Issues/Resolutions
- ACP/MCP stdio shutdown could emit cancel-scope errors. ACP now handles SIGINT/SIGTERM to close MCP.
- LLM responses sometimes return wrong cohort ids; core `phenotype_improvements` remaps when only one cohort provided.

## Useful Docs
- `docs/PHENOTYPE_RECOMMENDATION_DESIGN.md`
- `docs/PHENOTYPE_VALIDATION_REVIEW.md`
- `docs/PHENOTYPE_INDEXING.md`
- `docs/STRATEGUS_SHELL.md`
- `docs/TESTING.md`

## Current Environment Variables (common)
- `LLM_API_URL`, `LLM_API_KEY`, `LLM_MODEL`, `LLM_TIMEOUT`, `LLM_LOG`, `LLM_USE_RESPONSES`
- `EMBED_URL`, `EMBED_MODEL`, `EMBED_API_KEY`
- `PHENOTYPE_INDEX_DIR`, `PHENOTYPE_DENSE_WEIGHT`, `PHENOTYPE_SPARSE_WEIGHT`
- `STUDY_AGENT_HOST`, `STUDY_AGENT_PORT`
- `STUDY_AGENT_MCP_COMMAND`, `STUDY_AGENT_MCP_ARGS`

