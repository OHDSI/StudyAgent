# Strategus Cohort Methods Shell

Current stage scope:

- Cohort methods shell with ACP-assisted intent split and phenotype recommendation.
- The shell can derive target/comparator/outcome statements from a study intent.
- The shell can configure one effective analytic-settings profile through `step_by_step` prompts or `free_text` ACP recommendation.
- The shell writes reproducible R scripts, a Strategus analysis specification, and a merged CohortMethod execution script.
- The shell also supports in-shell run/resume mode for generated workflow steps, artifact exploration, and controlled return to build mode when revisions are needed.
- The Keeper review step is now ACP-based and does not call the legacy Keeper R package.

This shell is provided as `slashOhdsiStrategusAssistant::runStrategusCohortMethodsShell()`.

## Running

Usage examples for `slashOhdsiStrategusAssistant::runStrategusCohortMethodsShell()` live in `scripts/demo_strategus_cohort_method.R`. Package-level shell notes live in `R/slashOhdsiStrategusAssistant/README.md`.

Workflow diagrams live in `docs/WORKFLOW_COHORT_METHODS.md`.

## Current Stage Flow

1. Manual collection of required identifiers:
   - `studyIntent`
2. ACP-assisted split of `studyIntent` into:
   - `targetStatement`
   - `comparatorStatement`
   - one or more outcome statements (`outcomeStatement` remains the primary/first outcome for compatibility)
   - when multiple outcome statements are suggested interactively, choose the subset to keep or enter none/0 to provide a manual outcome before editing or adding statements
3. Role-specific phenotype recommendation / cache reuse for target, comparator, and outcome cohorts.
   Interactive runs ask for short analysis labels for selected cohorts and the comparison; labels must
   be 100 characters or fewer because downstream Strategus/Characterization result tables use short
   identifier fields.
4. Optional cohort ID remap step to avoid collisions (`remapCohortIds`).
5. Copy cohort JSON definitions from `indexDir/definitions` into selected cohort folders.
6. Optional negative control and covariate concept-set IDs are still captured as placeholders.
7. Configure one analytic-settings profile through `step_by_step`, `free_text`, or cached/function-argument inputs.
   Analytic settings are always collected in this stage and confirmed before finalization.
8. Optionally run ACP-based Keeper review inline with reuse/resume controls and bounded Keeper stage gates around domain generation and case review.
9. Generate scripts in `scripts/` for cohort generation, Keeper review, diagnostics, and CohortMethod spec/execution, including `07_cm_spec.R`.
10. Optionally enter run/resume mode in the same shell to execute generated steps, inspect artifacts, ask `/ohdsi` questions, or return to build mode with `revise ...`.

## Analytic Settings

The cohort methods shell resolves a single effective analytic-settings profile. This remains
prompt/cache/free-text-driven only; there is no public function argument that accepts a complete
analytic-settings object in this stage.

Supported configuration modes:

- `step_by_step`
- `free_text`

At a high level:

- `step_by_step` covers study population, time-at-risk, propensity score adjustment, and outcome model settings.
- `free_text` uses an ACP recommendation when available and falls back to a local stub if ACP is unavailable.
- Persisted JSON keeps the existing `CohortMethod`-aligned field names.

The effective selected profile is written to `outputs/cm_analysis_defaults.json`, which retains
profile metadata such as `profile_name`, `source`, and `customized_sections`. The generated
`scripts/06_cm_spec.R` combines those defaults with `outputs/cm_comparisons.json` and the selected
cohort definitions to create a Strategus analysis specification.

For traceability:

- `outputs/manual_inputs.json` stores the effective `analytic_settings` block plus the
  `customized_sections` array, the selected analytic-settings mode, and any free-text metadata.
- `outputs/cm_analytic_settings_recommendation.json` is written only for `free_text` mode. It stores the shell-facing recommendation derived from the ACP response or, if ACP is unavailable, from the local fallback.
- `outputs/cm_acp_specifications_recommendation.json` is written for `free_text` mode and stores the ACP flow request/response wrapper used to derive the shell-facing recommendation.
- `outputs/study_agent_state.json` echoes analytic-settings summary information plus the Keeper control settings used during the shell session.
- `analysis-settings/cmAnalysis.json` stores the template-shaped CohortMethod-oriented contract artifact.

## Output Layout

The following directories are created under `outputDir`:

- `outputs/`
- `selected-cohorts/`
- `selected-target-cohorts/`
- `selected-comparator-cohorts/`
- `selected-outcome-cohorts/`
- `patched-cohorts/`
- `patched-target-cohorts/`
- `patched-comparator-cohorts/`
- `patched-outcome-cohorts/`
- `keeper-case-review/`
- `concept-sets/`
- `analysis-settings/`
- `scripts/`
- `cm-results/`
- `cm-diagnostics/`
- `cm-data/`

### `outputs/` artifacts

