**Strategus Incidence Shell (R)**

This document summarizes the interactive Strategus incidence shell provided by
`OHDSIAssistant::runStrategusIncidenceShell()`. The shell is intended for
interactive use in R/RStudio and guides users through phenotype selection and
script generation for a CohortIncidence analysis.

## What the shell does

- Prompts for a study intent (with a default).
- Calls `phenotype_intent_split` to derive target and outcome cohort statements.
- Calls `phenotype_recommendation` separately for target and outcome cohorts.
- Lets the user select accepted target/outcome phenotypes and optionally remap cohort IDs.
- Calls `phenotype_improvements` for each selected cohort (target then outcome) and lets
  the user apply improvements immediately.
- Writes reproducible scripts for cohort generation, Keeper review, diagnostics,
  and incidence analysis.
- Saves session state to `outputs/study_agent_state.json` for traceability.

## Output folder layout

Default output directory: `demo-strategus-cohort-incidence/`

- `outputs/`: intent split, recommendations, improvements, roles, and session state.
- `selected-cohorts/`: combined selected cohort JSON + `Cohorts.csv`.
- `selected-target-cohorts/`: target cohort JSON.
- `selected-outcome-cohorts/`: outcome cohort JSON.
- `patched-cohorts/`: combined improved cohort JSON (if applied).
- `patched-target-cohorts/`: improved target cohort JSON (if applied).
- `patched-outcome-cohorts/`: improved outcome cohort JSON (if applied).
- `keeper-case-review/`: Keeper outputs and review artifacts.
- `analysis-settings/`: analysis specification JSON.
- `scripts/`: generated R scripts (01–06).

## Generated scripts

The shell writes scripts under `scripts/` for reproducibility:

1. `03_generate_cohorts.R`
2. `04_keeper_review.R`
3. `05_diagnostics.R`
4. `06_incidence_spec.R`

Scripts include database connection initialization using
`strategus-db-details.json` in the working directory.

## Notes

- If improvements were applied during the shell session, the scripts are marked
  as a portable record (no need to re-apply).
- If the initial recommendations are not acceptable, the shell can request a
  second window of candidates and then fall back to advisory guidance.
