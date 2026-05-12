# R Package Architecture

## Purpose

This document describes the implemented R-side architecture for the OHDSI Study Agent.
The former combined R package has been retired. The current split is:

- `slashOhdsiAcpClient`: ACP connectivity plus thin flow/action wrappers
- `slashOhdsiStrategusAssistant`: Strategus workflows, shell orchestration, dialogue context, and generated script assets

This is now current-state documentation rather than a migration plan.

## Implemented Package Split

### `slashOhdsiAcpClient`

Primary responsibility:

- manage ACP connection configuration
- perform HTTP calls to ACP flows/actions
- expose thin exported wrappers around ACP capabilities
- normalize request payloads and basic response handling

Key files:

- [`R/slashOhdsiAcpClient/R/client.R`](../R/slashOhdsiAcpClient/R/client.R)
- [`R/slashOhdsiAcpClient/R/flows.R`](../R/slashOhdsiAcpClient/R/flows.R)
- [`R/slashOhdsiAcpClient/R/compatibility_api.R`](../R/slashOhdsiAcpClient/R/compatibility_api.R)
- [`R/slashOhdsiAcpClient/R/lint_and_concept_sets.R`](../R/slashOhdsiAcpClient/R/lint_and_concept_sets.R)
- [`R/slashOhdsiAcpClient/R/actions_and_lint.R`](../R/slashOhdsiAcpClient/R/actions_and_lint.R)

Current role boundaries:

- no Strategus shell state
- no local artifact layout decisions
- no generated-script ownership
- no workflow progression logic beyond wrapper arguments

Representative exported seam:

- `acp_connect()`
- `acp_get_default_client()`
- `acp_is_connected()`
- `acp_call_flow()`
- `acp_workflow_context_dialogue()`
- `acp_suggest_cohort_method_specs()`
- `acp_keeper_concept_sets_generate()`
- `acp_keeper_profiles_generate()`
- `acp_phenotype_validation_review()`

### `slashOhdsiStrategusAssistant`

Primary responsibility:

- own user-facing Strategus shells
- collect inputs and manage checkpoints
- maintain local artifact layout under workflow output directories
- construct workflow-stage dialogue context for `/ohdsi`
- interpret ACP responses in workflow context
- generate Strategus-ready scripts and analysis assets
- provide a shared ACP-based Keeper review helper for generated scripts and inline shell execution

Key files:

- [`R/slashOhdsiStrategusAssistant/R/strategus_incidence_shell.R`](../R/slashOhdsiStrategusAssistant/R/strategus_incidence_shell.R)
- [`R/slashOhdsiStrategusAssistant/R/strategus_cohort_methods_shell.R`](../R/slashOhdsiStrategusAssistant/R/strategus_cohort_methods_shell.R)
- [`R/slashOhdsiStrategusAssistant/R/keeper_review_workflow.R`](../R/slashOhdsiStrategusAssistant/R/keeper_review_workflow.R)
- [`R/slashOhdsiStrategusAssistant/R/workflow_dialogue.R`](../R/slashOhdsiStrategusAssistant/R/workflow_dialogue.R)
- [`R/slashOhdsiStrategusAssistant/R/workflow_stage_context.R`](../R/slashOhdsiStrategusAssistant/R/workflow_stage_context.R)
- [`R/slashOhdsiStrategusAssistant/R/workflow_dialogue_mapping.R`](../R/slashOhdsiStrategusAssistant/R/workflow_dialogue_mapping.R)
- [`R/slashOhdsiStrategusAssistant/R/cohort_methods_specs.R`](../R/slashOhdsiStrategusAssistant/R/cohort_methods_specs.R)
- [`R/slashOhdsiStrategusAssistant/R/db_details.R`](../R/slashOhdsiStrategusAssistant/R/db_details.R)
- [`R/slashOhdsiStrategusAssistant/R/execution_settings.R`](../R/slashOhdsiStrategusAssistant/R/execution_settings.R)
- [`R/slashOhdsiStrategusAssistant/R/slash_ohdsi_runtime.R`](../R/slashOhdsiStrategusAssistant/R/slash_ohdsi_runtime.R)

Representative public seam:

