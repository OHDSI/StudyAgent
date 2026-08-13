# study-agent MCP server

`mcp_server/` contains the MCP-side implementation for reusable study-agent tools, prompt bundles, retrieval components, vocabulary helpers, and Keeper-related logic.

This README is intentionally thin. Tool registration, prompt bundles, and service boundaries are evolving, so the maintained documentation under [`docs/`](../docs/) should be treated as the primary reference surface.

## Prompt Bundles

A standing project convention is that prompts sent to LLMs should be as declarative and editable outside of code as practical.

Most LLM-facing interactions therefore live under [`mcp_server/prompts/`](./prompts/) in per-task subfolders. The common pattern is:

- `overview_*.md`: brief task overview and role framing
- `spec_*.md`: task-specific instructions and constraints
- `output_schema_*.json` or equivalent output contract artifact

Some tools add additional prompt artifacts when needed, such as:

- `system_prompt_*.md`
- domain configuration files such as `.yaml`
- templates such as `template_*.md`
- workflow-specific JSON templates such as `cmAnalysis_template.json`

Current prompt families include:

- [`prompts/phenotype/`](./prompts/phenotype/)
- [`prompts/keeper/`](./prompts/keeper/)
- [`prompts/keeper_concept_sets/`](./prompts/keeper_concept_sets/)
- [`prompts/lint/`](./prompts/lint/)
- [`prompts/workflow_dialogue/`](./prompts/workflow_dialogue/)
- [`prompts/case_causal_review/`](./prompts/case_causal_review/)
- [`prompts/cohort_methods/`](./prompts/cohort_methods/)

## Where To Look

For service and workflow orientation, start with:

- [`docs/SERVICE_REGISTRY.yaml`](../docs/SERVICE_REGISTRY.yaml)
- [`docs/WORKFLOW_PHENOTYPE_RECOMMENDATION.md`](../docs/WORKFLOW_PHENOTYPE_RECOMMENDATION.md)
- [`docs/WORKFLOW_CONTEXT_DIALOGUE_SLASH_OHDSI.md`](../docs/WORKFLOW_CONTEXT_DIALOGUE_SLASH_OHDSI.md)
- [`docs/WORKFLOW_COHORT_METHODS.md`](../docs/WORKFLOW_COHORT_METHODS.md)
- [`docs/WORKFLOW_INCIDENCE.md`](../docs/WORKFLOW_INCIDENCE.md)
- [`docs/SPEC_KEEPER_INTERFACE.md`](../docs/SPEC_KEEPER_INTERFACE.md)
- [`docs/PHENOTYPE_VALIDATION_REVIEW.md`](../docs/PHENOTYPE_VALIDATION_REVIEW.md)
- [`docs/MCP_TOOL_AUTHORING.md`](../docs/MCP_TOOL_AUTHORING.md)

Use `SERVICE_REGISTRY.yaml` as an important metadata surface, but not as the only source of truth for current runtime behavior.

## ACP Connection Modes

MCP is the tool-serving side of the system. ACP is the orchestration side, and ACP can attach to MCP in two supported ways:

- HTTP mode: ACP connects to a separately running MCP server via `STUDY_AGENT_MCP_URL`
- Managed stdio mode: ACP launches MCP as a subprocess via `STUDY_AGENT_MCP_COMMAND` and optional `STUDY_AGENT_MCP_ARGS`

In ACP code, `StudyAgent` depends on an `MCPClient` protocol rather than a specific transport implementation. ACP startup then injects either `HttpMCPClient` or `StdioMCPClient`.

HTTP is the recommended local runtime because it is easier to inspect and debug, but stdio remains a supported integration mode.

## Running MCP over HTTP

Recommended local MCP runtime:

```bash
export MCP_TRANSPORT=http
export MCP_HOST=127.0.0.1
export MCP_PORT=8790
export MCP_PATH=/mcp
study-agent-mcp --config config.yaml --profile native
```

ACP connects via:

```bash
export STUDY_AGENT_MCP_URL="http://127.0.0.1:8790/mcp"
```

For a uv-managed native installation, invoke MCP as `uv run study-agent-mcp --config .\config.yaml --profile native`. On managed Windows hosts, do not rely on bare project executables resolving to the intended Python environment. Docker Compose starts MCP with the `docker` profile; see [`README.md`](../README.md) and [`docs/ENVIRONMENT.md`](../docs/ENVIRONMENT.md) for deployment details.
