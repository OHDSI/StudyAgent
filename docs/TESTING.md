# Testing

This repo uses lightweight CLI smoke tests for the ACP and MCP layers. Keep these steps in sync as the interfaces evolve.

## Install (required before tests)

Install the repo in editable mode so the CLI entrypoints are available in the selected Python environment and changes take effect immediately:

```bash
python -m pip install -e ".[dev]"
```

Editable mode means Python imports the local source tree directly. You do not need to reinstall after edits; just re-run the commands. Manage this per environment (venv/conda) and remove with `python -m pip uninstall study-agent` if needed.

Dependency notes:

- `pyproject.toml` is the source of truth for the Python package and the optional `dev` extras.
- `environment.yml` only bootstraps Python 3.12 and `pip` for Conda or Micromamba. Install Study Agent into that environment with `python -m pip install -e ".[dev]"`; do not add application dependencies to `environment.yml`.
- `uv.lock` is intentionally not tracked. If you prefer `uv`, generate a local lockfile after cloning with `uv lock`.

For uv, include the optional development tools for test commands and run every project command through uv so a managed system Python cannot be selected from `PATH`:

```powershell
uv run --extra dev python -m pytest -q
uv run --extra dev doit test_all
uv run study-agent-mcp --config .\config.yaml --profile native
uv run study-agent-acp --config .\config.yaml --profile native
```

For Conda without shell activation:

```bash
conda run -n study-agent python -m pip install -e ".[dev]"
conda run -n study-agent python -m pytest -q
```

## Verify the selected Python runtime

Run these diagnostics before a native deployment or when a command appears to use the wrong Python environment. They identify what the shell would select and what uv actually uses for the project. Do not include secret values in the output you share.

PowerShell:

```powershell
Get-Command python -All
Get-Command pytest -All
Get-Command study-agent-mcp -All
Get-Command study-agent-acp -All
uv run python -c "import sys, study_agent_core; print(sys.executable); print(sys.prefix); print(study_agent_core.__file__)"
uv run python -m pip show mcp
```

Bash:

```bash
type -a python
type -a pytest
type -a study-agent-mcp
type -a study-agent-acp
uv run python -c 'import sys, study_agent_core; print(sys.executable); print(sys.prefix); print(study_agent_core.__file__)'
uv run python -m pip show mcp
```

The `uv run` output is the authoritative project runtime. If a bare command resolves elsewhere, continue to invoke Study Agent and its test tools through `uv run` rather than changing the system Python installation. For Conda, replace `uv run` with `conda run -n study-agent`.

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

`dodo.py` loads `config.yaml` from the repository root when present. Its service subprocesses receive the YAML-derived non-secret settings, while secrets remain environment variables. Runtime logs and timeout-calibration artifacts go to `paths.runtime` (default `.study-agent-runtime`), which works on Windows and Linux.

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

### PowerShell (Windows) equivalents

Notes:
- PowerShell aliases `curl` to `Invoke-WebRequest`. Use `curl.exe` for real curl, or use `Invoke-RestMethod` below.
- Use here-strings to keep JSON readable.
- When using uv, prefix every executable in the PowerShell examples with `uv run` (for example, `uv run study-agent-acp --config .\config.yaml --profile native`). Do not use bare project executables on managed Windows hosts.

Start ACP with verbose logging (server + LLM):

```powershell
$env:STUDY_AGENT_ALLOW_CORE_FALLBACK = "1"
$env:STUDY_AGENT_DEBUG = "1"
$env:LLM_LOG = "1"
uv run study-agent-acp --config .\config.yaml --profile native
```

If you launch from outside the repo root, set `STUDY_AGENT_BASE_DIR` so relative paths (index, banner, outputs) resolve correctly:

```powershell
$env:STUDY_AGENT_BASE_DIR = "C:\path\to\OHDSI-Study-Agent"
```

Windows note: ACP defaults MCP to oneshot mode on Windows to avoid stdio lockups. You can also set it explicitly:

```powershell
$env:STUDY_AGENT_MCP_ONESHOT = "1"
```

ACP uses a threaded HTTP server by default. To disable threading:

```powershell
$env:STUDY_AGENT_THREADING = "0"
```

Health/tools checks:

```powershell
curl.exe -s http://127.0.0.1:8765/health
curl.exe -s http://127.0.0.1:8765/tools
curl.exe -s http://127.0.0.1:8765/services
```

Tool call (Invoke-RestMethod):

```powershell
$body = @'
{"name":"cohort_lint","arguments":{"cohort":{"PrimaryCriteria":{"ObservationWindow":{"PriorDays":0}}}}}
'@

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8765/tools/call `
  -Headers @{ "Content-Type" = "application/json" } `
  -Body $body
```

Tool call (curl.exe):