- `runStrategusIncidenceShell()`
- `runStrategusCohortMethodsShell()`
- `runKeeperReviewWorkflow()`
- `new_workflow_dialogue_session()`
- `build_incidence_workflow_stage_context()`
- `build_cohort_methods_workflow_stage_context()`
- `render_workflow_dialogue_response()`
- `createStrategusConnectionDetails()`
- `createStrategusExecutionSettings()`

## Runtime Boundary Between Packages

The workflow package does not construct raw ACP HTTP requests directly in shell code.
Instead it calls public wrappers from `slashOhdsiAcpClient`, either directly or through the
small runtime bridge in [`slash_ohdsi_runtime.R`](../R/slashOhdsiStrategusAssistant/R/slash_ohdsi_runtime.R).

That bridge currently serves two purposes:

- keep shell code dependent on a small local seam instead of scattered package calls
- provide a stable place to expand ACP-backed runtime helpers such as Keeper flows and workflow dialogue

## Implemented Workflow Dialogue Contract

The shells now share a workflow-stage context contract for `/ohdsi` dialogue.
The structure is built in the workflow package and passed through the ACP client wrapper.

Current top-level context shape includes:

- `workflow_type`
- `current_step`
- `step_label`
- `user_goal`
- `entities`
- `available_artifacts`
- `dialogue`
- `constraints`
- `legacy_context`

The exact population varies by workflow and step, but the important implemented behavior is:

- incidence and cohort-method shells both emit normalized stage context
- `/ohdsi` dialogue uses that context instead of ad hoc free-form shell strings
- the workflow package owns stage labels and context shaping
- the ACP client wrapper flattens and forwards the resulting payload

Relevant files:

- [`R/slashOhdsiStrategusAssistant/R/workflow_stage_context.R`](../R/slashOhdsiStrategusAssistant/R/workflow_stage_context.R)
- [`R/slashOhdsiStrategusAssistant/R/workflow_dialogue_mapping.R`](../R/slashOhdsiStrategusAssistant/R/workflow_dialogue_mapping.R)
- [`R/slashOhdsiStrategusAssistant/R/workflow_dialogue.R`](../R/slashOhdsiStrategusAssistant/R/workflow_dialogue.R)
- [`R/slashOhdsiAcpClient/R/flows.R`](../R/slashOhdsiAcpClient/R/flows.R)

## Implemented Stage Vocabulary

Shared stages in current use include:

- `study_intent_capture`
- `intent_split`
- `target_selection`
- `outcome_selection`
- `phenotype_review`
- `keeper_concept_set_generation`
- `keeper_case_review`
- `workflow_summary`

Cohort-method-specific stages include:

- `comparator_selection`
- `analytic_settings_collection`
- `cohort_method_spec_recommendation`
- `cohort_method_spec_confirmation`

Incidence-specific stages include:

- `incidence_design_setup`
- `time_at_risk_configuration`

These identifiers are machine-facing workflow markers owned by the Strategus workflow package.

## Generated Artifact Ownership

The current package ownership of generated workflow artifacts is:

- `slashOhdsiStrategusAssistant` owns output directory layout, checkpoints, JSON artifacts, and generated R scripts
- `slashOhdsiAcpClient` owns only the ACP request/response seam and does not own filesystem artifacts

Important generated-script facts in the current architecture:

- both Strategus shells generate ACP-based `04_keeper_review.R`
- the generated Keeper script calls `runKeeperReviewWorkflow()` and no longer uses the legacy Keeper R package
- the incidence shell persists TAR and strata settings to `analysis-settings/time_at_risk_settings.json`
- the cohort-method shell persists analytic-settings artifacts and comparison artifacts used by `06_cm_spec.R`

## Current Architecture Benefits

The implemented split now gives the project:

- a smaller ACP client seam that can be reused outside the Strategus shells
- clearer separation between transport/wrapper code and workflow orchestration
- easier static testing of generated-script contracts and workflow dialogue mapping
- a consistent place to add new ACP-backed helpers without reintroducing the original combined-package coupling

## Remaining Gaps

This architecture is implemented, but several workflow capabilities remain incomplete:

- cohort-method negative-control and covariate concept-set workflows are still placeholder-based
- ACP analytic-settings recommendations are mapped into shell settings without a dedicated validation layer yet
- cohort-method generation still materializes only the first comparison from `cm_comparisons.json`
- ACP-based Keeper concept-set approve/edit/rerun UX is still incomplete even though the runtime seam is in place

Those are workflow/product gaps, not package-split gaps.
