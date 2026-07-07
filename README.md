# OHDSI Study Design Assistant

This repository is building an agent-style interface for common OHDSI study design tasks. The fundamental use case for this project is to enable AI-assisted, but human led, observational study designs leveraging existing deterministic OHDSI tools. Initially, this is with HADES and Atlas but there no restriction on the use of study agent flows in other tooling environments (e.g., DARWIN tools).

The current implementation provides:

- Phenotype recommendation for target and outcome cohort selection
- Keeper-assisted concept generation, profile extraction, and row adjudication for phenotype validation
- Shells for the HADES incidence rate analysis and CohortMethod real-world evidence generation methods that call the ACP/MCP flows and provide interactive run and inspection features along with `/ohdsi` contextualized question answering. 

[VIDEO: Overview of Study Agent for AI-Assisted Real-world evidence generation](https://www.youtube.com/watch?v=rMxnmEGWoO4)

[VIDEO: AI-assisted Real-world evidence - Study Agent and R part 1 - Strategus Cohort Method overview, study intent, phenotype selection, and interactive runner shell intro](https://pitt.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=eef98905-e9eb-497f-8d07-b46e00c3702d)

[VIDEO: AI-assisted Real-world evidence - Study Agent and R part 2 - inspect cohorts and initiate keeper concept set](https://pitt.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=8f719cc9-08f4-4bea-9091-b46e00cf641e)

[VIDEO: AI-assisted Real-world Evidence - Study Agent and R Part 3 - Keeper concept set run and inspection ](https://pitt.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=c3ab5141-d7cb-4bd6-b3ec-b46f00d8f83d)

[VIDEO: AI-assisted Real-world evidence - Study Agent and R part 4 - case review (Keeper) ](https://pitt.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=7bd986fa-960c-493a-8417-b470001e542f)

[VIDEO: AI-assisted Real-world evidence - Study Agent and R part 5 - diagnostics and cohort method](https://pitt.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=f0f50c8d-765e-4c36-97ec-b47100dfc516)

[VIDEO: AI-assisted Real-world evidence - Study Agent and R BONUS - using /ohsdi and Atlas/WebAPI to generate cohorts](https://pitt.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=f0df2da7-86ee-4f4e-8f65-b4790179fc70)


-----

The project separates orchestration from deterministic tooling:

- `acp_agent/`: ACP server that exposes the flow endpoints and handles LLM orchestration
- `mcp_server/`: MCP server that exposes retrieval, prompt, vocabulary, and Keeper tools
- `core/`: pure validation and business logic shared by ACP and MCP
- `R/slashOhdsiStrategusAssistant/`: R-side Strategus workflow package and canonical shell entrypoints

## What Problems This Solves

Researchers often have three immediate bottlenecks when designing an OHDSI study:

- finding a reasonable starting phenotype definition for a study intent
- refining or validating that phenotype before using it in downstream analyses
- moving from phenotype selection into a reproducible study workflow

This repo addresses those bottlenecks by combining:

- phenotype retrieval from an indexed phenotype library
- constrained LLM ranking or critique with deterministic validation
- Keeper-oriented tooling for concept generation, OMOP profile extraction, and row-level adjudication using sanitized summaries only
- R shells that turn selected cohorts into reproducible Strategus incidence and cohort-method workflows

At no point should raw row-level patient data be sent directly to an LLM.

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

### 2. Keeper-Assisted Phenotype Validation

This is the other strong implemented story. It covers concept generation through case-review input preparation and row adjudication.

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

## End-To-End Workflows

### Workflow A: Go from study intent to suggested phenotypes

Use this when you need a defensible starting cohort definition for a target or outcome.

1. Start MCP and ACP
2. Call `phenotype_recommendation` with a study intent
3. Review returned candidates and diagnostics
4. If needed, call `phenotype_recommendation_advice` for next-step guidance
5. Optionally call `phenotype_improvements` on a selected cohort
6. If you are working in R, continue through `slashOhdsiStrategusAssistant::runStrategusIncidenceShell()`

### Workflow B: Go from clinical event to keeper-assisted validation review

Use this when you need a practical validation loop around a phenotype.

1. Call `keeper_concept_sets_generate` for the phenotype of interest
2. Approve the concept sets you want to use for extraction
3. Call `keeper_profiles_generate` against your OMOP data
4. Take one generated `rows[]` entry at a time
5. Send the sanitized row to `phenotype_validation_review`
6. Repeat row adjudication as needed to review more sampled cases

## Quickstart

### Install

```bash
pip install -e ".[dev]"
```

## Dependency Management

The project currently uses a simple split:

- `pyproject.toml` defines the Python package, runtime dependencies, console scripts, and optional dev tools.
- `environment.yml` bootstraps a Conda or Micromamba environment with the Python tooling commonly used in this repo.
- `uv.lock` is not tracked as a repo source of truth. If you use `uv` locally, generate your own lockfile after cloning.

Official local workflow:

```bash
conda env create -f environment.yml
conda activate study-agent
pip install -e ".[dev]"
```

Optional `uv` workflow for users who prefer it:

```bash
uv lock
uv run pytest
```

The repo does not currently require `uv`. Docker builds the runtime in two layers: `environment.yml` provides the Micromamba/Conda base environment, and then `pyproject.toml` is used by `pip install -e .` to install the Python package and console entrypoints inside that environment.

### Start MCP over HTTP

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

This has been tested with [Open webui](https://docs.openwebui.com/), with locally hosted models, and [LLM Shim](https://github.com/dbmi-pitt/llm-shim) with access to cloud services (tested with openai and bedrock models) and an embedding model serviced using the HugginFace Text Embedding Interface service. 

If you want phenotype retrieval, you also need an indexed phenotype library. See [docs/PHENOTYPE_INDEXING.md](docs/PHENOTYPE_INDEXING.md).

Current indexing workflow:

1. Build `catalog.jsonl` plus `sparse_index.pkl` from OHDSI and/or CIPHER source files.
2. Optionally enable LLM-derived retrieval keywords during that build.
3. Build `dense.index` separately when embedding infrastructure is available, either during the main build with `--build-dense` or later with `--build-dense --dense-only`.

The retrieval layer reads from `PHENOTYPE_INDEX_DIR`, which should point to the built output directory. The source phenotype files do not need to live under that directory. In the default Docker/Compose setup, the index is expected on the host at `./data/phenotype_index` and is mounted into the container at `/data/phenotype_index`. If you set `PHENOTYPE_INDEX_DIR` in `.env`, make sure the mounted volume path is updated to match; otherwise the container will still only see the default mounted index location.


## Minimal Examples

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

- Installation, smoke tests, and provider-specific examples: [docs/TESTING.md](docs/TESTING.md)
- Implemented service inventory: [docs/SERVICE_REGISTRY.yaml](docs/SERVICE_REGISTRY.yaml)
- Docker setup: see `compose.yaml` and `.env.example`. The default containerized phenotype index path is `./data/phenotype_index` on the host, mounted to `/data/phenotype_index` in the container.
- ACP and MCP component details: [acp_agent/README.md](acp_agent/README.md), [mcp_server/README.md](mcp_server/README.md)

## Contributing

- Open an issue or discussion if a workflow is unclear or under-documented
- Submit PRs that tighten the implemented workflow docs before adding new service claims
- Join the discussion on the [OHDSI Forums](https://forums.ohdsi.org/t/seeking-input-on-services-that-the-ohdsi-study-agent-will-provide/24890)

## Roadmap

Near-term priorities:

- strengthen phenotype recommendation and improvement workflows for study design and Strategus handoff
- expand Keeper-assisted concept generation and profile-review workflows for phenotype validation
- improve researcher-facing workflow documentation, smoke tests, and deployment guidance

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