```powershell
$body = @'
{"name":"cohort_lint","arguments":{"cohort":{"PrimaryCriteria":{"ObservationWindow":{"PriorDays":0}}}}}
'@

curl.exe -s -X POST http://127.0.0.1:8765/tools/call `
  -H "Content-Type: application/json" `
  -d $body
```

## ACP smoke test (MCP-backed)

Start ACP with an MCP tool server:

```bash
STUDY_AGENT_MCP_COMMAND=study-agent-mcp STUDY_AGENT_MCP_ARGS="" study-agent-acp
```

This uses stdio MCP mode. If you use HTTP MCP, do not set `STUDY_AGENT_MCP_COMMAND`.

HTTP MCP mode (recommended for cross-platform stability):

```bash
export MCP_TRANSPORT=http
export MCP_HOST=127.0.0.1
export MCP_PORT=8790
export MCP_PATH=/mcp
study-agent-mcp
```

Then in a second shell:

```bash
export STUDY_AGENT_MCP_URL="http://127.0.0.1:8790/mcp"
study-agent-acp
```

Note: `STUDY_AGENT_MCP_URL` must include the port (e.g. `:8790`).
When set, ACP uses HTTP and ignores `STUDY_AGENT_MCP_COMMAND`.

PowerShell (Windows) MCP HTTP mode:

```powershell
$env:MCP_TRANSPORT = "http"
$env:MCP_HOST = "127.0.0.1"
$env:MCP_PORT = "8790"
$env:MCP_PATH = "/mcp"
uv run study-agent-mcp --config .\config.yaml --profile native
```

Then in a second PowerShell:

```powershell
$env:STUDY_AGENT_MCP_URL = "http://127.0.0.1:8790/mcp"
uv run study-agent-acp --config .\config.yaml --profile native
```

Health check (PowerShell):

```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8765/health
```

Built-in rotating service logging:

```bash
export STUDY_AGENT_LOG_DIR="/tmp/study-agent-logs"
export ACP_LOG_LEVEL=DEBUG
export MCP_LOG_LEVEL=DEBUG
```

ACP writes `study-agent-acp.log`; MCP writes `study-agent-mcp.log`.
Use `ACP_LOG_FILE` or `MCP_LOG_FILE` to override the exact file path.
Rotation is controlled by `STUDY_AGENT_LOG_MAX_BYTES` and `STUDY_AGENT_LOG_BACKUP_COUNT`.

Windows logging via shell redirection still works if desired:

```powershell
uv run study-agent-mcp --config .\config.yaml --profile native 1> mcp.out.log 2> mcp.err.log
uv run study-agent-acp --config .\config.yaml --profile native 1> acp.out.log 2> acp.err.log
```

Or using `Start-Process`:

```powershell
Start-Process uv -ArgumentList @("run", "study-agent-mcp", "--config", ".\config.yaml", "--profile", "native") -RedirectStandardOutput mcp.out.log -RedirectStandardError mcp.err.log
Start-Process uv -ArgumentList @("run", "study-agent-acp", "--config", ".\config.yaml", "--profile", "native") -RedirectStandardOutput acp.out.log -RedirectStandardError acp.err.log
```

Recommended MCP environment (use absolute paths for stability):

```bash
export PHENOTYPE_INDEX_DIR="/absolute/path/to/phenotype_index"
export EMBED_URL="http://localhost:3000/ollama/api/embed"
export EMBED_MODEL="qwen3-embedding:4b"
```

Optional host/port override:

```bash
STUDY_AGENT_HOST=0.0.0.0 STUDY_AGENT_PORT=9000 study-agent-acp
```

Then run the same curl commands as above.

Health check now includes MCP index preflight details under `mcp_index`:

```bash
curl -s http://127.0.0.1:8765/health
```

## ACP phenotype flow (MCP + LLM)

Ensure MCP is running and set LLM env vars for an OpenAI-compatible endpoint:

```bash
export LLM_API_URL="http://localhost:3000/api/chat/completions"
export LLM_API_KEY="..."
export LLM_MODEL="gemma3:4b"
export LLM_DRY_RUN=0
export LLM_USE_RESPONSES=0
export LLM_LOG=1
export LLM_TIMEOUT=300
export STUDY_AGENT_MCP_TIMEOUT=240
export ACP_TIMEOUT=360
export EMBED_TIMEOUT=120
export LLM_CANDIDATE_LIMIT=5
export LLM_RECOMMENDATION_MAX_RESULTS=3
```

`LLM_LOG=1` enables verbose LLM logging in the ACP logger (config, prompt, raw response).
For full payload capture during debugging, also set `LLM_LOG_RESPONSE=1`.
For OpenWebUI using `/api/chat/completions`, keep `LLM_USE_RESPONSES=0` (the Responses API schema is not supported and can yield empty outputs).
Recommended timeout ladder: `ACP_TIMEOUT > LLM_TIMEOUT > STUDY_AGENT_MCP_TIMEOUT`.

