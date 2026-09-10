# AGENTS.md

## Purpose

This repository implements an AI-assisted interface for OHDSI study design work. Treat it as a real, but still evolving, system for human-led observational study design support.

The strongest implemented stories today are:

- phenotype recommendation and improvement for target, comparator, and outcome cohort selection
- Keeper-assisted concept generation, profile extraction, and row adjudication for phenotype validation
- R Strategus shells for incidence and cohort-method workflows, including `/ohdsi` contextual guidance and execution support

Do not describe the repo as if the entire future service catalog is already implemented. The top-level [README.md](README.md) reflects the intended public-facing product story; your coding and docs changes should stay grounded in what the code actually does now.

## Architecture

The repo is intentionally split into orchestration, tool serving, deterministic core logic, and R workflow layers.

- `acp_agent/`: ACP server and user-facing flow orchestration
- `mcp_server/`: MCP tool server, prompt bundles, retrieval, vocabulary, and Keeper tooling
- `core/`: deterministic shared logic, validation, logging helpers, and networking helpers
- `docs/`: maintained documentation and architecture notes
- `scripts/`: manual demos and test entrypoints
- `tests/`: Python tests, smoke tests, and static assertions

Important architectural distinction:

- ACP is the orchestration layer
- MCP is the tool-serving layer
- `StudyAgent` depends on an `MCPClient` protocol, not a concrete transport
- ACP startup injects either an HTTP MCP client or a managed stdio MCP client into `StudyAgent`

Current startup modes:

- HTTP MCP: set `STUDY_AGENT_MCP_URL`
- Managed stdio MCP: set `STUDY_AGENT_MCP_COMMAND` and optional `STUDY_AGENT_MCP_ARGS`
- No MCP client: only limited core/fallback behavior is available where supported

Treat this dependency-injection boundary as intentional. Do not move MCP construction logic into `StudyAgent` without a strong reason.

## Source Of Truth

When the repo contains multiple descriptions of a capability, prefer these sources in this order:

1. implementation in code
2. maintained docs under `docs/`
3. thin component READMEs

Important nuance:

- [`docs/SERVICE_REGISTRY.yaml`](docs/SERVICE_REGISTRY.yaml) is an important metadata surface, but not the only source of truth for runtime behavior
- actual ACP flow routing lives in [`acp_agent/study_agent_acp/server.py`](acp_agent/study_agent_acp/server.py)
- flow and tool behavior often depends on both ACP and MCP code paths

## High-Value Docs

Start here before making architectural or behavioral changes:

- [README.md](README.md)
- [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md)
- [docs/TESTING.md](docs/TESTING.md)
- [docs/SERVICE_REGISTRY.yaml](docs/SERVICE_REGISTRY.yaml)
- [docs/WORKFLOW_PHENOTYPE_RECOMMENDATION.md](docs/WORKFLOW_PHENOTYPE_RECOMMENDATION.md)
- [docs/WORKFLOW_PHENOTYPE_MAKE_COMPUTABLE.md](docs/WORKFLOW_PHENOTYPE_MAKE_COMPUTABLE.md)
- [docs/WORKFLOW_CONTEXT_DIALOGUE_SLASH_OHDSI.md](docs/WORKFLOW_CONTEXT_DIALOGUE_SLASH_OHDSI.md)
- [docs/PHENOTYPE_VALIDATION_REVIEW.md](docs/PHENOTYPE_VALIDATION_REVIEW.md)
- [docs/SPEC_KEEPER_INTERFACE.md](docs/SPEC_KEEPER_INTERFACE.md)
- [docs/WORKFLOW_INCIDENCE.md](docs/WORKFLOW_INCIDENCE.md)
- [docs/WORKFLOW_COHORT_METHODS.md](docs/WORKFLOW_COHORT_METHODS.md)
- [docs/PHENOTYPE_INDEXING.md](docs/PHENOTYPE_INDEXING.md)

## Implemented ACP Flows

Treat the following as implemented, developer-relevant ACP flows:

- `phenotype_recommendation`
- `phenotype_recommendation_advice`
- `phenotype_improvements`
- `phenotype_intent_split`
- `phenotype_make_computable`
- `cohort_methods_intent_split`
- `workflow_context_dialogue`
- `keeper_concept_sets_generate`
- `keeper_profiles_generate`
- `phenotype_validation_review`

There are additional support surfaces and execution helpers, but do not expand docs or summaries beyond what is actually implemented and testable.

## Narrative-To-Computable Cohort Guardrails

`phenotype_make_computable` is a review-gated flow used by the Strategus shells' `create` acquisition branch. Preserve these boundaries when changing ACP, MCP, or R-shell code:

