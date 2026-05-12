# AGENTS.md

## Project overview

This repository builds an agent-style interface for OHDSI study design work. The clearest implemented stories are:

- phenotype recommendation and improvement for target/outcome cohort selection
- Keeper-assisted concept generation, profile extraction, and row adjudication for phenotype validation
- R Strategus shells for incidence and cohort-method workflows

Do not describe the repo as if the full future service catalog is already implemented. The top-level [README.md](README.md) reflects the intended public product story.

## Repo layout

- `acp_agent/`: ACP server and user-facing flow orchestration
- `mcp_server/`: MCP tool server, prompt bundles, retrieval, vocabulary, and Keeper tooling
- `core/`: deterministic logic and validation
- `R/slashOhdsiAcpClient/`: R ACP client package and thin flow/action wrappers
- `R/slashOhdsiStrategusAssistant/`: R Strategus workflow package and shell entrypoints
- `docs/`: primary documentation and architecture notes
- `scripts/`: manual R demos and test entrypoints
- `tests/`: Python tests, smoke tests, and static assertions

## Setup commands

Python environment:

```bash
pip install -e ".[dev]"
```

Recommended local runtime setup is MCP over HTTP plus ACP over HTTP:

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

Useful R-side manual entrypoints:

- `scripts/test_strategus_incidence_plus_keeper.R`
- `scripts/demo_strategus_cohort_method.R`
- `scripts/demo_ohdsi_dialogue.R`

## Testing instructions

Useful broad docs and commands:

- [docs/TESTING.md](docs/TESTING.md)
- `pytest -m acp`
- `pytest -m mcp`

Small targeted checks that are cheap to run:

```bash
pytest -q tests/test_demo_shell.py
python -m study_agent_acp.demo_shell --help
```

For R-shell and generated-script changes, prefer focused static tests first. Relevant examples:

- `tests/test_incidence_shell_selection_state.py`
- `tests/test_keeper_generated_scripts.py`
- `tests/test_keeper_dialogue_integration_static.py`
- `tests/test_cohort_methods_generated_scripts.py`
- `tests/test_r_workflow_context_dialogue_wrapper.py`

If you change R demo scripts, run parse checks with `Rscript -e "parse(file='...')"` before finishing.

## Code style and implementation guidance

- Prefer documenting implemented flows over speculative services.
- When updating docs, check whether files have moved under `docs/` before adding new references.
- The demo shell is intentionally thin; keep it as an ACP client unless there is a strong reason to duplicate ACP logic.
- For user-facing shell improvements, prefer low-complexity terminal upgrades first before introducing a heavier TUI dependency.
- Do not assume recommendation responses are a flat list; ACP wraps them in a `recommendations` object.
- For static tests that read repo files, prefer the helper in `tests/_repo_paths.py` so tests can resolve the repo root from `STUDY_AGENT_REPO_ROOT` or from the test tree.

## Security and data handling

- No PHI/PII should *EVER* be sent to LLMs.
- `phenotype_validation_review` must go through Keeper sanitization before prompt construction.
- `keeper_profiles_generate` is deterministic only; any downstream LLM use still requires the sanitization gate.
- Treat row-level data handling as safety-critical. Preserve fail-closed behavior.

## Key flows and components

Implemented ACP flows include:

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

Sources of truth:

- [docs/SERVICE_REGISTRY.yaml](docs/SERVICE_REGISTRY.yaml)
- [acp_agent/study_agent_acp/server.py](acp_agent/study_agent_acp/server.py)
- [R/slashOhdsiStrategusAssistant/README.md](R/slashOhdsiStrategusAssistant/README.md)

## Important environment variables

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

## High-value docs

- [README.md](README.md)
- [docs/TESTING.md](docs/TESTING.md)
- [docs/WORKFLOW_PHENOTYPE_RECOMMENDATION.md](docs/WORKFLOW_PHENOTYPE_RECOMMENDATION.md)
- [docs/PHENOTYPE_VALIDATION_REVIEW.md](docs/PHENOTYPE_VALIDATION_REVIEW.md)
- [docs/SPEC_KEEPER_INTERFACE.md](docs/SPEC_KEEPER_INTERFACE.md)
- [docs/R_STRATEGUS_INCIDENCE_SHELL.md](docs/R_STRATEGUS_INCIDENCE_SHELL.md)
- [docs/R_STRATEGUS_COHORT_METHODS_SHELL.md](docs/R_STRATEGUS_COHORT_METHODS_SHELL.md)
- [docs/WORKFLOW_INCIDENCE.md](docs/WORKFLOW_INCIDENCE.md)
- [docs/ROADMAP.md](docs/ROADMAP.md)
- [docs/R_PACKAGE_ARCHITECTURE_PLAN.md](docs/R_PACKAGE_ARCHITECTURE_PLAN.md)

## Practical notes

- The worktree may contain unrelated scratch files such as editor temp files or `demo-shell-output/`; do not delete them unless asked.
- The user may validate R workflows from a parent `renv` one level above the repo. Do not modify or replace that parent `renv`.
- For shell test scripts, prefer the shared helper in `scripts/demo_setup.R` rather than ad hoc destructive reset logic.