Then call:

```bash
curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
  -H 'Content-Type: application/json' \
  -d '{"study_intent":"Identify clinical risk factors for older adult patients who experience an adverse event of acute gastro-intenstinal (GI) bleeding", "top_k":20, "candidate_offset":0, "max_results":10,"candidate_limit":10}'
```

Expected recommendation responses now include `llm_used`, `llm_status`, `fallback_reason`, `fallback_mode`, and `diagnostics`. If the LLM path fails to parse or validate, ACP still returns `status: ok` with an explicit machine-readable fallback reason instead of silently degrading.


## Timeout calibration

Use the automated calibration task to derive environment-specific starting values for `EMBED_TIMEOUT`, `STUDY_AGENT_MCP_TIMEOUT`, `LLM_TIMEOUT`, and `ACP_TIMEOUT`:

```bash
doit calibrate_timeouts
```

What it does:

- starts MCP and ACP if they are not already running
- warms up and samples `phenotype_intent_split`, `phenotype_recommendation_advice`, and `phenotype_recommendation`
- tests multiple recommendation prompt sizes using `TIMEOUT_CALIBRATION_CANDIDATE_LIMITS` (default `3,5,8`)
- uses ACP diagnostics plus MCP embedding debug logs to recommend timeouts with safety margins

Useful overrides:

```bash
export TIMEOUT_CALIBRATION_RUNS=3
export TIMEOUT_CALIBRATION_CANDIDATE_LIMITS=3,5,8
export TIMEOUT_CALIBRATION_ENV_PATH=/tmp/study_agent_timeout_recommendations.env
export TIMEOUT_CALIBRATION_JSON_PATH=/tmp/study_agent_timeout_recommendations.json
doit calibrate_timeouts
```

Outputs:

- `.env` fragment with recommended timeout values
- JSON summary with observed p95 timings, fallback statuses, and per-run details

Interpretation notes:

- If the calibration run reports repeated `llm_status != ok`, fix LLM parsing/compatibility first rather than only raising timeouts.
- If larger `candidate_limit` values sharply increase latency, prefer a smaller `LLM_CANDIDATE_LIMIT` before increasing `LLM_TIMEOUT`.
- Treat the generated values as good starting points for that environment, not universal maxima.

Phenotype intent split (target/outcome statements):

```bash
curl -s -X POST http://127.0.0.1:8765/flows/phenotype_intent_split \
  -H 'Content-Type: application/json' \
  -d '{"study_intent":"Identify clinical risk factors for older adult patients who experience an adverse event of acute gastro-intenstinal (GI) bleeding"}'
```

PowerShell (Windows) equivalent:

```powershell
$body = @{
  study_intent = "Identify clinical risk factors for older adult patients who experience an adverse event of acute gastro-intenstinal (GI) bleeding"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8765/flows/phenotype_intent_split `
  -Headers @{ "Content-Type" = "application/json" } `
  -Body $body `
  -TimeoutSec 180
```

Cohort methods intent split (target/comparator/outcome statements):

```bash
curl -s -X POST http://127.0.0.1:8765/flows/cohort_methods_intent_split \
  -H 'Content-Type: application/json' \
  -d '{"study_intent":"What is the risk of angioedema or acute myocardial infarction in new users of ACE inhibitors compared to new users of thiazide and thiazide-like diuretics?"}'
