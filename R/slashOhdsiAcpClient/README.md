# slashOhdsiAcpClient

This package is the low-level ACP client for the slash-ohdsi R refactor.

It owns:

- ACP client construction
- HTTP transport and timeout handling
- flow and action wrappers

It does not own Strategus shells, checkpointing, or workflow-stage decisions.
