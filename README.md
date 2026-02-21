# OHDSI Study Design Assistant (in development)

## Overview

The goal OHDSI Study Design Assistant (SDA) is to provide an experience similar to working with a coding agent but for designing and executing observational retrospective studies using OHDSI tools. SDA is designed to organize and enable users to interact with a wide variety of agentic tools to suppor their study work.  It does so by providing a clean separation between the agentic user experience and the generative AI tools. Check out the tag `proof_of_concept` for the code for the initial coded proof of concepts such as shown [in this video](https://pitt.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=70502f91-3594-4cb6-b776-b3bd012cf637). See [this branch](https://github.com/OHDSI/StudyAgent/blob/proof-of-concept-mcp-plus-acp/) 
 
#### Want to contribute? 

Here are some ways:
- Create a fork of the project, branch the new project's main branch, edit the README.md and do a pull request back this main branch. Your changes could be integrated very quickly that way!
- Join the [discussion on the OHDSI Forums](https://forums.ohdsi.org/t/seeking-input-on-services-that-the-ohdsi-study-agent-will-provide/24890)
- Attend the Generative AI WG monthly calls (currently 2nd Tuesdays of the month at 12 Eastern) or reach out directly to Rich Boyce on the OHDSI Teams or the OHDSI forums.
- You may also post "question" issues on this repo.

### Roadmap

### Near term

Show the phenotype_* tools in use to design, run, and interpret the results of an OHDSI incidence rate analysis using the [CohortIncidenceModule](https://raw.githubusercontent.com/OHDSI/Strategus/main/inst/doc/CreatingAnalysisSpecification.pdf) of  [OHDSI Strategus](https://github.com/OHDSI/Strategus) 

Extend the study agent so it uses results from Data Quality Dashboard, Achilles Heel data quality checks, and Achilles data source characterizations over one or more sources that a user intends to use within a study.  In this mode, the study agent derive insights from those sources based on the user's study intent.  This is important because it will make the information in the characterizations and QC reports more relevant and actionable to users than static and broad-scope reports (current state). 

### Long term

Build out the entire set of planned services, each one evaluated and user-tested.

## Design 

- An [Agent Client Protocol](https://agentclientprotocol.com/get-started/introduction) (ACP) server that owns interaction policy: confirmations, safe summaries, and tool invocation routing.
   - `acp_agent/`: interaction policy + routing; calls MCP tools or falls back to core.
   
- Multiple MCP servers that own tool contracts: JSON schemas + deterministic tool outputs.
   - `mcp_server/`: exposes tool APIs (core tools plus phenotype retrieval and prompt bundles).

- Core logic stays pure and reusable across both ACP and MCP layers.
   - `core/`: pure, deterministic business logic (no IO, no network).

### Why this architecture matters

ACP provides consistent UX and control across environments (R, Atlas/WebAPI, notebooks), while MCP provides a shared tool bus that can be reused across agents and institutions. ACP orchestrates tool calls and LLM calls; MCP owns retrieval, prompt assets, and deterministic tool outputs. This enables the same core tools can be accessed via MCP or directly by ACP without coupling to datasets or local files.

NOTE: at no time for any of the services should an LLM see row-level data (this can be accomplished through the careful use of protocols (MCP for tooling, Agent Client Protocol for OHDSI tool <-> LLM communication) and a security layer). 


## What is implemented so far?

### Current unit tests 

See `docs/TESTING.md` for install and CLI smoke tests.

### `phenotype_recommendation` flow (ACP + MCP + LLM)

1. ACP calls MCP `phenotype_search` to retrieve candidates.
2. ACP calls MCP `phenotype_prompt_bundle` to fetch prompt assets and output schema.
3. ACP calls an OpenAI-compatible LLM API to rank candidates.
4. Core validates and filters LLM output.

For details on the design, see `docs/PHENOTYPE_RECOMMENDATION_DESIGN.md`.

### `phenotype_improvements` flow (ACP + MCP + LLM)

1. ACP calls MCP `phenotype_prompt_bundle` for improvement prompts.
2. ACP calls an OpenAI-compatible LLM API for improvement suggestions.
3. ACP calls MCP `phenotype_improvements` with LLM output for validation.

This flow reviews one phenotype definition at a time. If multiple cohorts are provided, ACP uses the first.

### `concept-sets-review` flow (ACP + MCP + LLM)

1. ACP calls MCP `lint_prompt_bundle` for lint prompts.
2. ACP calls an OpenAI-compatible LLM API for findings/patches/actions.
3. ACP calls MCP `propose_concept_set_diff` with LLM output for validation.

### `cohort-critique-general-design` flow (ACP + MCP + LLM)

1. ACP calls MCP `phenotype_prompt_bundle` for cohort critique prompts.
2. ACP calls an OpenAI-compatible LLM API for findings/patches.
3. ACP calls MCP `cohort_lint` with LLM output for validation.

### `phenotype_validation_review` flow (ACP + MCP + LLM)

1. ACP calls MCP `keeper_sanitize_row` to remove PHI/PII (fail-closed).
2. ACP calls MCP `keeper_prompt_bundle` and `keeper_build_prompt` for a sanitized patient prompt.
3. ACP calls an OpenAI-compatible LLM API to review the patient summary.
4. ACP calls MCP `keeper_parse_response` to normalize the label.

LLM requests never include row-level PHI/PII; only sanitized summaries are sent.

For details on PHI/PII handling, see `docs/PHENOTYPE_VALIDATION_REVIEW.md`.

### Service Registry

Service definitions live in `docs/SERVICE_REGISTRY.yaml`. ACP exposes a `/services` endpoint that
reports registry entries plus any additional ACP-implemented services. You can list services
quickly with `doit list_services`.

#### Example run for `phenotype_recommendations`

*Prerequisite:* you have embedded phenotype definitions - see `./docs/PHENOTYPE_INDEXING.md`

1. Start the ACP server (runs on http://127.0.0.1:8765/ by default):
```bash
export LLM_API_KEY=<YOUR KEY>
export LLM_API_URL="<URL BASE>/api/chat/completions"
export LLM_LOG=1
export LLM_MODEL=<a model that supports completions> 
export EMBED_API_KEY=<YOUR KEY>
export EMBED_MODEL=<a text embedding model>
export EMBED_URL="<URL BASE>/ollama/api/embed"
export STUDY_AGENT_HOST=127.0.0.1
export STUDY_AGENT_PORT=8765
export STUDY_AGENT_MCP_COMMAND=study-agent-mcp
export STUDY_AGENT_MCP_ARGS=""
study-agent-acp
```

2. Run `phenotype_recommendation`
```bash
curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
  -H 'Content-Type: application/json' \
  -d '{"study_intent":"Identify clinical risk factors for older adult patients who experience an adverse event of acute gastro-intenstinal (GI) bleeding", "top_k":20, "max_results":10,"candidate_limit":10}'
```

## Planned Services

Below is a set of planned study agent services, organized by category. For each service, document the input, output, and validation approach.

### High Level Conceptual

#### `protocol_generator`
**Input:** PICO/TAR for a study intent.  
**Output:** Templated protocol.  
**Validation:** Protocol completeness and consistency review.

#### `background_writer`
**Input:** PICO/TAR and hypothesis.  
**Output:** Background document justifying the study (systematic research summary).  
**Validation:** Source coverage and alignment with hypothesis.

#### `protocol_critique`
**Input:** Protocol.  
**Output:** Critique reviewing required components and consistency.  
**Validation:** Checklist of required components; coherence checks.

#### `dag_create`
**Input:** Protocol or study intent statement.  
**Output:** Directed acyclic graph of known causal/associative relations (LLM + literature discovery).  
**Validation:** Consistency with cited relations and domain plausibility.

### High Level Operational

#### `strategus_*`
**Input:** Study specification intent or existing Strategus JSON.  
**Output:** Composed/compared/edited/criticized/debugged Strategus JSON.  
**Validation:** Schema validation and diff review.

### Search and Suggest

#### `phenotype_recommendations`
**Input:** Study intent.  
**Output:** Suggested phenotypes with cohort definition artifacts for user-accepted selections.  
**Validation:** Allowed-id filtering; user confirmation before writes.

#### `phenotype_improvements` (or `phenotype fit`)
**Input:** Selected phenotypes + study intent.  
**Output:** Improved cohort definitions or Atlas records for accepted changes.  
**Validation:** Target cohort ID validation; user confirmation before writes.

#### `concept_set_recommendations`
**Input:** Phenotype/covariate intent lacking a cohort definition.  
**Output:** Suggested concept sets and created concept set artifacts if accepted.  
**Validation:** Concept set schema validation; user confirmation before writes.

#### `propose_negative_control_outcomes`
**Input:** Target (optionally comparator).  
**Output:** Recommended negative control outcomes with cohort definitions if accepted.  
**Validation:** Clinical plausibility check; user confirmation before writes.

#### `propose_comparator`
**Input:** Target.  
**Output:** Proposed comparator cohort definition if accepted (optionally using OHDSI Comparator Selector).  
**Validation:** Comparator appropriateness review; user confirmation before writes.

#### `propose_adjustment_set`
**Input:** Study intent + DAG.  
**Output:** Adjustment set from OHDSI features plus suggested FeatureExtraction features.  
**Validation:** Confounder/collider/mediator checks against DAG.

### Study Component Testing, Improvement, and Linting

#### `propose_concept_set_diff`
**Input:** Concept set + study intent.  
**Output:** Proposed patches to concept set artifacts if accepted.  
**Validation:** Deterministic diff rules; user confirmation before writes.

#### `phenotype_characterize`
**Input:** Selected phenotype(s).  
**Output:** R code (or Atlas services) to characterize populations.  
**Validation:** Execution preview; user confirmation before running.

#### `phenotype_data_quality_review`
**Input:** Phenotype definitions + data quality sources (DQD, Achilles Heel, characterization).  
**Output:** Mitigations and patches for accepted issues.  
**Validation:** Issue traceability to data quality sources; user confirmation before writes.

#### `phenotype_dataset_profiler`
**Input:** Phenotype definition(s) + datasets.  
**Output:** R code to run (e.g., Cohort Diagnostics) and a brief summary of drivers of cohort size variation.  
**Validation:** Reproducible execution outputs; summary tied to diagnostics.

#### `phenotype_validation_review`
**Input:** Selected phenotype definition(s).  
**Output:** Code to sample cases for validation and compare to known phenotype performance.  
**Validation:** Sampling logic review; user confirmation before running.

#### `cohort_definition_build`
**Input:** Phenotype/covariate intent without a cohort definition.  
**Output:** Capr code for cohort definition.  
**Validation:** Schema validation; user confirmation before writes.

#### `cohort_definition_lint`
**Input:** Cohort JSON.  
**Output:** Proposed patches for design issues and execution efficiency.  
**Validation:** Deterministic lint rules; user confirmation before writes.

#### `review_negative_control`
**Input:** Target + outcome.  
**Output:** Judgement on causal implausibility with explanation and citations.  
**Validation:** Citation review and domain plausibility.