```

PowerShell (Windows) equivalent:

```powershell
$body = @{
  study_intent = "What is the risk of angioedema or acute myocardial infarction in new users of ACE inhibitors compared to new users of thiazide and thiazide-like diuretics?"
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8765/flows/cohort_methods_intent_split `
  -Headers @{ "Content-Type" = "application/json" } `
  -Body $body `
  -TimeoutSec 180
```

Cohort methods specifications recommendation (analytic settings):

```bash
curl -s -X POST http://127.0.0.1:8765/flows/cohort_methods_specifications_recommendation \
  -H 'Content-Type: application/json' \
  -d '{"analytic_settings_description":"Compare sitagliptin new users vs glipizide new users for acute myocardial infarction. Use a 365-day washout, intent-to-treat follow-up, 1:1 propensity score matching on standardized logit with a caliper of 0.2, and a Cox model.","study_intent":"Comparative effectiveness study on CV outcomes."}' | python -m json.tool
```

PowerShell (Windows) equivalent:

```powershell
$body = @{
  analytic_settings_description = "Compare sitagliptin new users vs glipizide new users for acute myocardial infarction. Use a 365-day washout, intent-to-treat follow-up, 1:1 propensity score matching on standardized logit with a caliper of 0.2, and a Cox model."
  study_intent = "Comparative effectiveness study on CV outcomes."
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8765/flows/cohort_methods_specifications_recommendation `
  -Headers @{ "Content-Type" = "application/json" } `
  -Body $body `
  -TimeoutSec 240
```

Expected responses include `status`, `recommendation`, `cohort_methods_specifications`, `section_rationales`, and `diagnostics`. Valid top-level statuses are `ok`, `schema_validation_error`, and `llm_parse_error`; parse or section validation failures should return a backfilled recommendation with diagnostics rather than an unstructured response.

For local non-live coverage of the route, input model, validation, and mocked ACP flow:

```bash
pytest tests/test_acp_cohort_methods_route.py \
  tests/test_cohort_methods_specs_models.py \
  tests/test_cohort_methods_spec_validation.py \
  tests/test_acp_cohort_methods_flow.py
```

## ACP flow examples (MCP-backed)

Phenotype improvements:

```bash
curl -s -X POST http://127.0.0.1:8765/flows/phenotype_improvements \
  -H 'Content-Type: application/json' \
  -d '{"protocol_text":"Example protocol text","cohorts":[{"id":1,"name":"Example"}],"characterization_previews":[]}'
```

Client-side file loading:

- ACP no longer opens local paths from request bodies.
- Local clients should load protocol/cohort artifacts first and send inline `protocol_text` plus `cohorts`.

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

Client-side file loading:

- ACP no longer opens local paths from request bodies.
- Local clients should load concept-set and cohort JSON first and send inline `concept_set` or `cohort` payloads.

Phenotype validation review (single patient):

```bash
curl -s -X POST http://127.0.0.1:8765/flows/phenotype_validation_review \
  -H 'Content-Type: application/json' \
  -d '{"disease_name":"Gastrointestinal bleeding","keeper_row":{"age":44,"gender":"Male","visitContext":"Inpatient Visit","presentation":"Gastrointestinal hemorrhage","priorDisease":"Peptic ulcer","symptoms":"","comorbidities":"","priorDrugs":"celecoxib","priorTreatmentProcedures":"","diagnosticProcedures":"","measurements":"","alternativeDiagnosis":"","afterDisease":"","afterDrugs":"Naproxen","afterTreatmentProcedures":""}}'
```


### Case causal review (review a canonical row from a safety surveillance system):

Important:
- `case_row` must already be in the compact canonical case format expected by Study Agent
- `candidate_items` are the only structured ranking universe
- `context_items` and `case_metadata` may influence reasoning and narrative but are not ranked by default
- `index_event` is assumed to have occurred and must never be ranked as a cause
- `source_type` must currently be `signal_validation` or `patient_profile`
- sanitization is fail-closed before any LLM call
- optional enrichment tools may be hinted via `tool_hints`, but the flow must still work without them

Positive test path using `signal_validation` with compact `case_row` and optional tool hints:

```bash
curl -s -X POST http://127.0.0.1:8765/flows/case_causal_review   -H 'Content-Type: application/json'   -d '{
    "adverse_event_name": "Cystitis",
    "source_type": "signal_validation",
    "allowed_domains": ["drug_exposures", "conditions"],
    "case_row": {
      "case_id": "25196051",
      "case_summary": "Single suspect-drug spontaneous report with cystitis and additional hepatic reactions.",
      "index_event": {
        "label": "Cystitis",
        "source_record_id": "reaction-4",
        "domain": "index_event",
        "why_observed": "Selected adverse event present in reported reactions"
      },
      "candidate_items": [
        {
          "domain": "drug_exposures",
          "label": "Ketamine hydrochloride",
          "source_record_id": "drug-1",
          "source_kind": "reported_drug",
          "why_observed": "Primary suspect drug in spontaneous report",
          "subrole": "primary_suspect",
          "annotations": {
            "concept_set_match": false,
            "ingredient_concept_id": 123,
            "reported_indication": "Substance use",
            "approved_indications": [],
            "label_mentions_event": true,
            "box_warning_mentions_event": false,
            "has_disproportional_signal": true
          }
        }
      ],
      "context_items": [
        {
          "domain": "conditions",
          "label": "Drug abuse",
          "source_record_id": "reaction-5",
          "source_kind": "reported_reaction",
          "why_observed": "Additional reported reaction in same case",
          "subrole": "contextual_factor",
          "annotations": {
            "concept_set_match": false
          }
        }
      ],
      "case_metadata": {
        "age": "3 years",
        "sex": "male",
        "reporter_type": "health professional",
        "reporting_country": "GB",
        "serious": true,
        "seriousness_flags": ["other"],
        "literature_reference_present": true,
        "timing_granularity": "coarse"
      },
      "annotations": {
        "concept_set_id": "uuid",
        "concept_set_version": 1,
        "concept_set_available_domains": ["doi", "alternativeDiagnosis", "symptoms", "drugs"]
      },
      "tool_hints": {
        "available_expansions": [
          "get_case_review_concept_set_domain",
          "get_case_review_drug_signal_details",
          "get_case_review_drug_label_details",
          "get_case_review_report_literature_stub"
        ],
        "prefetch_expansions": [
          "get_case_review_drug_signal_details",
          "get_case_review_report_literature_stub"
        ]
      }
    }
  }' | python -m json.tool
