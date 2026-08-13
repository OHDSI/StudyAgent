# study-agent ACP agent

`acp_agent/` contains the ACP-side orchestration layer for user-facing study-agent flows. ACP exposes the runtime HTTP surface, coordinates LLM-backed flow execution, and connects to MCP tools over HTTP or managed stdio.

This README is intentionally thin. The environment surface spans ACP, MCP, retrieval, Keeper tooling, and R workflows, so the maintained documentation under [`docs/`](../docs/) should be treated as the primary reference surface rather than this directory README.

## What ACP Does

ACP is the orchestration and control-plane layer for implemented flows such as:

- phenotype recommendation and related advice / intent-splitting flows
- workflow context dialogue
- Keeper-backed review and concept-generation flows
- cohort-method and incidence workflow support surfaces

The current runtime surface is defined by the actual server implementation and the maintained service metadata:

- [`acp_agent/study_agent_acp/server.py`](./study_agent_acp/server.py)
- [`docs/SERVICE_REGISTRY.yaml`](../docs/SERVICE_REGISTRY.yaml)

Use `SERVICE_REGISTRY.yaml` as an important metadata surface, but not as the only source of truth for runtime behavior.

## ACP To MCP Client Model

ACP does not construct MCP tool calls inside `StudyAgent` directly. Instead, ACP startup builds a concrete MCP client and injects it into `StudyAgent`.

The key distinction is:

- `MCPClient` in `study_agent_acp/agent.py` is a typing `Protocol`, not a concrete implementation
- ACP startup instantiates either an HTTP client or a managed stdio client
- `StudyAgent` receives that client through `StudyAgent(mcp_client=...)`

Current startup modes are:

- HTTP MCP: set `STUDY_AGENT_MCP_URL`; ACP builds `HttpMCPClient` and sends MCP requests over HTTP
- Managed stdio MCP: set `STUDY_AGENT_MCP_COMMAND` and optional `STUDY_AGENT_MCP_ARGS`; ACP builds `StdioMCPClient` and manages an MCP subprocess
- No MCP client: ACP can still run limited core or fallback paths when supported

This is a dependency-injection boundary between ACP orchestration and MCP tool serving. The bootstrap logic lives in [`acp_agent/study_agent_acp/server.py`](./study_agent_acp/server.py), while the interface expected by `StudyAgent` lives in [`acp_agent/study_agent_acp/agent.py`](./study_agent_acp/agent.py).

## Environment And Runtime Setup

For the comprehensive environment-variable reference, start with:

- [`docs/ENVIRONMENT.md`](../docs/ENVIRONMENT.md)
- [`docs/TESTING.md`](../docs/TESTING.md)
- [`docs/PHENOTYPE_INDEXING.md`](../docs/PHENOTYPE_INDEXING.md)

Recommended local MCP + ACP startup:

```bash
export MCP_TRANSPORT=http
export MCP_HOST=127.0.0.1
export MCP_PORT=8790
export MCP_PATH=/mcp
study-agent-mcp --config config.yaml --profile native
```

```bash
export STUDY_AGENT_MCP_URL="http://127.0.0.1:8790/mcp"
export STUDY_AGENT_HOST=127.0.0.1
export STUDY_AGENT_PORT=8765
study-agent-acp --config config.yaml --profile native
```

For a uv-managed native installation, prefix both commands with `uv run`. On managed Windows hosts, do not invoke bare project executables because PowerShell can select a globally installed Python environment. Docker Compose supplies the `docker` profile itself; see [`README.md`](../README.md) and [`docs/ENVIRONMENT.md`](../docs/ENVIRONMENT.md) for deployment steps.

## Where To Look

For workflow and service orientation, start with:

- [`docs/ENVIRONMENT.md`](../docs/ENVIRONMENT.md)
- [`docs/SERVICE_REGISTRY.yaml`](../docs/SERVICE_REGISTRY.yaml)
- [`docs/WORKFLOW_PHENOTYPE_RECOMMENDATION.md`](../docs/WORKFLOW_PHENOTYPE_RECOMMENDATION.md)
- [`docs/WORKFLOW_CONTEXT_DIALOGUE_SLASH_OHDSI.md`](../docs/WORKFLOW_CONTEXT_DIALOGUE_SLASH_OHDSI.md)
- [`docs/WORKFLOW_COHORT_METHODS.md`](../docs/WORKFLOW_COHORT_METHODS.md)
- [`docs/WORKFLOW_INCIDENCE.md`](../docs/WORKFLOW_INCIDENCE.md)
- [`docs/PHENOTYPE_VALIDATION_REVIEW.md`](../docs/PHENOTYPE_VALIDATION_REVIEW.md)
