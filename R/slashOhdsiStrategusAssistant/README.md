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

Current shell details:

- the incidence shell persists explicit TAR and strata settings to `analysis-settings/time_at_risk_settings.json`
- both Strategus shells support `/back` at major stage boundaries while preserving `/ohdsi` dialogue prompts inside the workflow
- both Strategus shells can run or generate ACP-based Keeper concept-set and case-review workflows with `keeper_concept_set_state.json` and `keeper_case_review_state.json` artifacts plus bounded inline Keeper gates for domain generation and case review
- generated Keeper scripts expose `ACP_TIMEOUT`, concept-set reuse/overwrite controls, and explicit row selection controls

It depends on `slashOhdsiAcpClient` for ACP calls.