```

Positive test path using `patient_profile` with `candidate_items` and `context_items` kept separate:

```bash
curl -s -X POST http://127.0.0.1:8765/flows/case_causal_review   -H 'Content-Type: application/json'   -d '{
    "adverse_event_name": "Hepatic failure",
    "source_type": "patient_profile",
    "allowed_domains": ["drug_exposures", "conditions", "measurements"],
    "case_row": {
      "case_id": "profile-17",
      "case_summary": "Progressive liver injury after recent medication changes.",
      "index_event": {
        "label": "Hepatic failure",
        "source_record_id": "event-1",
        "domain": "index_event",
        "why_observed": "Selected event of interest in the patient profile"
      },
      "candidate_items": [
        {
          "domain": "drug_exposures",
          "label": "Valproate",
          "source_record_id": "drug-17",
          "source_kind": "medication_exposure",
          "why_observed": "Recent active exposure before liver injury",
          "subrole": "primary_suspect",
          "annotations": {
            "label_mentions_event": true,
            "has_disproportional_signal": false
          }
        }
      ],
      "context_items": [
        {
          "domain": "conditions",
          "label": "Chronic liver disease",
          "source_record_id": "cond-3",
          "source_kind": "condition_occurrence",
          "why_observed": "Pre-existing condition",
          "subrole": "vulnerability_factor",
          "annotations": {
            "concept_set_match": true
          }
        },
        {
          "domain": "measurements",
          "label": "ALT 622 U/L",
          "source_record_id": "meas-8",
          "source_kind": "lab_measurement",
          "why_observed": "Observed during index event window",
          "subrole": "proximate_marker",
          "annotations": {}
        }
      ],
      "case_metadata": {
        "sex": "female",
        "timing_granularity": "coarse"
      },
      "annotations": {
        "concept_set_id": "cs-1",
        "concept_set_version": 2,
        "concept_set_available_domains": ["drugs", "alternativeDiagnosis"]
      },
      "tool_hints": {
        "available_expansions": ["get_case_review_drug_label_details"],
        "prefetch_expansions": []
      }
    }
  }' | python -m json.tool
```

Validation check for unsupported `source_type`:

```bash
curl -i -s -X POST http://127.0.0.1:8765/flows/case_causal_review   -H 'Content-Type: application/json'   -d '{
    "adverse_event_name": "Gastrointestinal bleeding",
    "source_type": "faers_raw",
    "case_row": {
      "case_id": "case-1",
      "index_event": {
        "domain": "index_event",
        "label": "Gastrointestinal bleeding",
        "source_record_id": "reaction-1"
      },
      "candidate_items": [
        {
          "domain": "drug_exposures",
          "label": "Warfarin",
          "source_record_id": "drug-1"
        }
      ]
    }
  }'
```
Expected result: HTTP 400 with `source_type must be signal_validation or patient_profile`.

Direct enrichment tool checks through Study Agent (`/tools/call`):

Assumptions:
- ACP is running on `http://127.0.0.1:8765`
- MCP is running with `PV_COPILOT_HOST` and `PV_COPILOT_PORT` already configured
- dev mode is being used with no pv-copilot auth requirement
- if you configured `PV_COPILOT_BASE_URL` instead, these commands do not change

Concept-set domain lookup:

```bash
curl -s -X POST http://127.0.0.1:8765/tools/call   -H 'Content-Type: application/json'   -d '{
    "name": "get_case_review_concept_set_domain",
    "arguments": {
      "concept_set_id": "uuid",
      "concept_set_version": 1,
      "domain_name": "doi",
      "limit": 10
    }
  }' | python -m json.tool
```

Drug signal details lookup:

```bash
curl -s -X POST http://127.0.0.1:8765/tools/call   -H 'Content-Type: application/json'   -d '{
    "name": "get_case_review_drug_signal_details",
    "arguments": {
      "source_type": "signal_validation",
      "adverse_event_name": "Cystitis",
      "source_record_id": "drug-1",
      "report_lookup_key": {
        "primaryid": "25196051",
        "isr": null
      },
      "adverse_event_concept_id": 4172256,
      "ingredient_concept_id": 123,
      "ingred_rxcui": "11289"
    }
  }' | python -m json.tool
```

Drug label details lookup:

