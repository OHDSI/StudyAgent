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

## Suggest Cohort Method Specifications

Use `suggestCohortMethodSpecs()` when you want ACP to turn a free-text analytic-settings description into a CohortMethod recommendation without running the full shell.

```r
OHDSIAssistant::acp_connect("http://127.0.0.1:8765")

res <- OHDSIAssistant::suggestCohortMethodSpecs(
  studyIntent = "What is the risk of angioedema or acute myocardial infarction in new users of ACE inhibitors compared to new users of thiazide and thiazide-like diuretics?",
  analyticSettingsDescription = "Use one-to-one propensity score matching, a 365-day washout, and a Cox outcome model.",
  interactive = TRUE
)
```

The helper calls ACP `/flows/cohort_methods_specifications_recommendation`. When ACP is not connected, it returns a local stub with the same broad response shape.

## Strategus Cohort Methods Shell

Use `runStrategusCohortMethodsShell()` when you want the full cohort-methods workflow: intent split, target/comparator/outcome recommendation or explicit cohort IDs, analytic-settings collection, output artifacts, generated R scripts, and a merged `06_cm_spec.R` that builds and executes the Strategus specification.

Fully interactive run:

```r
OHDSIAssistant::acp_connect("http://127.0.0.1:8765")

OHDSIAssistant::runStrategusCohortMethodsShell()
```

Provide only the study intent and let the shell recommend/select target, comparator, and outcome cohorts:

```r
OHDSIAssistant::runStrategusCohortMethodsShell(
  studyIntent = "What is the risk of angioedema or acute myocardial infarction in new users of ACE inhibitors compared to new users of thiazide and thiazide-like diuretics?"
)
```

Provide explicit cohort IDs when you already know the target, comparator, and outcome cohorts:

```r
OHDSIAssistant::acp_connect("http://127.0.0.1:8765")

OHDSIAssistant::runStrategusCohortMethodsShell(
  outputDir = "demo-strategus-cohort-methods",
  studyIntent = "What is the risk of angioedema or acute myocardial infarction in new users of ACE inhibitors compared to new users of thiazide and thiazide-like diuretics?",
  targetCohortId = 12345,
  comparatorCohortId = 23456,
  outcomeCohortIds = c(34567, 45678),
  comparisonLabel = "ace_inhibitors_vs_thiazide_diuretics"
)
```

To exercise the analytic-settings flow with stable demo inputs, pass explicit target/comparator/outcome IDs and either choose `step_by_step` when prompted or provide a free-text description:

```r
OHDSIAssistant::runStrategusCohortMethodsShell(
  outputDir = "demo-strategus-cohort-methods-analytic-settings",
  studyIntent = "What is the risk of angioedema or acute myocardial infarction in new users of ACE inhibitors compared to new users of thiazide and thiazide-like diuretics?",
  targetCohortId = 12345,
  comparatorCohortId = 23456,
  outcomeCohortIds = c(34567),
  comparisonLabel = "ace_inhibitors_vs_thiazide_diuretics",
  analyticSettingsDescription = "Use one-to-one propensity score matching and a Cox outcome model."
)
```

The shell writes outputs under `outputDir`, including `outputs/cm_analysis_defaults.json`, `outputs/cm_acp_specifications_recommendation.json` for free-text mode, `analysis-settings/cmAnalysis.json`, `analysis-settings/analysisSpecification.json`, and scripts under `scripts/`.

Generated scripts are:

1. `02_apply_improvements.R`
2. `03_generate_cohorts.R`
3. `04_keeper_review.R`
4. `05_diagnostics.R`
5. `06_cm_spec.R`

Before running scripts that connect to the database, place these two files at the root of
`outputDir`:

```text
<outputDir>/strategus-db-details.json
<outputDir>/strategus-execution-settings.json
```

`strategus-db-details.json`:

```json
{
  "dbms": "postgresql",
  "DB_SERVER": "localhost/database_name",
  "DB_PORT": "5432",
  "DB_USER": "ohdsi",
  "DB_PASS": "change_me",
  "DB_DRIVER_PATH": "~/jdbcDrivers",
  "extraSettings": "sslmode=disable"
}
```

`strategus-execution-settings.json`:

```json
{
  "cdmDatabaseSchema": "cdm_schema",
  "workDatabaseSchema": "work_schema",
  "resultsDatabaseSchema": "results_schema",
  "vocabularyDatabaseSchema": "vocab_schema",
  "cohortTable": "cohort",
  "workFolder": "demo-strategus-cohort-methods/work",
  "resultsFolder": "demo-strategus-cohort-methods/results",
  "cohortIdFieldName": "cohort_definition_id",
  "maxCores": 1
}
```

