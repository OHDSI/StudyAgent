**Strategus Incidence Shell (R)**

This document summarizes the interactive Strategus incidence shell provided by
`slashOhdsiStrategusAssistant::runStrategusIncidenceShell()`. The shell is intended for
interactive use in R/RStudio and guides users through phenotype selection,
improvement review, time-at-risk configuration, ACP-based Keeper review, and script
generation for a CohortIncidence analysis.

## What the shell does

- Prompts for a study intent.
- Calls `phenotype_intent_split` to derive target and outcome cohort statements.
- Calls `phenotype_recommendation` separately for target and outcome cohorts.
- Lets the user select accepted target/outcome phenotypes and optionally remap cohort IDs.
- Calls `phenotype_improvements` for each selected cohort and lets the user apply improvements immediately.
- Captures explicit time-at-risk and strata settings for the incidence analysis.
- Optionally runs ACP-based Keeper review inline or writes a standalone Keeper script.
- Writes reproducible scripts for recommendation replay, cohort generation, Keeper review, diagnostics, and incidence analysis.
- Saves session state to `outputs/study_agent_state.json` for traceability.

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
- `scripts/`: generated R scripts (`01` through `06`).

## Generated scripts

The shell writes scripts under `scripts/` for reproducibility:

1. `01_recommend_and_select.R`
2. `02_apply_improvements.R`
3. `03_generate_cohorts.R`
4. `04_keeper_review.R`
5. `05_diagnostics.R`
6. `06_incidence_spec.R`

Current runtime expectations:

- `03_generate_cohorts.R`, `05_diagnostics.R`, and `06_incidence_spec.R` expect site-specific Strategus connection/execution settings files under `outputDir`.
- `04_keeper_review.R` uses the ACP-based Keeper workflow helper and writes `outputs/keeper_review_state.json`.
- `06_incidence_spec.R` reads `analysis-settings/time_at_risk_settings.json` instead of hard-coding TAR definitions.

## Notes

- If improvements were applied during the shell session, the scripts are a portable record and do not need to re-apply the same changes.
- The shell exposes a `/ohdsi` dialogue step for `time_at_risk_configuration`, so users can ask denominator-design questions while configuring TAR and strata settings.
- If the initial phenotype recommendations are not acceptable, the shell can request a second window of candidates and then fall back to advisory guidance.