```bash
curl -s -X POST http://127.0.0.1:8765/tools/call   -H 'Content-Type: application/json'   -d '{
    "name": "get_case_review_drug_label_details",
    "arguments": {
      "source_type": "signal_validation",
      "adverse_event_name": "Cystitis",
      "source_record_id": "drug-1",
      "report_lookup_key": "25196051",
      "adverse_event_concept_id": 4172256,
      "adverse_event_meddra_id": "10011735",
      "ingredient_concept_id": 123,
      "ingred_rxcui": "11289",
      "mention_limit": 5
    }
  }' | python -m json.tool
```

Report literature stub lookup:

```bash
curl -s -X POST http://127.0.0.1:8765/tools/call   -H 'Content-Type: application/json'   -d '{
    "name": "get_case_review_report_literature_stub",
    "arguments": {
      "source_type": "signal_validation",
      "case_id": "25196051",
      "report_lookup_key": "25196051"
    }
  }' | python -m json.tool
```

Patient-profile compatibility check for a non-fatal `unsupported` response:

```bash
curl -s -X POST http://127.0.0.1:8765/tools/call   -H 'Content-Type: application/json'   -d '{
    "name": "get_case_review_drug_signal_details",
    "arguments": {
      "source_type": "patient_profile",
      "adverse_event_name": "Hepatic failure",
      "source_record_id": "drug-17"
    }
  }' | python -m json.tool
```
Expected result: tool-level `status` may be `ok`, `not_found`, `unsupported`, or `unavailable`. `unsupported` and `not_found` are valid non-fatal outcomes.

End-to-end flow check with optional enrichment enabled:

```bash
curl -s -X POST http://127.0.0.1:8765/flows/case_causal_review   -H 'Content-Type: application/json'   -d '{
    "adverse_event_name": "Cystitis",
    "source_type": "signal_validation",
    "allowed_domains": ["drug_exposures", "conditions"],
    "case_row": {
      "case_id": "25196051",
      "case_summary": "Single suspect-drug spontaneous report with cystitis and additional hepatic reactions.",
      "index_event": {
        "label": "Cystitis",
        "source_record_id": "reaction-4",
        "domain": "index_event",
        "why_observed": "Selected adverse event present in reported reactions",
        "annotations": {
          "adverse_event_meddra_id": "10011735"
        }
      },
      "candidate_items": [
        {
          "domain": "drug_exposures",
          "label": "Ketamine hydrochloride",
          "source_record_id": "drug-1",
          "source_kind": "reported_drug",
          "why_observed": "Primary suspect drug in spontaneous report",
          "subrole": "primary_suspect",
          "annotations": {
            "ingredient_concept_id": 123,
            "report_lookup_key": "25196051",
            "label_mentions_event": true,
            "has_disproportional_signal": true
          }
        }
      ],
      "context_items": [
        {
          "domain": "conditions",
          "label": "Drug abuse",
          "source_record_id": "reaction-5",
          "source_kind": "reported_reaction",
          "why_observed": "Additional reported reaction in same case",
          "subrole": "contextual_factor",
          "annotations": {}
        }
      ],
      "case_metadata": {
        "literature_reference_present": true,
        "reporter_type": "health professional",
        "timing_granularity": "coarse"
      },
      "annotations": {
        "concept_set_id": "uuid",
        "concept_set_version": 1,
        "concept_set_available_domains": ["drugs", "symptoms"],
        "report_lookup_key": "25196051"
      },
      "tool_hints": {
        "available_expansions": [
          "get_case_review_concept_set_domain",
          "get_case_review_drug_signal_details",
          "get_case_review_drug_label_details",
          "get_case_review_report_literature_stub"
        ],
        "prefetch_expansions": [
          "get_case_review_drug_signal_details",
          "get_case_review_drug_label_details",
          "get_case_review_report_literature_stub"
        ]
      }
    }
  }' | python -m json.tool
```
Check `diagnostics.optional_enrichment` in the response to confirm which enrichment tools were called and what they returned.

### Keeper concept sets generate

This flow is now usable end to end.

Supported provider patterns:
- Hecate-backed vocabulary search plus Hecate Phoebe expansion
- air-gapped `generic_search_api` vocabulary search plus DB-backed concept enrichment and Phoebe recommendations

Important:
- restart ACP and MCP after code changes or environment changes affecting provider selection
- `keeper_concept_sets_generate` does not use patient-level data
- `keeper_profiles_generate` is deterministic only and does not call the LLM

### Hecate-backed configuration

```bash
export VOCAB_SEARCH_PROVIDER=hecate_api
export VOCAB_SEARCH_URL="https://hecate.pantheon-hds.com/api/search_standard"
export PHOEBE_PROVIDER=hecate_api
export PHOEBE_BULK_URL="https://hecate.pantheon-hds.com/api/concepts/phoebe/bulk"
```

