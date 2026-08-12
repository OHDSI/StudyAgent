# OHDSI Study Design Assistant

This repository is building an agent-style interface for common OHDSI study design tasks. The fundamental use case for this project is to enable AI-assisted, but human led, observational study designs leveraging existing deterministic OHDSI tools. Initially, this is with HADES and Atlas but there no restriction on the use of study agent flows in other tooling environments (e.g., DARWIN tools).

The current implementation provides:

- Phenotype recommendations for target, comparator, and outcome cohort selection
- Phenotype validation using AI-assisted concept generation, profile extraction, and row adjudication for phenotype validation (i.e., an ACP service for [Keeper](https://github.com/OHDSI/Keeper) functionality)
- R-based interactive shells to specify and run real-world evidence generation using HADES incidence rate analysis and CohortMethod methods
- Support for `/ohdsi` AI interactive run and inspection features and contextualized question answering. 

This project is in beta testing. The videos below provide an overview of the current state for R-Hades support.

[VIDEO: Overview of Study Agent for AI-Assisted Real-world evidence generation](https://www.youtube.com/watch?v=rMxnmEGWoO4)

[VIDEO: AI-assisted Real-world evidence - Study Agent and R part 1 - Strategus Cohort Method overview, study intent, phenotype selection, and interactive runner shell intro](https://pitt.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=eef98905-e9eb-497f-8d07-b46e00c3702d)

[VIDEO: AI-assisted Real-world evidence - Study Agent and R part 2 - inspect cohorts and initiate keeper concept set](https://pitt.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=8f719cc9-08f4-4bea-9091-b46e00cf641e)

[VIDEO: AI-assisted Real-world Evidence - Study Agent and R Part 3 - Keeper concept set run and inspection ](https://pitt.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=c3ab5141-d7cb-4bd6-b3ec-b46f00d8f83d)

[VIDEO: AI-assisted Real-world evidence - Study Agent and R part 4 - case review (Keeper) ](https://pitt.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=7bd986fa-960c-493a-8417-b470001e542f)

[VIDEO: AI-assisted Real-world evidence - Study Agent and R part 5 - diagnostics and cohort method](https://pitt.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=f0f50c8d-765e-4c36-97ec-b47100dfc516)

[VIDEO: AI-assisted Real-world evidence - Study Agent and R BONUS - using /ohsdi and Atlas/WebAPI to generate cohorts](https://pitt.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=f0df2da7-86ee-4f4e-8f65-b4790179fc70)


-----

### How it works


The project separates orchestration from deterministic tooling:

- `acp_agent/`: [Agent Client Protocol](https://agentclientprotocol.com/get-started/introduction) (ACP) server that exposes the flow endpoints and handles LLM orchestration
- `mcp_server/`: [Model Context Protocol](https://modelcontextprotocol.io/docs/getting-started/intro) (MCP) server that exposes retrieval, prompt, vocabulary, concept search, case validateion, and numerous other tools. Many of the tools reside in the project but others do not. ACP specification and tool registration allows for extension beyond this project. 
- `core/`: pure validation and business logic shared by ACP and MCP
- `R/slashOhdsiStrategusAssistant/`: R-side Strategus workflow package and canonical shell entrypoints. This will likely eventually evolve to become a separate R HADES package.
- `R/slashOhdsiAcpClient/' : R-side interface to connect R with the ACP using REST calls. This will likely eventually evolve to become a separate R HADES package.

## What problems this project solves

Researchers often have three immediate bottlenecks when designing an OHDSI study:

- finding a reasonable starting phenotype definition for a study intent
- refining and/or validating that phenotype before using it in downstream analyses
- moving from phenotype selection into a reproducible study workflow

This repo addresses those bottlenecks by combining:

- phenotype retrieval from an indexed phenotype library
- constrained LLM ranking or critique with deterministic validation
- Keeper-oriented tooling for concept generation, OMOP profile extraction, and row-level adjudication using sanitized summaries only
- R shells that turn selected cohorts into reproducible HADES Strategus incidence and cohort-method workflows. The code in the HADES toolstack is deterministic and the R shells provide AI support where users frequently need assistance creating the Strategus specification that coordinates the HADES tools.

At no point should raw row-level patient data be sent directly to an LLM. Data shared with LLM is scrubbed to remove any protected health information prior to transactions. Any uncertainty leads to the termination of the transaction before any data is sent. 

## What Is Usable Now

### 1. Phenotype Recommendation

Implemented flow:

1. Retrieve phenotype candidates with MCP `phenotype_search`
2. Build the prompt and schema with MCP `phenotype_prompt_bundle`
3. Rank candidates with an OpenAI-compatible LLM
4. Validate and filter results in `core`
5. Return diagnostics and explicit fallback metadata if the LLM output is unusable

Related implemented flows:

- `phenotype_recommendation`
- `phenotype_recommendation_advice`
- `phenotype_improvements`
- `phenotype_intent_split`
- `cohort_methods_intent_split`
- `concept_sets_review`
- `cohort_critique_general_design`

This same recommendation path is already wired into the R Strategus incidence shell and the cohort-method shell.

Primary references:
- [docs/TESTING.md](docs/TESTING.md)
- [docs/WORKFLOW_CONTEXT_DIALOGUE_SLASH_OHDSI.md](docs/WORKFLOW_CONTEXT_DIALOGUE_SLASH_OHDSI.md)
- [docs/WORKFLOW_PHENOTYPE_RECOMMENDATION.md](docs/WORKFLOW_PHENOTYPE_RECOMMENDATION.md)
- [docs/PHENOTYPE_VALIDATION_REVIEW.md](docs/PHENOTYPE_VALIDATION_REVIEW.md)
- [docs/SPEC_KEEPER_INTERFACE.md](docs/SPEC_KEEPER_INTERFACE.md)
- [docs/R_STRATEGUS_INCIDENCE_SHELL.md](docs/R_STRATEGUS_INCIDENCE_SHELL.md)
- [docs/R_STRATEGUS_COHORT_METHODS_SHELL.md](docs/R_STRATEGUS_COHORT_METHODS_SHELL.md)
- [docs/WORKFLOW_INCIDENCE.md](docs/WORKFLOW_INCIDENCE.md)
- [docs/ROADMAP.md](docs/ROADMAP.md)
- [docs/R_PACKAGE_ARCHITECTURE_PLAN.md](docs/R_PACKAGE_ARCHITECTURE_PLAN.md)

### 2.  Phenotype Validation

This covers concept generation through case-review input preparation and row adjudication.

Implemented workflow:

1. Generate Keeper-oriented concept sets with `keeper_concept_sets_generate`
2. Extract OMOP-backed Keeper profiles with `keeper_profiles_generate`
3. Convert those profiles into review rows
4. Sanitize each row before any LLM call
5. Run `phenotype_validation_review` to adjudicate a single review row as `yes`, `no`, or `unknown`

Current characteristics:

- concept generation can use Hecate-backed, generic-search, or DB-backed vocabulary tooling
- profile extraction is deterministic only and does not call an LLM
- downstream adjudication is constrained by fail-closed sanitization and a small label set
- the R Strategus shells now generate split ACP-based Keeper scripts, `04_keeper_concept_sets.R` and `05_keeper_case_review.R`, that persist concept-set and case-review state for reuse and resume

Primary references:

- [docs/KEEPER_INTERFACE_SPEC.md](docs/KEEPER_INTERFACE_SPEC.md)
- [docs/PHENOTYPE_VALIDATION_REVIEW.md](docs/PHENOTYPE_VALIDATION_REVIEW.md)
- [docs/TESTING.md](docs/TESTING.md)

## End-To-End workflows implemented in R 

### Workflow A:  HADES real-world evidence generation using incidence rate analysis

1. Start MCP and ACP
2. Continue through `slashOhdsiStrategusAssistant::runStrategusIncidenceShell()`

See scripts/demo_strategus_incidence_rate.R

### Workflow B: :  HADES real-world evidence generation using CohortMethod

Use this when you need a practical validation loop around a phenotype.

1. Start MCP and ACP
2. Continue through `slashOhdsiStrategusAssistant::runStrategusCohortMethodsShell()`

scripts/demo_strategus_cohort_method.R

## Quickstart

### Native Python environments

For Windows and other managed-machine deployments, use a project environment rather than installing Study Agent into the system Python. `uv` is the recommended native path:

```powershell
uv python install 3.12
uv lock
uv run --extra dev python -m pytest -q tests/test_config_deployment.py
```

This quick verification does not require the optional phenotype source corpus, a built phenotype index, an LLM, or an embedding service.

Always launch project commands through `uv run`; do not use bare `python`, `pytest`, `doit`, `study-agent-mcp`, or `study-agent-acp`, because PowerShell may resolve a managed system installation instead of the project environment:

```powershell
uv run study-agent-setup
```

After configuring the required secrets and phenotype index, run the smoke task **before** starting long-lived ACP or MCP services. The task starts and stops its own MCP and ACP on ports 8790 and 8765:

```powershell
# Ensure no study-agent ACP or MCP process is already listening on ports 8765 or 8790.
uv run --extra dev doit smoke_phenotype_recommend_flow
```

Only after that smoke test succeeds, start the long-lived services for interactive use in separate terminals:

```powershell
uv run study-agent-mcp --config .\config.yaml --profile native
uv run study-agent-acp --config .\config.yaml --profile native
```

Conda or Micromamba remains supported. It supplies Python and `pip`; `conda run -n study-agent python -m pip install -e ".[dev]"` reads the application dependency definition from `pyproject.toml`.

### Install this package in development mode

```bash
python -m pip install -e ".[dev]"
```

`pip` reads `pyproject.toml`, so this installs the same Study Agent runtime and development dependencies as every other supported Python environment. Without activating the environment, use:

```bash
conda run -n study-agent python -m pip install -e ".[dev]"
conda run -n study-agent study-agent-mcp --config config.yaml
conda run -n study-agent study-agent-acp --config config.yaml
```

### Configure a deployment

After installation, run the interactive setup helper from the project directory:

```powershell
# uv-managed project environment
uv run study-agent-setup

# Or after installing into an activated Conda/virtual environment:
# study-agent-setup
```

The helper writes non-secret, cross-platform settings to `config.yaml` and, only when needed, writes hidden API keys or database URLs to private `secrets.env`. Do not place secrets in `config.yaml`. Docker Compose reads both files automatically. For native services, pass the YAML file explicitly:

```bash
study-agent-mcp --config config.yaml --profile native
study-agent-acp --config config.yaml --profile native
```

Existing environment-only deployments remain supported during this migration. See [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) for the precedence and migration details.

## Dependency Management

The project currently uses a simple split:

- `pyproject.toml` defines the Python package, runtime dependencies, console scripts, and optional dev tools.
- `environment.yml` bootstraps only a Python 3.12 and `pip` Conda or Micromamba environment. It deliberately does not duplicate application dependencies.
- `uv.lock` is not tracked as a repo source of truth. If you use `uv` locally, generate your own lockfile after cloning.

Official local workflow:

```bash
conda env create -f environment.yml
conda activate study-agent
python -m pip install -e ".[dev]"
```

Optional `uv` workflow for users who prefer it:

```bash
uv lock
uv run --extra dev python -m pytest
```

The repo does not require `uv`; it is the recommended native deployment path because every command can be explicitly tied to its project environment. `uv.lock` is currently a local artifact, so run `uv lock` after cloning and whenever dependency constraints change. Docker builds the runtime in two layers: `environment.yml` provides the Micromamba/Conda Python base environment, and then `pyproject.toml` is used by `python -m pip install -e .` to install the Python package and console entrypoints inside that environment.

### Docker Compose deployment

Docker Compose starts both services with the `docker` profile, mounts `config.yaml` read-only, and reads secrets from `secrets.env` (or the legacy secret-only `.env`). Prepare those files before starting Compose:

```bash
cp config.example.yaml config.yaml
# Edit config.yaml with non-secret deployment settings.
# Put only API keys, tokens, and database URLs in secrets.env.
docker compose up --build
```

On Linux, the container's non-root service user must be able to read the bind-mounted configuration. If startup reports `PermissionError: '/app/config.yaml'`, correct the host file mode and restart:

```bash
chmod 644 config.yaml
docker compose up --build
```

Check both services with `docker compose ps`, follow logs with `docker compose logs -f acp-agent mcp-server`, and call ACP at `http://127.0.0.1:8765`. The MCP endpoint is exposed at `http://127.0.0.1:8790/mcp` for diagnostics.

For an LLM or embedding service running on the Docker host, keep the `docker` profile URLs as `http://host.docker.internal:<port>/...`; Compose maps that name to the host gateway on Linux, macOS, and Windows. If the host service is reached through an SSH tunnel, the tunnel must listen on an address reachable from the Docker bridge, not only `127.0.0.1`; restrict the host firewall accordingly. See [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md) for verification commands and security details.

### Start MCP over HTTP (environment-only compatibility)

```bash
export MCP_TRANSPORT=http
export MCP_HOST=127.0.0.1
export MCP_PORT=8790
export MCP_PATH=/mcp
study-agent-mcp
```

### Start ACP

```bash
export STUDY_AGENT_MCP_URL="http://127.0.0.1:8790/mcp"
export STUDY_AGENT_HOST=127.0.0.1
export STUDY_AGENT_PORT=8765
study-agent-acp
```

If you want LLM-backed phenotype flows, also set an OpenAI-compatible endpoint:

```bash
export LLM_API_KEY=<YOUR_KEY>
export LLM_API_URL="<URL_BASE>/api/chat/completions"
export LLM_MODEL=<MODEL_NAME>
```

This has been tested with [Open webui](https://docs.openwebui.com/), with locally hosted models, and [LLM Shim](https://github.com/dbmi-pitt/llm-shim) with access to cloud services (tested with openai and bedrock models) and an embedding model serviced using the HuggingFace Text Embedding Interface service. 

If you want phenotype retrieval, you also need an indexed phenotype library. See [docs/PHENOTYPE_INDEXING.md](docs/PHENOTYPE_INDEXING.md).

Current indexing workflow:

1. Build `catalog.jsonl` plus `sparse_index.pkl` from OHDSI and/or CIPHER source files.
2. Optionally enable LLM-derived retrieval keywords during that build.
3. Build `dense.index` separately when embedding infrastructure is available, either during the main build with `--build-dense` or later with `--build-dense --dense-only`.

The retrieval layer reads from `PHENOTYPE_INDEX_DIR`, which should point to the built output directory. The source phenotype files do not need to live under that directory. In the default Docker/Compose setup, the index is expected on the host at `./data/phenotype_index` and is mounted into the container at `/data/phenotype_index`. If you set `PHENOTYPE_INDEX_DIR` in `.env`, make sure the mounted volume path is updated to match; otherwise the container will still only see the default mounted index location.


## Minimal examples of ACP flows

### Phenotype recommendation

```bash
curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
  -H 'Content-Type: application/json' \
  -d '{"study_intent":"Identify clinical risk factors for older adult patients who experience an adverse event of acute gastrointestinal bleeding","top_k":20,"candidate_offset":0,"max_results":10,"candidate_limit":10}'
```

### Keeper concept generation

```bash
curl -s -X POST http://127.0.0.1:8765/flows/keeper_concept_sets_generate \
  -H 'Content-Type: application/json' \
  -d '{"phenotype":"Gastrointestinal bleeding",
       "domain_keys":["doi","alternativeDiagnosis","symptoms"],
       "candidate_limit":5,
       "include_diagnostics":true
       }'
```

### Keeper row adjudication

```bash
curl -s -X POST http://127.0.0.1:8765/flows/phenotype_validation_review \
  -H 'Content-Type: application/json' \
  -d '{
    "disease_name": "Gastrointestinal bleeding",
    "keeper_row": {
      "age": 44,
      "gender": "Male",
      "visitContext": "Inpatient Visit",
      "presentation": "Gastrointestinal hemorrhage",
      "priorDisease": "Peptic ulcer",
      "priorDrugs": "celecoxib",
      "afterDrugs": "naproxen"
    }
  }'
```

## Where To Go Next

- Installation, smoke tests (see `doit list`), and provider-specific examples: [docs/TESTING.md](docs/TESTING.md)
- Environment-variable reference across ACP, MCP, retrieval, Keeper, and R workflows: [docs/ENVIRONMENT.md](docs/ENVIRONMENT.md)
- Implemented service inventory: [docs/SERVICE_REGISTRY.yaml](docs/SERVICE_REGISTRY.yaml)
- Docker setup: see `compose.yaml` and `.env.example`. The default containerized phenotype index path is `./data/phenotype_index` on the host, mounted to `/data/phenotype_index` in the container.
- ACP and MCP component details: [acp_agent/README.md](acp_agent/README.md), [mcp_server/README.md](mcp_server/README.md)

## Contributing

- Open an issue or discussion if a workflow is unclear or under-documented
- Submit PRs that tighten the implemented workflow docs before adding new service claims
- Join the discussion on the [OHDSI Forums](https://forums.ohdsi.org/t/seeking-input-on-services-that-the-ohdsi-study-agent-will-provide/24890)

## Roadmap

Near-term priorities:

- Beta testing and UX improvements
- Hardening of the agent harness as a standard OHDSI environment evolves
- Integration with Atlas as a client 

Active expansion areas:

- data-quality interpretation tied to study intent
- more phenotype authoring support beyond recommendation and improvement
- broader study-design critique and cohort authoring services

For the broader future-service catalog, see [docs/ROADMAP.md](docs/ROADMAP.md).

## What Remains Experimental

The repository still contains broader plans that are not the main implemented story yet. Treat these as exploratory or partial unless the docs for a specific flow say otherwise:

- generalized protocol-writing and critique services
- broader data-quality interpretation services
- wider cohort authoring and design-review service families beyond the currently implemented lint/recommendation paths
- expansion toward a larger study-agent service catalog

The planned-service inventory in older docs should not be read as "fully available now".
