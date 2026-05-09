# Strategus Cohort Methods Shell

Current stage scope:

- Cohort methods shell with ACP-assisted intent split and phenotype recommendation.
- The shell can derive target/comparator/outcome statements from a study intent.
- The shell can configure one effective analytic-settings profile through `step_by_step` prompts or `free_text` ACP recommendation.
- The shell writes reproducible R scripts, a Strategus analysis specification, and a merged CohortMethod execution script.

This shell is provided as `OHDSIAssistant::runStrategusCohortMethodsShell()`.

## Running

Usage examples for `OHDSIAssistant::runStrategusCohortMethodsShell()` live in the R package README: `R/OHDSIAssistant/README.md`.

Workflow diagrams live in `docs/COHORT_METHODS_WORKFLOW.md`.

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
   be 50 characters or fewer because downstream Strategus/Characterization result tables use short
   identifier fields.
4. Optional cohort ID remap step to avoid collisions (`remapCohortIds`).
5. Copy cohort JSON definitions from `indexDir/definitions` into selected cohort folders.
6. Optional negative control and covariate concept-set IDs are captured as placeholders.
7. Configure one analytic-settings profile through `step_by_step`, `free_text`, or cached/function-argument inputs.
   Analytic settings are always collected in this stage and confirmed before finalization.
8. Generate scripts in `scripts/` for cohort generation, keeper review, diagnostics, and
   CohortMethod spec/execution.

## Analytic Settings

The cohort methods shell now resolves a single effective analytic-settings profile. This remains
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
- `outputs/cm_analytic_settings_recommendation.json` is written only for `free_text` mode in the
  current stage. It stores the shell-facing recommendation derived from the ACP response or, if ACP
  is unavailable, from the local fallback.
- `outputs/cm_acp_specifications_recommendation.json` is written for `free_text` mode and stores
  the ACP flow request/response wrapper used to derive the shell-facing recommendation.
- `outputs/study_agent_state.json` echoes `analytic_settings_profile_name` and
  `analytic_settings_customized_sections`, plus analytic-settings mode / confirmation summary.
- `analysis-settings/cmAnalysis.json` stores the template-shaped CohortMethod-oriented contract
  artifact. The generated `06_cm_spec.R` currently still reads `outputs/cm_analysis_defaults.json`
  as its execution settings source.

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
- `cm_analysis_state.json` (written by `scripts/06_cm_spec.R`)
- `study_agent_state.json`

`cm_analysis_defaults.json` stores the effective analytic-settings profile used by the generated
`06_cm_spec.R` when projecting shell settings into Strategus module specifications.

`manual_inputs.json` is the cache/resume-friendly shell artifact for the same run. It includes the
effective `analytic_settings` object plus `customized_sections`.

`06_cm_spec.R` reads the expanded analytic-settings schema and uses it directly when constructing
the CohortMethod module settings:

- `getDbCohortMethodDataArgs`
- `createStudyPopulationArgs`
- `createPsArgs`
- `trimByPsArgs`
- `matchOnPsArgs`
- `stratifyByPsArgs`
- `fitOutcomeModelArgs`

It also writes `analysis-settings/analysisSpecification.json`, a Strategus specification containing:

- a shared cohort-definition resource
- `CharacterizationModule`
- `CohortIncidenceModule`
- `CohortMethodModule`

The generated script uses `CohortGeneratorModule$new()` only to create the shared cohort-definition
resource. The generated Strategus specification intentionally does not add a cohort-generation module
specification or a `CohortDiagnosticsModule` specification because cohort generation and diagnostics
are handled by `03_generate_cohorts.R` and `05_diagnostics.R`.

`scripts/06_cm_spec.R` also writes:

- `outputs/cm_analysis_state.json`
- `analysis-settings/strategus_execute_result.rds`

The same `06_cm_spec.R` script then executes the just-created specification with
`Strategus::execute()`. There is no separate `07_cm_run_analyses.R` in the merged Strategus
CohortMethod flow.

## Generated Scripts

- `scripts/02_apply_improvements.R`
- `scripts/03_generate_cohorts.R`
- `scripts/04_keeper_review.R`
- `scripts/05_diagnostics.R`
- `scripts/06_cm_spec.R`

Generated scripts that connect to the database expect these site-specific files at the root of
`outputDir`:

- `strategus-db-details.json`
- `strategus-execution-settings.json`

The scripts still contain placeholders for values that are not captured in those files yet, such as
`databaseId` for Keeper/export steps.

## Current Boundaries

- `phenotype_improvements` is wired for target, comparator, and outcome cohorts. The shell writes
  role-specific improvement artifacts after prompting whether to run improvements for each role,
  can apply mutating actions (`set`, `replace`, `update`), keeps advisory `note` actions as
  recommendations, and keeps `patched-cohorts/` complete for downstream scripts when any mutating
  improvement is applied.
- Remaining deferred integration points:
  - comparator reuse lookup
  - phenotype index search for suggestion workflows
