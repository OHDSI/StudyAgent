# OHDSI Assistant Prototype

This repo contains:
- A tiny **ACP-like bridge** (`acp/server.py`) exposing:
  - `/tools/propose_concept_set_diff` (concept-sets-review)
  - `/tools/cohort_lint` (cohort-critique-general-design)
- An **R package** `OHDSIAssistant` with `lintStudyDesign()` that calls the bridge (or uses a local fallback).
- A **demo** study in `demo/`.

Currently, this is a minimalistic demo
- basic concept set and cohort definition checks

Ideas for further implementation
- suggestions for use of specific OHDSI phenotypes within a study
- flagged issues with the source data wrt to the concept sets and/or cohort definitions based on data from DQD and Achilles
- adapatations of cohort definitions using OHDSI phenotypes for the specific study use case
- a review of study artifacts (cohort definitions and concept set) from a causal inference and identification theory perspective
- add AI generated doc comments to cohort definition,
- generate R code or Atlas/WebAPI custom features from Atlas cohorts,
- generate R code SQL-based custom features,
- explain and address Circe-Be checks within R or Atlas/WebAPI
- manage configuration within Atlas/WebAPI such as security reviews, and clean up of concept sets and cohort definitions


## Quick start

1) Start bridge:

```bash
./scripts/start_acp.sh
```

Optional) Use another ACP-style CLI backend:

```bash
export ACP_MODEL_CMD="my-cli --reads-stdin"  # prompt sent via stdin; must return JSON
./scripts/start_acp.sh
```

Optional) Use OpenWebUI HTTP backend (recommended):

```bash
export OPENWEBUI_API_KEY="..."  # required
export OPENWEBUI_API_URL="http://localhost:3000/api/chat/completions"  # default
export OPENWEBUI_MODEL="agentstudyassistant"  # default
export FLASK_DEBUG=1 # Optional but helpful
./scripts/start_acp.sh
```

In R:

```r
devtools::load_all("R/OHDSIAssistant")
OHDSIAssistant::acp_connect("http://127.0.0.1:7777")
OHDSIAssistant::lintStudyDesign(
  studyProtocol = "demo/protocol.md",
  studyPackage  = "demo",
  lintTasks     = c("concept-sets-review","cohort-critique-general-design"),
  apply         = FALSE,
  interactive   = TRUE
)
```

You'll see plans, findings, and suggested patches. Advice logs are saved under demo/inst/assistant/.

Executable action (concept-set includeDescendants helper):

```r
patch <- OHDSIAssistant::proposeIncludeDescendantsPatch("demo/concept_set.json")
OHDSIAssistant::previewConceptSetPatch("demo/concept_set.json", patch)
OHDSIAssistant::applyConceptSetPatch("demo/concept_set.json", patch, backup = TRUE)
```

Phenotype suggestions (stubbed if no LLM):

```r
devtools::load_all("R/OHDSIAssistant")
OHDSIAssistant::acp_connect("http://127.0.0.1:7777")  # optional; falls back to stub
rec <- OHDSIAssistant::suggestPhenotypes("demo/protocol.md", "demo/Cohorts.csv", maxResults = 3)
ids <- OHDSIAssistant::selectPhenotypeRecommendations(rec$phenotype_recommendations, interactive = TRUE)
paths <- OHDSIAssistant::pullPhenotypeDefinitions(ids, outputDir = "demo")
OHDSIAssistant::reviewPhenotypes("demo/protocol.md", paths)
# Optionally persist improvement notes next to the cohort JSONs
OHDSIAssistant::reviewPhenotypes("demo/protocol.md", paths, apply = TRUE, select = "all")
```

LLM actions (preview/apply model-proposed edits):

```r
resp <- OHDSIAssistant:::`.acp_post`("/tools/propose_concept_set_diff", list(
  conceptSetRef = "demo/concept_set.json",
  studyIntent   = paste(readLines("demo/protocol.md", warn = FALSE), collapse = " ")
))
OHDSIAssistant::applyLLMActionsConceptSet("demo/concept_set.json", resp$actions, preview = TRUE)
```

Next steps

Replace "note" patches with executable JSON Patch aligned to ATLAS schema.

Add WebAPI resolvers for webapi://cohort/<id> and webapi://conceptSet/<id>.

Pull in Achilles/DQD summaries to drive severity and evidence links.
