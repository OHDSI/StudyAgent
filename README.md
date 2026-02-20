# Study Design Assistant - ACP + MCP Prototype

This repo refactors the initial proof of concept into a clean separation between an ACP server (agent UX + policy) and MCP servers (tools). It demonstrates how an interactive client can rely on ACP for orchestration while keeping tool logic portable and reusable via MCP.

## What this prototype demonstrates

- ACP server owns interaction policy: confirmations, safe summaries, and tool invocation routing.
- MCP server owns tool contracts: JSON schemas + deterministic tool outputs.
- Core logic stays pure and reusable across both ACP and MCP layers.
### Overview 

## Architecture (current scaffold)

- **ACP agent** (`acp_agent/`): interaction policy + routing; calls MCP tools or falls back to core.
- **MCP server** (`mcp_server/`): exposes tool APIs (core tools plus phenotype retrieval and prompt bundles).
- **Core** (`core/`): pure, deterministic business logic (no IO, no network).

### Preliminary Note and initial roadmap
This project is in a design phase. Check out the tag `proof_of_concept` for the code for the initial coded proof of concepts such as shown [in this video](https://pitt.hosted.panopto.com/Panopto/Pages/Viewer.aspx?id=70502f91-3594-4cb6-b776-b3bd012cf637). See [this branch](https://github.com/OHDSI/StudyAgent/blob/proof-of-concept-mcp-plus-acp/) for demonstration of clean separation between an ACP server (agent UX + policy) and MCP servers (tools). It demonstrates how an interactive client can rely on the emerging [Agent Client Protocol](https://agentclientprotocol.com/overview/introduction) (ACP) for orchestration while keeping tool logic portable and reusable via MCP. These illustrate part of the main architectural concepts. The steps in process now are 1) fleshing out a much larger set of potential Study Agent services, and 2) building out more completely two initial service `phenotype_recommendations` and `phenotype_improvements`.

#### Want to contribute? 

Here are some ways:
- Create a for of the projct, branch the new project's main branch, edit the README.md and do a pull request back this main branch. Your changes could be integrated very quickly that way!
- Join the [discussion on the OHDSI Forums](https://forums.ohdsi.org/t/seeking-input-on-services-that-the-ohdsi-study-agent-will-provide/24890)
- Attend the Generative AI WG monthly calls (currently 2nd Tuesdays of the month at 12 Eastern) or reach out directly to Rich Boyce on the OHDSI Teams.
- You may also post "question" issues on this repo.

### Design 

## Why this separation matters

ACP provides consistent UX and control across environments (R, Atlas/WebAPI, notebooks), while MCP provides a shared tool bus that can be reused across agents and institutions. ACP orchestrates tool calls and LLM calls; MCP owns retrieval, prompt assets, and deterministic tool outputs. This prototype shows how the same core tools can be accessed via MCP or directly by ACP without coupling to datasets or local files.

## Current unit tests 

See `docs/TESTING.md` for install and CLI smoke tests.

## Phenotype Recommendation Flow (ACP + MCP + LLM)

1. ACP calls MCP `phenotype_search` to retrieve candidates.
2. ACP calls MCP `phenotype_prompt_bundle` to fetch prompt assets and output schema.
3. ACP calls an OpenAI-compatible LLM API to rank candidates.
4. Core validates and filters LLM output.

For details on the design, see `docs/PHENOTYPE_RECOMMENDATION_DESIGN.md`.
In one mode of operation, the study agent will have access to output from Data Quality Dashboard, Achilles Heel data quality checks, and Achilles data source characterizations over one or more sources that a user intends to use within a study.  In this mode, specifically designed OHDSI study agent MCP tools will derive insights from those sources based on the user's study intent.  This is important because it will make the information in the characterizations and QC reports more relevant and actionable to users than static and broad-scope reports (current state). 

### Initial Services (draft!)

Below is the first draft of study agent services based on what I am calling "study intent" (a narrative description of the research question) : 

NOTE: at no time for any of the services would an LLM see row-level data (this can be accomplished through the careful use of protocols (MCP for tooling, Agent Client Protocol for OHDSI tool <-> LLM communication) and a security layer). 

#### High level Conceptual
* `protocol_generator`: given the PICO/TAR for a study intent, **write a templated protocol**
* `background_writer`: based on PICO/TAR and hypothesis **do (systematic) research and write document justifying study**
* `protocol_critique`: given a protocol, **write a critique reviewing the protocol for required components and consistency**
* `dag_create`: given a protocol or a study intent statement, **propose a directed acyclic graph of known causal and associative relations** (leveraging LLMs and literature-based discovery methods)

#### High level operational
* `strategus_*`: compose/compare/edit/critique/debug study specification **all of these services edit Strategus .json)** and may utilize one or more of the other services listed below.


#### Search and suggest
* `phenotype_recommendations`: Suggest relevant phenotypes from the thousands of phenotype definitions available from various credible sources (OHDSI Phenotype library, VA CIPHER, a user's own Atlas cohort definitions) for the study intent. **Write cohort definition artifacts** for any phenotype definitions the user accepts as relecant.
* `phenotype_improvements` or `phenotype fit`: Review *already selected* phenotypes for improvements against study intent. Of the use accepts, **write the new artifacts** (JSON cohort definitions or Atlas cohort records)
* `concept_set_recommendations`:Based on a phenotype or covariate relevant to the study intent for which a cohort definition has not been defined, suggest relevant concept sets from sources available to the user (concept set JSON, Atlas) to use in a new cohort definition. **If the user accepts, create the concept set artifacts.** 
* `propose_negative_control_outcomes`: Given a target (and optionally a comparator) recommend outcomes that are unlikely to be caused by the target (nor by the comparator). **If the user accepts, create the cohort definitions for the negative control outcomes**
* `propose_comparator`: Given a target, propose a comparator. This could leverage the [OHDSI Comparator Selector tool](https://data.ohdsi.org/ComparatorSelectionExplorer/). **If the user accepts, create the cohort definition for the comparator**
* `propose_adjustment_set`: Given a study intent statement and a DAG (see `dag_create`), 1) filter the default OHDSI features to an appropriate adjustment set that correctly handles confounders, colliders, and mediators; and 2) suggest features that could be constructed using FeatureExtraction and added to the adjustment set.


#### Study component testing, improvement, and linting  
* `propose_concept_set_diff`: Review concept set for gaps and inconsistencies given the study intent.  **If the user accepts, patch the concept set artifacts.**
* `phenotype_characterize`: **Generate R code** that the user will run, or request the user's permission to **run Atlas services**, to characterize the population of individuals that match a selected phenotype (i.e., same as a cohort characterization)  
* `phenotype_data_quality_review`: Check for likely issues with a set of phenotype definitions and propose mitigation based on information from the Data Quality Dashboard, Achilles Heel data quality checks, and Achilles data source characterizations over the one or more sources that a user intends to use within the study. For issues that the use acknowledges ,  **patch the artifacts** (JSON cohort definitions or Atlas cohort records)
* `phenotype_dataset_profiler`: **Generate R code** to execute a given phenotype definition on multiple datasets (possibly using [Cohort Diagnostics](https://ohdsi.github.io/CohortDiagnostics/)) and **write an brief summary** that compares which phenotype definition elements cause the biggest differences in variation in cohort size (CohortDiagnostics)
* `phenotype_validation_review`: Generate Keeper code for the use to run that will enable them to review case samples from the population of patients meeting a selected phenotype definition. **The agen will write the code to make the sample** such that the user can compare performance characteristics with their sample to known for the phenotype from other sources where it was tested.   
* `cohort_definition_build`: **Write the Capr code** for a use to define a phenotype or covariate relevant to the study intent for which a cohort definition has not yet been defined.
* `cohort_definition_lint`: Review cohort JSON for general design issues (washout/time-at-risk, inverted windows, empty or conflicting criteria) and for execution efficiency (unnecessary criterion nesting, sub-optimal logical ordering of criteria) and **write the proposed patches** (new JSON or new cohort definitions in Atlas)
* `review_negative_control`: Given a target and an outcome, judge whether they are unlikely to be causally related. **Provide a clear explanation for the judgement with accurate citations**

### Initial Architecture - Existing OHDSI tools + Agent Client Protocol (ACP) + Model Context Protocol (MCP)

### Example run for `phenotype_recommendations`

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

## Roadmap

### near term

- `phenotype_improvements`
- `phenotype_validation_review`

Show these tools in use to design, run, and interpret the results of an OHDSI incidence rate analysis using the [CohortIncidenceModule](https://raw.githubusercontent.com/OHDSI/Strategus/main/inst/doc/CreatingAnalysisSpecification.pdf) of  [OHDSI Strategus](https://github.com/OHDSI/Strategus) 
