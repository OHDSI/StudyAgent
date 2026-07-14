# slashOhdsiStrategusAssistant

This package is the workflow layer for the slash-ohdsi R refactor.

It owns:

- workflow-stage context construction
- interactive Strategus shell entrypoints
- checkpointing and artifact layout
- generated Strategus assets
- ACP-based Keeper workflow orchestration for generated scripts
- Strategus DB and execution-settings helpers

Primary entrypoints:

- `slashOhdsiStrategusAssistant::runStrategusIncidenceShell()`
- `slashOhdsiStrategusAssistant::runStrategusCohortMethodsShell()`
- `slashOhdsiStrategusAssistant::runKeeperConceptSetWorkflow()`
- `slashOhdsiStrategusAssistant::runKeeperCaseReviewWorkflow()`
- `slashOhdsiStrategusAssistant::createStrategusConnectionDetails()`
- `slashOhdsiStrategusAssistant::createStrategusExecutionSettings()`

Current demo entry scripts in the repo:

- `scripts/test_strategus_incidence_plus_keeper.R`
- `scripts/demo_strategus_cohort_method.R`

Current shell details:

- the incidence shell persists explicit TAR and strata settings to `analysis-settings/time_at_risk_settings.json`
- both Strategus shells support `/back` at major stage boundaries while preserving `/ohdsi` dialogue prompts inside the workflow
- both Strategus shells support build-mode `h` / `help` prompts for step-appropriate command guidance during interactive design
- both Strategus shells can derive a default `study_intent` from directly entered cohort role statements when the initial study-intent prompt is left blank, and then persist the user-confirmed wording for downstream context
- both Strategus shells can run or generate ACP-based Keeper concept-set and case-review workflows with `keeper_concept_set_state.json` and `keeper_case_review_state.json` artifacts plus bounded inline Keeper gates for domain generation and case review
- the incidence shell can now import an existing OHDSI cohort definition from a configured database schema when the phenotype index does not contain a usable candidate
- both Strategus shell entrypoints now accept `showBanner = FALSE` to suppress the startup ASCII art for narrow UIs
- generated Keeper scripts expose `ACP_TIMEOUT`, concept-set reuse/overwrite controls, and explicit row selection controls
- both Strategus shells now also persist `study-agent-project.json` and `outputs/study_agent_runtime_state.json` so generated workflow steps can be run and resumed inside the same shell
- both Strategus shells expose an execution menu for run/resume mode with step status, `run <step>`, `inspect[_v] <step>`, artifact inventory, approved exploration commands via `x` / `explore[_v]`, `/ohdsi` guidance, and an `executionTableDisplay` startup option for viewer-first table rendering
- the incidence execution menu now includes dedicated incidence-result summaries for `CohortIncidenceModule` outputs, including `incidence_summary_preview` and `incidence_analysis_settings_summary`
- both Strategus shells now generate `scripts/08_launch_diagnostics_explorer.R` as an optional second-session launcher that creates the merged diagnostics SQLite if needed and then opens `CohortDiagnostics::launchDiagnosticsExplorer()`
- execution mode now supports `rev` / `revise ...` commands so users can leave run mode and return to build mode, optionally switch to a temporary revision cache mode, and intentionally reopen a target/comparator/outcome decision point when a phenotype or study configuration needs to be changed
- build-only steps such as initial recommend/select are tracked in the workflow status but are not treated as runnable generated scripts during execution mode

It depends on `slashOhdsiAcpClient` for ACP calls.
