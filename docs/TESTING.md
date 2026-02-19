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

## Task runner (doit)

List tasks:

```bash
doit list
```

Common tasks:

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

Then run the same curl commands as above.

## ACP phenotype flow (MCP + LLM)

Ensure MCP is running and set LLM env vars for an OpenAI-compatible endpoint:

```bash
export LLM_API_URL="http://localhost:3000/api/chat/completions"
export LLM_API_KEY="..."
export LLM_MODEL="agentstudyassistant"
export LLM_DRY_RUN=0
export LLM_USE_RESPONSES=0
```

Then call:

```bash
curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
  -H 'Content-Type: application/json' \
  -d '{"study_intent":"Example intent text","top_k":20,"max_results":10,"candidate_limit":10}'
```

## MCP smoke test (import)

```bash
python -c "import study_agent_mcp; print('mcp import ok')"
```

## Stop server

Press `Ctrl+C` in the terminal running `study-agent-acp` to stop the server.
