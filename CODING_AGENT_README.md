# Coding Agent Summary (OHDSI-Study-Agent)

This file is a concise handoff for future coding-agent sessions.

## Current Product Story

The clearest implemented stories in this repo are:

- phenotype recommendation and improvement for target/outcome cohort selection
- Keeper-assisted concept generation, profile extraction, and row adjudication for phenotype validation

The top-level [README.md](/ai-agent/HadesProject/OHDSI-Study-Agent/README.md:1) now reflects that narrower scope. Do not describe the repo as if the full future service catalog is already implemented.

## Repo Layout

- `acp_agent/`: ACP server and user-facing flow orchestration
- `mcp_server/`: MCP tool server, prompt bundles, retrieval, vocabulary, and Keeper tooling
- `core/`: pure deterministic logic and validation
- `R/OHDSIAssistant/`: R Strategus shell
- `docs/`: primary documentation, including testing, roadmap, Keeper specs, and moved legacy docs
- `demo/`: sample artifacts and cohort JSON files

Recent doc moves to remember:

- `docs/TEST-RUN.md`
- `docs/GIT-GUIDE.md`
- `docs/KEEPER-EXPANSION-PLAN.md`

## Architecture

### ACP

- HTTP server in `acp_agent/study_agent_acp/server.py`
- exposes `/health`, `/tools`, `/tools/call`, `/services`, and flow endpoints under `/flows/*`
- orchestrates MCP tool calls and LLM calls
- safe-summary wrapping happens in ACP when using `/tools/call`

### MCP

- tool contracts and deterministic outputs live under `mcp_server/study_agent_mcp/tools/`
- can run via stdio or HTTP
- owns phenotype index access, vocabulary search tools, Keeper prompt bundles, and Keeper extraction tooling

### Core

- reusable validation and filtering logic in `core/study_agent_core/`
- no network or IO assumptions

## Key Safety Rule

- No PHI/PII should be sent to LLMs.
- `phenotype_validation_review` must go through Keeper sanitization before prompt construction.
- `keeper_profiles_generate` is deterministic only; downstream LLM use still requires the sanitization gate.

## Implemented ACP Flows

The currently exposed ACP flow endpoints are:

- `phenotype_recommendation`
- `phenotype_recommendation_advice`
- `phenotype_improvements`
- `phenotype_intent_split`
- `cohort_methods_intent_split`
- `concept_sets_review`
- `cohort_critique_general_design`
- `keeper_concept_sets_generate`
- `keeper_profiles_generate`
- `phenotype_validation_review`

For the source of truth, check:

- [docs/SERVICE_REGISTRY.yaml](/ai-agent/HadesProject/OHDSI-Study-Agent/docs/SERVICE_REGISTRY.yaml:1)
- [acp_agent/study_agent_acp/server.py](/ai-agent/HadesProject/OHDSI-Study-Agent/acp_agent/study_agent_acp/server.py:1)

## Demo Shell

There is now a small ACP-backed demo CLI:

- entrypoint: `study-agent-demo-shell`
- module: [acp_agent/study_agent_acp/demo_shell.py](/ai-agent/HadesProject/OHDSI-Study-Agent/acp_agent/study_agent_acp/demo_shell.py:1)
- output dir default: `./demo-shell-output/`
- history file: `demo-shell-output/.study-agent-demo-history`

Current slash commands:

- `/phenotype-intent-split`
- `/phenotype-recommend`
- `/vocab-search-standard`
- `/vocab-phoebe-related`
- `/keeper-generate-concepts`
- `/keeper-review-row`
- `/services`
- `/help`
- `/quit`

Important limitation:

- `/keeper-review-row` currently reviews a JSON row or a row selected from a JSON `rows[]` payload on disk.
- it can use a Keeper concepts file to infer `disease_name`, but the ACP review flow itself still only consumes `disease_name` plus `keeper_row`
- there is not yet a matching `/keeper-generate-profiles` shell command

If future work extends the shell, adding `/keeper-generate-profiles` is the most natural next step.

## Packaging / Entry Points

Current console scripts from [pyproject.toml](/ai-agent/HadesProject/OHDSI-Study-Agent/pyproject.toml:1):

- `study-agent-mcp`
- `study-agent-acp`
- `study-agent-demo-shell`

After changing entrypoints or package layout, rerun:

```bash
pip install -e .
```

