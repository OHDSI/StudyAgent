# OHDSIAssistant

This package is now a compatibility layer during the R refactor.

Canonical packages:

- `slashOhdsiAcpClient` for ACP connectivity and phenotype-oriented helper APIs
- `slashOhdsiStrategusAssistant` for Strategus workflows, shell entrypoints, and Strategus helper utilities

Compatibility exports still available here forward to those packages, including:

- `acp_connect()`
- `suggestPhenotypes()`
- `reviewPhenotypes()`
- `runStrategusIncidenceShell()`
- `runStrategusCohortMethodsShell()`
- `suggestCohortMethodSpecs()`

Preferred entrypoints going forward:

- `slashOhdsiAcpClient::acp_connect()`
- `slashOhdsiAcpClient::suggestPhenotypes()`
- `slashOhdsiAcpClient::reviewPhenotypes()`
- `slashOhdsiStrategusAssistant::runStrategusIncidenceShell()`
- `slashOhdsiStrategusAssistant::runStrategusCohortMethodsShell()`
- `slashOhdsiStrategusAssistant::suggestCohortMethodSpecs()`
