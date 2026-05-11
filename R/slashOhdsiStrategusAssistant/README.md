# slashOhdsiStrategusAssistant

This package is the workflow layer for the slash-ohdsi R refactor.

It owns:

- workflow-stage context construction
- Strategus shell orchestration
- checkpointing and artifact layout
- generated Strategus assets

It depends on `slashOhdsiAcpClient` for ACP calls.