The Hecate PHOEBE provider always uses the bulk endpoint and sends concept IDs in chunks of 100. Optional hardening knobs: `PHOEBE_HTTP_RETRIES` and `PHOEBE_HTTP_BACKOFF_MS`.

Run the flow:

```bash
curl -s -X POST http://127.0.0.1:8765/flows/keeper_concept_sets_generate \
  -H 'Content-Type: application/json' \
  -d '{"phenotype":"Gastrointestinal bleeding","domain_keys":["doi","alternativeDiagnosis","symptoms"],"candidate_limit":10,"include_diagnostics":true}' | python -m json.tool
```


Real bulk-endpoint smoke test:

```bash
doit smoke_hecate_phoebe_bulk_endpoint
```

This target makes a real POST to `PHOEBE_BULK_URL` through the MCP tool code path. It is opt-in and is not part of `doit run_all`. The smoke path exercises the same bulk-only provider branch used by `phoebe_related_concepts` when `PHOEBE_PROVIDER=hecate_api`.

Optional overrides:

```bash
export HECATE_SMOKE_CONCEPT_IDS="4247297,4116092"
export HECATE_SMOKE_RELATIONSHIP_IDS="Ontology-parent"
export HECATE_SMOKE_EXPECT_MIN_COUNT=1
```

## Keeper profiles generate

This flow is now implemented for the first deterministic slice.

What it does:
- calls MCP `keeper_profile_extract` to query OMOP CDM and build Keeper-style long-form profile records
- calls MCP `keeper_profile_to_rows` to convert those records into row-oriented review payloads
- does not call the LLM

Important:
- row-level patient data remains on the deterministic MCP side
- downstream `phenotype_validation_review` must still receive sanitized rows only
- the current sampling mode is deterministic head-of-cohort, not random

Example:

```bash
curl -s -X POST http://127.0.0.1:8765/flows/keeper_profiles_generate \
  -H 'Content-Type: application/json' \
  -d '{
    "cdm_database_schema": "cdm",
    "cohort_database_schema": "results",
    "cohort_table": "cohort",
    "cohort_definition_id": 123,
    "sample_size": 5,
    "phenotype_name": "Gastrointestinal bleeding",
    "remove_pii": true,
    "keeper_concept_sets": [
      {
        "conceptId": 192671,
        "conceptName": "Gastrointestinal hemorrhage",
        "vocabularyId": "SNOMED",
        "conceptSetName": "doi",
        "target": "Disease of interest"
      }
    ]
  }' | python -m json.tool
```

Direct MCP tool checks through ACP:

```bash
curl -s -X POST http://127.0.0.1:8765/tools/call \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "keeper_concept_set_bundle",
    "arguments": {
      "phenotype": "Gastrointestinal bleeding",
      "domain_key": "doi",
      "target": "Disease of interest"
    }
  }' | python -m json.tool
```

```bash
curl -s -X POST http://127.0.0.1:8765/tools/call \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "vocab_search_standard",
    "arguments": {
      "query": "gastrointestinal hemorrhage",
      "domains": ["Condition"],
      "concept_classes": [],
      "limit": 5,
      "provider": "hecate_api"
    }
  }' | python -m json.tool
```

```bash
curl -s -X POST http://127.0.0.1:8765/tools/call \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "phoebe_related_concepts",
    "arguments": {
      "concept_ids": [192671],
      "relationship_ids": [],
      "provider": "hecate_api"
    }
  }' | python -m json.tool
```

### Air-gapped search plus DB-backed Phoebe/metadata

Use this when the embedding service is local and returns sparse concept rows that need OMOP metadata enrichment from the vocabulary database.

```bash
export VOCAB_SEARCH_PROVIDER=generic_search_api
export VOCAB_SEARCH_URL="http://127.0.0.1:30080/search"
export VOCAB_SEARCH_QUERY_PREFIX="Instruction: retrieve the concepts most related to the query. Query: "
export VOCAB_METADATA_PROVIDER=db
export PHOEBE_PROVIDER=db
export OMOP_DB_ENGINE='<sqlalchemy engine url>'
export VOCAB_DATABASE_SCHEMA=vocabulary
export PHOEBE_DB_TABLE=concept_recommended
export VOCAB_CONCEPT_TABLE=concept
```

Test sparse search:

```bash
curl -s -X POST http://127.0.0.1:8765/tools/call \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "vocab_search_standard",
    "arguments": {
      "query": "intracranial hemorrhage",
      "domains": ["Condition"],
      "concept_classes": [],
      "limit": 5,
      "provider": "generic_search_api"
    }
  }' | python -m json.tool
```

Test DB-backed Phoebe:

```bash
curl -s -X POST http://127.0.0.1:8765/tools/call \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "phoebe_related_concepts",
    "arguments": {
      "concept_ids": [192671],
      "relationship_ids": ["Patient context"],
      "provider": "db"
    }
  }' | python -m json.tool
```

