
## What Was Implemented

We added the current CohortMethod shell path around
`OHDSIAssistant::runStrategusCohortMethodsShell()`. In broad terms, the work now
supports:

- CohortMethod-specific intent splitting from one study-intent sentence into
  target, comparator, and one or more outcome statements.
  - We kept the existing `phenotype_intent_split` flow unchanged and added a
    separate `cohort_methods_intent_split` flow. Please decide whether these
    should remain separate or be consolidated later.
- Phenotype recommendation and optional improvement for target, comparator, and
  outcome cohorts.
- Negative-control and covariate concept-set selection remain future work. This
  step currently implements only the scaffold; it should be completed once ACP
  flows for suggesting negative controls and covariate concept sets are
  available.
- CohortMethod analytic-settings collection through either `step_by_step` prompts
  or `free_text` ACP recommendation.
- Generation of reproducible output artifacts, CohortMethod analytic-settings
  JSON, and Strategus R scripts including `scripts/06_cm_spec.R`

### Main ACP/MCP/core additions:

- ACP flow endpoint: 
	- `/flows/cohort_methods_intent_split`
	- ACP flow endpoint: `/flows/cohort_methods_specifications_recommendation`
- MCP tool:
	- `cohort_methods_intent_split`
	- MCP tool: `cohort_methods_prompt_bundle`
- R helper: `OHDSIAssistant::suggestCohortMethodSpecs()`
- R shell integration:  `runStrategusCohortMethodsShell()`
- Prompt/template assets:
  - CohortMethod intent-split overview/spec/schema assets.
  - CohortMethod cmAnalysis template and instruction assets under
    `mcp_server/prompts/cohort_methods/`.

## Read These For Details

- Shell workflow, output layout, generated scripts, current boundaries, and
  analytic-settings prompt details:
  - `docs/STRATEGUS_COHORT_METHODS_SHELL.md`
- End-to-end workflow diagrams:
  - `docs/COHORT_METHODS_WORKFLOW.md`
- Free-text analytic-settings recommendation flow, endpoint shape, response
  shape, and projection from cmAnalysis-style specs:
  - `docs/COHORT_METHODS_SPECIFICATIONS_RECOMMENDATION_DESIGN.md`
- CohortMethod ACP/MCP service registry entries:
  - `docs/SERVICE_REGISTRY.yaml`
- CohortMethod cmAnalysis prompt/template assets:
  - `mcp_server/prompts/cohort_methods/cmAnalysis_template.json`
  - `mcp_server/prompts/cohort_methods/CM_ANALYSIS_TEMPLATE.md`
  - `mcp_server/prompts/cohort_methods/instruction_cohort_methods_specs.md`
  - `mcp_server/prompts/cohort_methods/output_style_cohort_methods_specs.md`
- CohortMethod intent-split prompt/schema assets:
  - `mcp_server/prompts/phenotype/overview_cohort_methods_intent_split.md`
  - `mcp_server/prompts/phenotype/spec_cohort_methods_intent_split.md`
  - `mcp_server/prompts/phenotype/output_schema_cohort_methods_intent_split.json`
- R usage examples:
  - `R/OHDSIAssistant/README.md`
- Test and smoke-test commands:
  - `docs/TESTING.md`

## Remaining TODO


Future CohortMethod coverage:

- Replace dummy negative-control and covariate concept-set artifacts with real
  ACP/MCP-backed workflows.
	- The current  placeholder path cannot exclude high-correlation covariates, which can cause script `06_cm_spec.R` to fail when `errorOnHighCorrelation` is enabled.
- Properly implement `scripts/04_keeper_review.R` for CohortMethod outputs.
- Support multiple CohortMethod analyses
- Add validation for cohort-method analytic-settings recommendations before
  they are accepted into the shell/generated scripts.