- Scope confirmation, candidate retrieval, and explicit concept-set approval are separate stages. Never infer a clinical scope decision, concept selection, descendant policy, mapped policy, or exclusion policy.
- A candidate limit is a retrieval bound, not evidence that a concept set is complete. Required review sessions may return up to 500 candidates; proposal-mode limits remain lower and are not a shortcut around review.
- Review CSV/manifest artifacts and the exact approved policy object are durable resume state. Preserve their provenance and do not silently replace a reviewed policy.
- Do not emit Capr/Circe artifacts until explicit concept-set approval. Successful ACP validation is technical only: it does not establish clinical validity or database-level cohort validity.
- Shell-facing state must retain a human-readable target/comparator/outcome label. Keeper adjudication must fail closed if no non-generic clinical label can be recovered; never substitute `Cohort <id>`.

## Prompting Convention

A standing project convention is that prompts sent to LLMs should be as declarative and editable outside of code as practical.

Most LLM-facing interactions therefore live under `mcp_server/prompts/` in per-task subfolders. The common pattern is:

- `overview_*.md`: task overview and role framing
- `spec_*.md`: task instructions and constraints
- `output_schema_*.json` or equivalent output contract artifact

Some tools also add task-specific prompt artifacts such as:

- `system_prompt_*.md`
- `.yaml` domain configuration files
- workflow templates such as `cmAnalysis_template.json`

When changing LLM behavior, check whether the real source of behavior lives in prompt artifacts rather than inline Python or R code.

## Environment And Runtime

Use [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) as the central environment-variable reference. Do not create new partial env-var inventories in subdirectory READMEs unless there is a strong reason.

Most local setups only need:

- MCP runtime settings
- ACP runtime settings
- LLM settings for LLM-backed flows
- phenotype retrieval settings if phenotype search is used
- Keeper / OMOP / vocabulary settings if Keeper flows are used

Python configuration uses config.yaml for validated, non-secret settings and named profiles
such as native and docker. Keep secrets in secrets.env, never in config.yaml. CLI values override YAML;
YAML overrides legacy non-secret environment variables. Use the documented configuration rather than
introducing new non-secret environment-variable setup instructions.

Recommended native runtime:

```bash
uv run study-agent-mcp --config ./config.yaml --profile native
```

```bash
uv run study-agent-acp --config ./config.yaml --profile native
```

On managed Windows hosts, use uv run for every project command so PowerShell cannot select a global
Python or console script. Docker Compose supplies the docker profile.

Use full filesystem paths where practical, especially for:

- `PHENOTYPE_INDEX_DIR`
- generated workflow result and work roots
- Windows and airgapped deployments

## Setup

Python packaging and development:

- [pyproject.toml](pyproject.toml) is the source of truth for Python dependencies, console scripts, and the dev extra.
- Prefer uv run --extra dev for development, tests, and service commands.
- environment.yml remains a Conda/Micromamba bootstrap for Python plus pip; install this project into it with python -m pip install -e ".[dev]".
- config.yaml is created from config.example.yaml or uv run study-agent-setup; keep private settings in secrets.env.

Do not rely on bare python, pytest, doit, study-agent-mcp, or study-agent-acp commands when using uv.

For MCP tools and ACP flows that use R note the following:

Before diagnosing dependency failures or running package checks,
verify that R is using that library rather than an empty renv cache.

1. Locate the project-specific R library under `renv/library/` for the active platform,
   R version, and architecture. It may be a symbolic link to a shared HADES library.
2. Use it explicitly through `R_LIBS_USER` and start ad-hoc R commands with `--vanilla`.
3. Confirm availability before testing. The key packages include `Strategus`,
   `CohortGenerator`, `CohortIncidence`, `CohortMethod`, `DatabaseConnector`, and
   `PhenotypeLibrary`.

Use a placeholder such as `<renv-library>` rather than assuming a machine-specific path:

```sh
R_LIBS_USER=<renv-library> Rscript --vanilla -e   'stopifnot(requireNamespace("Strategus", quietly = TRUE))'
```

The project `.Rprofile` activates renv. If it redirects R away from the intended working
library during `R CMD build` or `R CMD check`, disable the user profile for that command
and retain the explicit library:

```sh
R_PROFILE_USER=/dev/null R_ENVIRON_USER=/dev/null R_LIBS_USER=<renv-library>   R CMD check --no-manual <package-tarball>
```

Do not run `renv::restore()` or modify the lockfile merely to make a check pass unless the
user explicitly asks to change dependency state.

## Manual testing deployment refresh