Test DB-backed enrichment/filtering for sparse rows:

```bash
curl -s -X POST http://127.0.0.1:8765/tools/call \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "vocab_filter_standard_concepts",
    "arguments": {
      "concepts": [
        {"conceptId": 439847, "score": 0.98}
      ],
      "domains": ["Condition"],
      "concept_classes": [],
      "provider": "db"
    }
  }' | python -m json.tool
```

```bash
curl -s -X POST http://127.0.0.1:8765/tools/call \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "vocab_fetch_concepts",
    "arguments": {
      "concept_ids": [439847],
      "concepts": [
        {"conceptId": 439847, "score": 0.98}
      ],
      "provider": "db"
    }
  }' | python -m json.tool
```

Run the flow with the air-gapped provider path:

```bash
curl -s -X POST http://127.0.0.1:8765/flows/keeper_concept_sets_generate \
  -H 'Content-Type: application/json' \
  -d '{"phenotype":"Intracranial hemorrhage","domain_keys":["doi"],"candidate_limit":5,"vocab_search_provider":"generic_search_api","phoebe_provider":"db","include_diagnostics":true}' | python -m json.tool
```

### LLM shim example

Make sure the LLM shim `config.yaml` is configured for the target provider/model.
Example Bedrock naming may require the `us.` prefix.

```bash
export LLM_MODEL=bedrock:us.anthropic.claude-opus-4-5-20251101-v1:0
```

```bash
curl -s -X POST http://127.0.0.1:8765/flows/keeper_concept_sets_generate \
  -H 'Content-Type: application/json' \
  -d '{"phenotype":"Gastrointestinal bleeding","domain_keys":["doi","alternativeDiagnosis","symptoms"],"candidate_limit":10,"include_diagnostics":true}' | python -m json.tool
```


## Phenotype flow smoke test (ACP + MCP)

Run the Python smoke test via `doit`:

```bash
doit smoke_phenotype_flow
```

If you want `doit` to spin up MCP over HTTP automatically, set:

```bash
export STUDY_AGENT_MCP_URL="http://127.0.0.1:8790/mcp"
export STUDY_AGENT_MCP_MANAGED=1
export MCP_START_TIMEOUT=3
```

Note: the smoke tasks set `ACP_URL` internally per flow. Avoid exporting a global `ACP_URL` unless you intend to override the target flow.

## Concept sets review smoke test

```bash
doit smoke_concept_sets_review_flow
```

## Cohort critique smoke test

```bash
doit smoke_cohort_critique_flow
```

## Cohort methods specifications recommendation smoke test

This live ACP + MCP smoke test requires LLM credentials, because the flow asks the LLM to map free-text cohort-method analytic settings into the CohortMethod specification shape:

```bash
export LLM_API_KEY="..."
doit smoke_cohort_methods_specs_recommend_flow
```

If you want `doit` to start MCP over HTTP automatically, use the same managed MCP settings as the phenotype flow smoke test:

```bash
export STUDY_AGENT_MCP_URL="http://127.0.0.1:8790/mcp"
export STUDY_AGENT_MCP_MANAGED=1
export MCP_START_TIMEOUT=3
export LLM_API_KEY="..."
doit smoke_cohort_methods_specs_recommend_flow
```

The smoke test posts to `/flows/cohort_methods_specifications_recommendation` and checks that the response status is one of `ok`, `schema_validation_error`, or `llm_parse_error`, and that `recommendation.raw_description` is present.

## Phenotype validation review smoke test

```bash
doit smoke_phenotype_validation_review_flow
```

## Keeper concept sets generate smoke test

```bash
doit smoke_keeper_concept_sets_generate_flow
```

## MCP smoke test (import)

```bash
python -c "import study_agent_mcp; print('mcp import ok')"
```

## MCP probe (index + search)

This checks index paths and runs a simple search, without ACP.

```bash
python mcp_server/scripts/mcp_probe.py --query "acute GI bleed in hospitalized patients" --top-k 5
```

PowerShell (Windows) equivalent:

```powershell
python mcp_server/scripts/mcp_probe.py --query "acute GI bleed in hospitalized patients" --top-k 5
```

Print and sort environment variables (PowerShell):

```powershell
Get-ChildItem Env: | Sort-Object Name
```

## Service listing

Use the `/services` endpoint (or the helper task) to list ACP services:

```bash
doit list_services
```

## Stop server

Press `Ctrl+C` in the terminal running `study-agent-acp` to stop ACP.

If MCP is running as a separate HTTP process, stop ACP first, then stop MCP.
If ACP started MCP via `STUDY_AGENT_MCP_COMMAND`, stopping ACP should also close the managed MCP subprocess.
