# slashOhdsiStrategusAssistant

This package is the workflow layer for the slash-ohdsi R refactor.

It owns:

- workflow-stage context construction
- interactive Strategus shell entrypoints
- checkpointing and artifact layout
- generated Strategus assets
- Strategus DB and execution-settings helpers

Primary entrypoints:

- `slashOhdsiStrategusAssistant::runStrategusIncidenceShell()`
- `slashOhdsiStrategusAssistant::runStrategusCohortMethodsShell()`
- `slashOhdsiStrategusAssistant::createStrategusConnectionDetails()`
- `slashOhdsiStrategusAssistant::createStrategusExecutionSettings()`

It depends on `slashOhdsiAcpClient` for ACP calls.