Before asking for or performing manual testing, determine whether the changes affect either linked R package or ACP/MCP runtime behavior. When they do, explicitly remind the tester to complete the applicable refresh first:

- Reinstall `slashOhdsiAcpClient` and/or `slashOhdsiStrategusAssistant` after changes to either package source, then restart the R session so it loads the installed changes.
- Restart MCP after MCP tool, retrieval/index, prompt, or MCP configuration changes.
- Restart ACP after ACP flow/server/client-contract changes, and restart it after MCP when ACP uses a managed MCP process or cached MCP service inventory.

Do not treat source-tree edits, an already-running R session, or already-running ACP/MCP processes as evidence that a manual test is exercising the new behavior. State the required refresh actions in the manual-test handoff.

## Testing

- Use the standard `testthat` entrypoint while developing:

  ```sh
  R_LIBS_USER=<renv-library> Rscript --vanilla -e 'testthat::test_local(".")'
  ```

- Build first, then run `R CMD check --no-manual` against the tarball for an installed
  package test.

## Testing Guidance

Primary testing guide:

- [docs/TESTING.md](docs/TESTING.md)
- If testing R-based code used by some MCPs or the ACP, Keep the test suite in `tests/testthat/` and use `tests/testthat.R` as the test runner.


Useful broad commands:

```bash
uv run --extra dev python -m pytest -m acp
uv run --extra dev python -m pytest -m mcp
```

Cheap targeted checks:

```bash
uv run --extra dev python -m pytest -q tests/test_demo_shell.py
uv run study-agent-demo-shell --help
```

For R-shell and generated-script changes, prefer focused static tests first. Relevant examples:

- `tests/test_incidence_shell_selection_state.py`
- `tests/test_keeper_generated_scripts.py`
- `tests/test_keeper_dialogue_integration_static.py`
- `tests/test_cohort_methods_generated_scripts.py`
- `tests/test_r_workflow_context_dialogue_wrapper.py`
- `tests/test_workflow_shell_runtime_static.py`
- `tests/test_strategus_db_details.py`

When editing R scripts, R shell code, or generated-script emitters:

- run focused static tests first
- run parse checks with `Rscript -e "parse(file='...')"` before finishing
- prefer preserving generated-script stability over cosmetic refactors

If you update documentation, verify that examples, env vars, and file references match the current code.

For live-smoke changes involving OMOP vocabulary or Keeper profile extraction, test both states explicitly: report that the database-backed smoke is skipped when `OMOP_DB_ENGINE` is absent, and run it when configured. Do not interpret a lexical candidate count or a successful R compilation as clinical validation.

## Implementation Guidance

- Prefer documenting implemented behavior over speculative future services.
- Keep component READMEs thin and point readers to maintained docs under `docs/`.
- Use `docs/ENVIRONMENT.md` for comprehensive env-var documentation.
- Treat `SERVICE_REGISTRY.yaml` as important, but do not assume it is the sole runtime truth.
- The demo shell is intentionally thin; keep it as an ACP client unless there is a strong reason to duplicate ACP logic.
- For user-facing shell improvements, prefer low-complexity terminal improvements before introducing heavier TUI dependencies.
- Do not assume recommendation responses are a flat list; ACP wraps them in a `recommendations` object.
- For static tests that need repo-relative paths, prefer the helpers in `tests/_repo_paths.py`.
- For Strategus resume and artifact discovery work, be careful about persisted execution roots, mutable execution-settings files, and full-path handling.
- For Windows database connectivity in Strategus-generated scripts, preserve support for integrated auth through the shared DB helper instead of patching generated scripts ad hoc.

## Security And Data Handling

These constraints are not optional:

- No PHI or PII should ever be sent to LLMs.
- `phenotype_validation_review` must pass through Keeper sanitization before prompt construction.
- `keeper_profiles_generate` is deterministic only; any downstream LLM use still requires the sanitization gate.
- Treat row-level data handling as safety-critical and preserve fail-closed behavior.
- When uncertain whether data is safe to send to an LLM, stop and preserve the guardrail rather than weakening it.

## Practical Notes

- The worktree may contain unrelated scratch files such as editor temp files or `demo-shell-output/`; do not delete them unless asked.
- The user may validate R workflows from a parent `renv` one level above the repo; do not modify or replace that parent `renv`.
- For shell test scripts, prefer the shared helper in `scripts/demo_setup.R` rather than ad hoc destructive reset logic.
- When docs drift, prefer consolidating references into maintained docs under `docs/` rather than expanding many local READMEs.
- For a release or evaluation that depends on an LLM, record the model identifier, immutable digest/version when available, serving stack, and relevant inference settings. Do not treat a mutable `:latest` label as reproducible provenance.
