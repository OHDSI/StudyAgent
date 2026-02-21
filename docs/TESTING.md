# Testing

This repo uses lightweight CLI smoke tests for the ACP and MCP layers. Keep these steps in sync as the interfaces evolve.

## Install (required before tests)

Install the repo in editable mode so the CLI entrypoints are on your PATH and changes take effect immediately:

```bash
pip install -e .
```

Editable mode means Python imports the local source tree directly. You do not need to reinstall after edits; just re-run the commands. Manage this per environment (venv/conda) and remove with `pip uninstall study-agent` if needed.

## Test output verbosity

Use pytest's built-in verbosity:

```bash
pytest -v
```

Or enable per-test progress lines via environment variable:

```bash
STUDY_AGENT_PYTEST_PROGRESS=1 pytest
```

You can also set `PYTEST_OPTS` and `doit` will pass it through:

```bash
PYTEST_OPTS="-vv -rA -s" doit run_all_tests
```

## ACP/MCP test groups

- `pytest -m acp` covers ACP flow tests (including phenotype flow).
- `pytest -m mcp` covers MCP tool tests (including prompt bundles and search weights).

## Task runner (doit)

List tasks:

```bash
doit list
```

Common tasks but see `doit list` for the most current set:

```bash
doit install
doit test_unit
doit test_core
doit test_acp
doit test_all
```

Task dependencies:

- `test_unit` depends on `test_core` and `test_acp`

## ACP smoke test (core fallback)

Start the ACP shim with core fallback enabled:

```bash
STUDY_AGENT_ALLOW_CORE_FALLBACK=1 study-agent-acp
```

In another shell:

```bash
curl -s http://127.0.0.1:8765/health
curl -s http://127.0.0.1:8765/tools
curl -s -X POST http://127.0.0.1:8765/tools/call \
  -H 'Content-Type: application/json' \
  -d '{"name":"cohort_lint","arguments":{"cohort":{"PrimaryCriteria":{"ObservationWindow":{"PriorDays":0}}}}}'
```

## ACP smoke test (MCP-backed)

Start ACP with an MCP tool server:

```bash
STUDY_AGENT_MCP_COMMAND=study-agent-mcp STUDY_AGENT_MCP_ARGS="" study-agent-acp
```

Optional host/port override:

```bash
STUDY_AGENT_HOST=0.0.0.0 STUDY_AGENT_PORT=9000 study-agent-acp
```

Then run the same curl commands as above.

## ACP phenotype flow (MCP + LLM)

Ensure MCP is running and set LLM env vars for an OpenAI-compatible endpoint:

```bash
export LLM_API_URL="http://localhost:3000/api/chat/completions"
export LLM_API_KEY="..."
export LLM_MODEL="gemma3:4b"
export LLM_DRY_RUN=0
export LLM_USE_RESPONSES=0
```

Then call:

```bash
curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
  -H 'Content-Type: application/json' \
  -d '{"study_intent":"Identify clinical risk factors for older adult patients who experience an adverse event of acute gastro-intenstinal (GI) bleeding", "top_k":20, "max_results":10,"candidate_limit":10}'
```

## ACP flow examples (MCP-backed)

Phenotype improvements:

```bash
curl -s -X POST http://127.0.0.1:8765/flows/phenotype_improvements \
  -H 'Content-Type: application/json' \
  -d '{"protocol_text":"Example protocol text","cohorts":[{"id":1,"name":"Example"}],"characterization_previews":[]}'
```

Using file paths:

```bash
curl -s -X POST http://127.0.0.1:8765/flows/phenotype_improvements \
  -H 'Content-Type: application/json' \
  -d '{"protocol_path":"demo/protocol.md","cohort_paths":["demo/1197_Acute_gastrointestinal_bleeding.json"]}'
```

Concept sets review:

```bash
curl -s -X POST http://127.0.0.1:8765/flows/concept_sets_review \
  -H 'Content-Type: application/json' \
  -d '{"concept_set":{"items":[]},"study_intent":"Example intent"}'
```

Cohort critique (general design):

```bash
curl -s -X POST http://127.0.0.1:8765/flows/cohort_critique_general_design \
  -H 'Content-Type: application/json' \
  -d '{"cohort":{"PrimaryCriteria":{}}}'
```

Using file paths:

```bash
curl -s -X POST http://127.0.0.1:8765/flows/concept_sets_review \
  -H 'Content-Type: application/json' \
  -d '{"concept_set_path":"demo/concept_set.json","study_intent":"Example intent"}'

curl -s -X POST http://127.0.0.1:8765/flows/cohort_critique_general_design \
  -H 'Content-Type: application/json' \
  -d '{"cohort_path":"demo/cohort_definition.json"}'
```

Phenotype validation review (single patient):

```bash
curl -s -X POST http://127.0.0.1:8765/flows/phenotype_validation_review \
  -H 'Content-Type: application/json' \
  -d '{"disease_name":"Gastrointestinal bleeding","keeper_row":{"age":44,"gender":"Male","visitContext":"Inpatient Visit","presentation":"Gastrointestinal hemorrhage","priorDisease":"Peptic ulcer","symptoms":"","comorbidities":"","priorDrugs":"celecoxib","priorTreatmentProcedures":"","diagnosticProcedures":"","measurements":"","alternativeDiagnosis":"","afterDisease":"","afterDrugs":"Naproxen","afterTreatmentProcedures":""}}'
```

## Phenotype flow smoke test (ACP + MCP)

Run the Python smoke test via `doit`:

```bash
doit smoke_phenotype_flow
```

## Concept sets review smoke test

```bash
doit smoke_concept_sets_review_flow
```

## Cohort critique smoke test

```bash
doit smoke_cohort_critique_flow
```

## Phenotype validation review smoke test

```bash
doit smoke_phenotype_validation_review_flow
```

## MCP smoke test (import)

```bash
python -c "import study_agent_mcp; print('mcp import ok')"
```

## Stop server

Press `Ctrl+C` in the terminal running `study-agent-acp` to stop the server.
