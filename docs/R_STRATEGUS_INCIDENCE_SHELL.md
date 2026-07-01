**Strategus Incidence Shell (R)**

This document summarizes the interactive Strategus incidence shell provided by
`slashOhdsiStrategusAssistant::runStrategusIncidenceShell()`. The shell is intended for
interactive use in R/RStudio and guides users through phenotype selection,
improvement review, time-at-risk configuration, ACP-based Keeper review, and script
generation plus in-shell execution for a CohortIncidence analysis.

## What the shell does

- Prompts for a study intent.
- Calls `phenotype_intent_split` to derive target and outcome cohort statements.
- Calls `phenotype_recommendation` separately for target and outcome cohorts.
- Lets the user select accepted target/outcome phenotypes and optionally remap cohort IDs.
- When the phenotype index is missing a usable cohort, the shell can instead import an existing OHDSI cohort definition from a database schema that exposes `cohort_definition` plus `cohort_definition_details` with `SIMPLE_EXPRESSION` JSON payloads. Imported definitions are validated, cached under the workflow directory, and then treated like local cohort artifacts for the rest of the run.
- Calls `phenotype_improvements` for each selected cohort and lets the user apply improvements immediately.
- Captures explicit time-at-risk and strata settings for the incidence analysis.
- Supports `/back` at major stage boundaries while keeping `/ohdsi` dialogue available during the workflow.
- Optionally runs ACP-based Keeper concept-set and case-review phases inline or writes standalone Keeper scripts. Inline Keeper runs now expose bounded review gates before and after each concept-set domain and before and after case review.
- Writes reproducible scripts for recommendation replay, cohort generation, Keeper review, diagnostics, and incidence analysis.
- Saves session state to `outputs/study_agent_state.json` for traceability.
- Persists `study-agent-project.json` and `outputs/study_agent_runtime_state.json` so generated workflow steps can be run and resumed in the same shell.
- Supports in-shell artifact exploration and controlled return from run mode back to build mode when a revision is needed.

## Output folder layout

Default output directory: `demo-strategus-cohort-incidence/`

- `outputs/`: intent split, recommendations, improvements, roles, Keeper state, and session state.
- `selected-cohorts/`: combined selected cohort JSON + `Cohorts.csv`.
- `selected-target-cohorts/`: target cohort JSON.
- `selected-outcome-cohorts/`: outcome cohort JSON.
- `patched-cohorts/`: combined improved cohort JSON (if applied).
- `patched-target-cohorts/`: improved target cohort JSON (if applied).
- `patched-outcome-cohorts/`: improved outcome cohort JSON (if applied).
- `keeper-case-review/`: ACP Keeper artifacts, generated/approved concept sets, sampled rows, and review outputs.
- `analysis-settings/`: analysis artifacts including `time_at_risk_settings.json` and the generated Strategus specification.
- `scripts/`: generated R scripts (`01` through `07`).

## Generated scripts

The shell writes scripts under `scripts/` for reproducibility:

1. `01_recommend_and_select.R`
2. `02_apply_improvements.R`
3. `03_generate_cohorts.R`
4. `04_keeper_concept_sets.R`
5. `05_keeper_case_review.R`
6. `06_diagnostics.R`
7. `07_incidence_spec.R`
8. `08_launch_diagnostics_explorer.R`

## Execution Menu

After script generation or during `resume = TRUE`, the shell can re-enter run mode inside the same R session.

Current execution-menu capabilities:

- `n` / `run next`: run the next runnable generated step
- `a` / `run all`: keep running until blocked, failed, or complete
- `run <step>`: run a specific runnable step by step number or step id
- `i` / `inspect <step>`: inspect registered outputs for a workflow step in the console
- `art` / `artifacts`: list known workflow artifacts
- `x` / `explore[_v]`: list approved exploration commands for the current workflow state
- `x <command-id>` or `explore <command-id>` or a listed command number: run one approved artifact-exploration command
  Current incidence-specific result views include `incidence_summary_preview` and `incidence_analysis_settings_summary` once incidence results exist.
- `/ohdsi <question>`: ask a contextualized workflow question using the current workflow state
- `rev` / `revise [build|intent|target|outcome]`: leave execution mode and return to build mode, with an option to switch to temporary revision cache mode for this pass

Current behavior notes:

- Exiting the execution menu asks for confirmation unless the workflow is already complete.
- Invalid step or exploration input no longer exits the shell; the menu stays active and prints valid choices.
- `inspect_v <step>` and `explore_v <command-id>` try to open tabular results with `utils::View(...)` when an interactive viewer is available.
- `executionTableDisplay = "console" | "viewer" | "auto"` sets the default rendering mode for `art`, `inspect`, and `explore`. `"viewer"` suppresses console table previews when a viewer is available, and `"auto"` uses the viewer when possible but falls back to console output.
- Build-only steps are tracked in workflow status, but if a step has no generated script it is not treated as runnable during execution mode.

Current runtime expectations:

- `03_generate_cohorts.R`, `06_diagnostics.R`, and `07_incidence_spec.R` expect site-specific Strategus connection/execution settings files under `outputDir`.
- `08_launch_diagnostics_explorer.R` launches `CohortDiagnostics::launchDiagnosticsExplorer()` against the generated diagnostics results and is intended to be run outside the shell runner.
- `04_keeper_concept_sets.R` uses the ACP-based Keeper concept-set helper and writes `outputs/keeper_concept_set_state.json`.
- `05_keeper_case_review.R` uses the ACP-based Keeper case-review helper and writes `outputs/keeper_case_review_state.json`.
- `07_incidence_spec.R` reads `analysis-settings/time_at_risk_settings.json` instead of hard-coding TAR definitions.
- Run `08_launch_diagnostics_explorer.R` in a second R session, RStudio Job, or terminal if you want the workflow shell and `/ohdsi` support to remain available.

Generated scripts that connect to the database expect these site-specific files at the root of
`outputDir`:

- Template `strategus-db-details.json`

```
{
  "dbms": "postgresql",
  "DB_SERVER": "localhost",
  "DB_PORT": "5432",
  "DB_USER": "ohdsi",
  "DB_PASS": "change_me",
  "DB_DRIVER_PATH": "",
  "extraSettings": "sslmode=disable"
}
```

- Template `strategus-execution-settings.json`

```
{
  "cdmDatabaseSchema": "cdm_schema",
  "workDatabaseSchema": "work_schema",
  "resultsDatabaseSchema": "results_schema",
  "vocabularyDatabaseSchema": "vocab_schema",
  "cohortTable": "cohort",
  "workFolder": "demo-strategus-cohort-incidence/work",
  "resultsFolder": "demo-strategus-cohort-incidence/results",
  "cohortIdFieldName": "cohort_definition_id"
}
```


## Notes

- If improvements were applied during the shell session, the scripts are a portable record and do not need to re-apply the same changes.
- The shell exposes `/ohdsi` guidance throughout the workflow and supports `/back` at the major stage boundaries for study intent, target selection, outcome selection, TAR confirmation, and Keeper-review entry. The execution menu help also reminds users that `/ohdsi` remains available during run/resume mode.
- Inline Keeper review uses bounded stage gates rather than a fully generic rewind. Users can skip or rerun domains, inspect generated artifacts, adjust review settings, and inspect saved reviewed rows.
- If no Keeper artifacts exist yet, the shell now suppresses the reuse/resume prompts instead of asking about caches unconditionally.
- If the initial phenotype recommendations are not acceptable, the shell can request a second window of candidates and then fall back to advisory guidance.