## Common Run Setup

Recommended cross-platform-stable local setup is MCP over HTTP plus ACP over HTTP:

```bash
export MCP_TRANSPORT=http
export MCP_HOST=127.0.0.1
export MCP_PORT=8790
export MCP_PATH=/mcp
study-agent-mcp
```

Then:

```bash
export STUDY_AGENT_MCP_URL="http://127.0.0.1:8790/mcp"
export STUDY_AGENT_HOST=127.0.0.1
export STUDY_AGENT_PORT=8765
study-agent-acp
```

Then:

```bash
study-agent-demo-shell
```

## Important Environment Variables

LLM:

- `LLM_API_URL`
- `LLM_API_KEY`
- `LLM_MODEL`
- `LLM_TIMEOUT`
- `LLM_LOG`
- `LLM_USE_RESPONSES`

Embeddings / phenotype retrieval:

- `EMBED_URL`
- `EMBED_MODEL`
- `EMBED_API_KEY`
- `PHENOTYPE_INDEX_DIR`
- `PHENOTYPE_DENSE_WEIGHT`
- `PHENOTYPE_SPARSE_WEIGHT`

ACP / MCP:

- `STUDY_AGENT_HOST`
- `STUDY_AGENT_PORT`
- `STUDY_AGENT_MCP_URL`
- `STUDY_AGENT_MCP_COMMAND`
- `STUDY_AGENT_MCP_ARGS`
- `STUDY_AGENT_MCP_TIMEOUT`
- `ACP_TIMEOUT`

Demo shell:

- `STUDY_AGENT_DEMO_ACP_URL`
- `STUDY_AGENT_DEMO_OUTPUT_DIR`

Vocabulary / Phoebe providers:

- `VOCAB_SEARCH_PROVIDER`
- `VOCAB_SEARCH_URL`
- `PHOEBE_PROVIDER`

## Testing

Useful current tests/docs:

- [docs/TESTING.md](/ai-agent/HadesProject/OHDSI-Study-Agent/docs/TESTING.md:1)
- [tests/test_demo_shell.py](/ai-agent/HadesProject/OHDSI-Study-Agent/tests/test_demo_shell.py:1)
- pytest markers: `core`, `acp`, `mcp`

Small targeted checks that are cheap to run:

```bash
pytest -q tests/test_demo_shell.py
python -m study_agent_acp.demo_shell --help
```

## High-Value Docs

- [README.md](/ai-agent/HadesProject/OHDSI-Study-Agent/README.md:1)
- [docs/TESTING.md](/ai-agent/HadesProject/OHDSI-Study-Agent/docs/TESTING.md:1)
- [docs/PHENOTYPE_RECOMMENDATION_DESIGN.md](/ai-agent/HadesProject/OHDSI-Study-Agent/docs/PHENOTYPE_RECOMMENDATION_DESIGN.md:1)
- [docs/PHENOTYPE_VALIDATION_REVIEW.md](/ai-agent/HadesProject/OHDSI-Study-Agent/docs/PHENOTYPE_VALIDATION_REVIEW.md:1)
- [docs/KEEPER_INTERFACE_SPEC.md](/ai-agent/HadesProject/OHDSI-Study-Agent/docs/KEEPER_INTERFACE_SPEC.md:1)
- [docs/STRATEGUS_SHELL.md](/ai-agent/HadesProject/OHDSI-Study-Agent/docs/STRATEGUS_SHELL.md:1)
- [docs/INCIDENCE_WORKFLOW.md](/ai-agent/HadesProject/OHDSI-Study-Agent/docs/INCIDENCE_WORKFLOW.md:1)
- [docs/ROADMAP.md](/ai-agent/HadesProject/OHDSI-Study-Agent/docs/ROADMAP.md:1)

## Practical Notes For Future Coding Agents

- Prefer documenting implemented flows over speculative services.
- When updating docs, check whether files have moved under `docs/` before adding new references.
- The demo shell is intentionally thin; keep it as an ACP client unless there is a strong reason to duplicate ACP logic.
- For user-facing shell improvements, prefer low-complexity terminal upgrades first, such as readline/history/completion, before introducing a larger TUI dependency.
- Do not assume recommendation responses are a flat list; ACP wraps them in a `recommendations` object.
- The worktree may contain unrelated scratch files such as editor temp files or `demo-shell-output/`; do not delete them unless asked.
