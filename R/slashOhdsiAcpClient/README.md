# slashOhdsiAcpClient

This package is the low-level ACP client for the slash-ohdsi R refactor.

It owns:

- ACP client construction
- HTTP transport and timeout handling
- flow and action wrappers

It does not own Strategus shells, checkpointing, or workflow-stage decisions.

## ACP Compatibility

The client requires ACP API version 1. acp_client(check = TRUE) checks /health and validates the
server api_version before returning a client. The ACP server also reports service_version, which
makes a site mismatch actionable without coupling this R package to the StudyAgent source checkout.