- Atlas settings deferred in this stage:
  - negative control cohort-definition logic
  - positive control synthesis
  - empirical calibration configuration
  - detailed covariate feature-group selection beyond the current default-plus-include/exclude model
- TODO: implement ACP/MCP support for negative control and covariate concept-set workflows, then
  update the shell to use those tools instead of writing dummy placeholder concept-set artifacts.
- Covariate concept-set include/exclude is not fully implemented yet. Because the generated
  CohortMethod scripts cannot currently materialize exclude covariate concepts, high-correlation
  covariates may remain in the model and cause `06_cm_spec.R` to fail when
  `errorOnHighCorrelation` is enabled.
- Atlas / CohortMethod settings partially supported but still needing broader validation:
  - `minDaysAtRisk`
  - PS trimming (`none`, percent trimming, and equipoise bounds)
  - `inversePtWeighting` passed through to `fitOutcomeModelArgs`
- Evaluation settings from section 12.7.3 remain deferred as well.
- Multiple analytic-settings profiles, multi-comparison support, and broader CohortMethod branching
  remain for a later stage.
- Script TODO comments document where these extensions are expected.

## Notes

- This stage is designed as a bridge: it combines ACP/MCP-assisted intent split, phenotype
  recommendation/improvement, and analytic-settings recommendation with reproducible Strategus
  script generation.

## Analytic Settings Prompt Details

Current `step_by_step` section flow:

- `study_population`
- `time_at_risk`
- `propensity_score_adjustment`
- `outcome_model`

User-facing `step_by_step` prompts follow the ATLAS section grouping:

- ask only the section's core settings directly
- then offer a keep-defaults step for the remaining hidden/default settings
- if the user declines defaults, ask each remaining exposed setting one by one
- show short setting names only in default summaries and final summaries
- show detailed per-setting descriptions only in the one-by-one customization path

Exception for propensity score adjustment:

- first ask the strategy: `match_on_ps`, `stratify_by_ps`, or `none`
- if `match_on_ps`, ask only `maxRatio`
- if `stratify_by_ps`, ask only `numberOfStrata`
- after that, show the remaining PS defaults and ask whether to keep them
- if the user declines defaults, ask the exposed remaining PS settings one by one
- exposed PS trimming settings in that remaining-defaults path: `trimmingStrategy` with `none`, `by_percent`, or `by_equipoise`
- if trimming is customized to `by_percent`, the shell asks for the trimming percent
- if trimming is customized to `by_equipoise`, the shell asks for the lower and upper equipoise bounds
- match defaults currently exposed in that remaining-defaults path: `maxCohortSizeForFitting`, `errorOnHighCorrelation`, `useRegularization`, `caliper`, `caliperScale`
- stratify defaults currently exposed in that remaining-defaults path: `maxCohortSizeForFitting`, `errorOnHighCorrelation`, `useRegularization`, `baseSelection`
- hidden internal defaults such as `create_ps.estimator` still remain persisted but are not directly prompted

Current execution defaults and persisted artifacts use these effective analytic-settings fields:

- `profile_name`
- Study population: `studyStartDate`, `studyEndDate`, `maxCohortSize`, `firstExposureOnly`, `washoutPeriod`, `restrictToCommonPeriod`, `removeDuplicateSubjects`, `censorAtNewRiskWindow`, `removeSubjectsWithPriorOutcome`, `priorOutcomeLookback`
- Covariate settings: current default covariate behavior, include-all state, include concept-set selection, exclude concept-set selection
- Time-at-risk: `minDaysAtRisk`, `riskWindowStart`, `startAnchor`, `riskWindowEnd`, `endAnchor`
- Propensity score adjustment: `strategy`, `trimmingStrategy`, `trimmingPercent`, `equipoiseLowerBound`, `equipoiseUpperBound`, `estimator`, `maxCohortSizeForFitting`, `errorOnHighCorrelation`, `useRegularization`, matching `caliper`, matching `caliperScale`, matching `maxRatio`, stratification `numberOfStrata`, stratification `baseSelection`
- Outcome model: `modelType`, `stratified`, `useCovariates`, `inversePtWeighting`, `useRegularization`

Important current default behavior:

- Matching defaults follow CohortMethod defaults, including `maxRatio = 1`, `caliper = 0.2`, and `caliperScale = "standardized logit"`.
- PS fitting defaults exposed in the shell include `maxCohortSizeForFitting = 250000`, `errorOnHighCorrelation = FALSE`, and `useRegularization = TRUE`.
- PS trimming defaults exposed in the shell include `trimmingStrategy = none`, `trimmingPercent = 5`, and equipoise bounds `c(0.25, 0.75)`.
- Time-at-risk defaults follow CohortMethod defaults, including `riskWindowStart = 0` and `censorAtNewRiskWindow = FALSE`.
- Outcome-model defaults are partially dynamic: `stratified = FALSE` for no PS adjustment or one-to-one matching, `stratified = TRUE` for variable-ratio matching and PS stratification, `useCovariates = FALSE`, `inversePtWeighting = FALSE`, and `useRegularization = TRUE`.