- `manual_intent.json`
- `manual_inputs.json`
- `cohort_methods_intent_split.json`
- `cohort_id_map.json`
- `cohort_roles.json`
- `recommendations_target.json`
- `recommendations_comparator.json`
- `recommendations_outcome.json`
- `recommendations_outcome_<n>.json` (when multiple outcome statements are recommended separately)
- `cm_comparisons.json`
- `cm_analysis_defaults.json`
- `cm_acp_specifications_recommendation.json` (free-text mode only)
- `cm_analytic_settings_recommendation.json` (free-text mode only)
- `cm_concept_set_selections.json`
- `improvements_target.json`
- `improvements_comparator.json`
- `improvements_outcome.json`
- `improvements_status.json`
- `cm_evaluation_todo.json`
- `cm_analysis_state.json` (written by `scripts/07_cm_spec.R`)
- `keeper_concept_set_state.json` (written by inline or standalone ACP Keeper concept-set workflow)
- `keeper_case_review_state.json` (written by inline or standalone ACP Keeper case-review workflow)
- `study_agent_state.json`
- `study-agent-project.json`
- `outputs/study_agent_runtime_state.json`

## Generated Scripts

- `scripts/02_apply_improvements.R`
- `scripts/03_generate_cohorts.R`
- `scripts/04_keeper_concept_sets.R`
- `scripts/05_keeper_case_review.R`
- `scripts/06_diagnostics.R`
- `scripts/07_cm_spec.R`

Build vs run note:

- `recommend_and_select` is completed interactively during build mode and is tracked in `study-agent-project.json`, but there is no standalone `scripts/01_recommend_and_select.R`.
- In execution mode, build-only steps are shown in workflow status but are not treated as runnable generated scripts.

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
  Diagnostics review remains file- and artifact-based inside the runner; the Shiny diagnostics explorer is launched from a separate generated script.
- `/ohdsi <question>`: ask a contextualized workflow question using the current workflow state
- `rev` / `revise [build|intent|target|comparator|outcome]`: leave execution mode and return to build mode, with an option to switch to temporary revision cache mode for this pass

Current behavior notes:

- Exiting the execution menu asks for confirmation unless the workflow is already complete.
- Invalid step or exploration input no longer exits the shell; the menu stays active and prints valid choices.
- `inspect_v <step>` and `explore_v <command-id>` try to open tabular results with `utils::View(...)` when an interactive viewer is available.
- `executionTableDisplay = "console" | "viewer" | "auto"` sets the default rendering mode for `art`, `inspect`, and `explore`. `"viewer"` suppresses console table previews when a viewer is available, and `"auto"` uses the viewer when possible but falls back to console output.


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
  "workFolder": "demo-strategus-cohort-method/work",
  "resultsFolder": "demo-strategus-cohort-method/results",
  "cohortIdFieldName": "cohort_definition_id"
}
```


Current Keeper specifics:

- `scripts/04_keeper_concept_sets.R` uses `runKeeperConceptSetWorkflow(...)` and writes `outputs/keeper_concept_set_state.json`.
- `scripts/05_keeper_case_review.R` uses `runKeeperCaseReviewWorkflow(...)` and writes `outputs/keeper_case_review_state.json`.
- `scripts/08_launch_diagnostics_explorer.R` launches `CohortDiagnostics::launchDiagnosticsExplorer()` against the generated diagnostics results and should be run in a second R session if you want the shell and `/ohdsi` to remain available.
- Inline Keeper review now exposes bounded stage gates before and after each requested concept-set domain and before and after case review.
- The generated Keeper scripts expose `ACP_TIMEOUT`, concept-set reuse/overwrite, row reuse/resume, and explicit row selection controls such as `1-3,5`.
- Manual editing of `keeper-case-review/concept-sets-approved/*.json` is consumable, but the concept-set approve/edit/rerun UX is still incomplete.

## Current Boundaries

- `phenotype_improvements` is wired for target, comparator, and outcome cohorts. The shell writes role-specific improvement artifacts after prompting whether to run improvements for each role, can apply mutating actions (`set`, `replace`, `update`), keeps advisory `note` actions as recommendations, and keeps `patched-cohorts/` complete for downstream scripts when any mutating improvement is applied.
- Remaining deferred integration points:
  - comparator reuse lookup
  - phenotype index search for suggestion workflows
- Atlas settings deferred in this stage:
  - negative control cohort-definition logic
  - positive control synthesis
  - empirical calibration configuration
  - detailed covariate feature-group selection beyond the current default-plus-include/exclude model
- TODO: implement ACP/MCP support for negative control and covariate concept-set workflows, then update the shell to use those tools instead of writing dummy placeholder concept-set artifacts.
- Covariate concept-set include/exclude is not fully implemented yet. Because the generated CohortMethod scripts cannot currently materialize exclude covariate concepts, high-correlation covariates may remain in the model and cause `06_cm_spec.R` to fail when `errorOnHighCorrelation` is enabled.
- Analytic-settings recommendations are mapped into shell settings before script generation, but there is not yet a dedicated validation layer for ACP recommendation payloads.
- Multiple analytic-settings profiles and multi-comparison support remain for a later stage.

## Notes

- This stage is designed as a bridge: it combines ACP/MCP-assisted intent split, phenotype recommendation/improvement, analytic-settings recommendation, and ACP-based Keeper review with reproducible Strategus script generation.
- Interactive runs support `/back` at major stage boundaries for study intent, target selection, comparator selection, outcome selection, study configuration, and Keeper-review entry while keeping `/ohdsi` available for contextual guidance. The execution menu help now also reminds users that `/ohdsi` is available during run/resume mode.
- If no Keeper artifacts exist yet, the shell suppresses the inline Keeper reuse/resume prompts instead of asking about caches unconditionally.
