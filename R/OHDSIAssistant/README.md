# OHDSIAssistant (R) - ACP Client

This package provides a thin R client for the ACP study agent. It assumes the ACP server is already running and accessible over HTTP.

## Quick Start

```r
devtools::load_all("R/OHDSIAssistant")
OHDSIAssistant::acp_connect("http://127.0.0.1:8765")
```

## Phenotype Recommendations (ACP Flow)

File-based study intent:

```r
rec <- OHDSIAssistant::suggestPhenotypes(
  protocolPath = "demo/protocol.md",
  maxResults = 10,
  candidateLimit = 10,
  interactive = TRUE
)
```

Direct study intent:

```r
rec <- OHDSIAssistant::suggestPhenotypes(
  studyIntent = "Identify clinical risk factors for older adults with GI bleeding in hospital settings.",
  maxResults = 10
)
```

Interactive prompt (if no intent provided):

```r
rec <- OHDSIAssistant::suggestPhenotypes()
```

## Notes

- The ACP server must be running and configured with its MCP connection.
- The R client calls ACP `/flows/phenotype_recommendation`.
- The response includes `recommendations`, which contains the validated core output.

## Strategus Incidence Shell (ACP-assisted, outputs pure R)

This helper runs an interactive, ACP-backed design session and writes a set of clean R scripts
that do not require ACP to run at other sites.

```r
OHDSIAssistant::runStrategusIncidenceShell(
  outputDir = "demo-strategus-cohort-incidence",
  studyIntent = "What is the risk of GI bleed in new users of Celecoxib compared to new users of Diclofenac?"
)
```

It generates scripts under `demo-strategus-cohort-incidence/scripts/` following the flow:

1. `01_recommend_and_select.R`
2. `02_apply_improvements.R`
3. `03_generate_cohorts.R`
4. `04_keeper_review.R`
5. `05_diagnostics.R`
6. `06_incidence_spec.R`
