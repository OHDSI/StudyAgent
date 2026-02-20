# Study Design Assistant - ACP + MCP Prototype

This repo refactors the initial proof of concept into a clean separation between an ACP server (agent UX + policy) and MCP servers (tools). It demonstrates how an interactive client can rely on ACP for orchestration while keeping tool logic portable and reusable via MCP.

## What this prototype demonstrates

- ACP server owns interaction policy: confirmations, safe summaries, and tool invocation routing.
- MCP server owns tool contracts: JSON schemas + deterministic tool outputs.
- Core logic stays pure and reusable across both ACP and MCP layers.

## Architecture (current scaffold)

- **ACP agent** (`acp_agent/`): interaction policy + routing; calls MCP tools or falls back to core.
- **MCP server** (`mcp_server/`): exposes tool APIs (core tools plus phenotype retrieval and prompt bundles).
- **Core** (`core/`): pure, deterministic business logic (no IO, no network).

## Why this separation matters

ACP provides consistent UX and control across environments (R, Atlas/WebAPI, notebooks), while MCP provides a shared tool bus that can be reused across agents and institutions. ACP orchestrates tool calls and LLM calls; MCP owns retrieval, prompt assets, and deterministic tool outputs. This prototype shows how the same core tools can be accessed via MCP or directly by ACP without coupling to datasets or local files.

## Current unit tests 

See `docs/TESTING.md` for install and CLI smoke tests.

## Phenotype Recommendation Flow (ACP + MCP + LLM)

1. ACP calls MCP `phenotype_search` to retrieve candidates.
2. ACP calls MCP `phenotype_prompt_bundle` to fetch prompt assets and output schema.
3. ACP calls an OpenAI-compatible LLM API to rank candidates.
4. Core validates and filters LLM output.

For details on the design, see `docs/PHENOTYPE_RECOMMENDATION_DESIGN.md`.

### Example run for `phenotype_recommendations`

*Prerequisite:* you have embedded phenotype definitions - see `./docs/PHENOTYPE_INDEXING.md`

1. Start the ACP server (runs on http://127.0.0.1:8765/ by default):
```bash
export LLM_API_KEY=<YOUR KEY>
export LLM_API_URL="<URL BASE>/api/chat/completions"
export LLM_LOG=1
export LLM_MODEL=<a model that supports completions> 
export EMBED_API_KEY=<YOUR KEY>
export EMBED_MODEL=<a text embedding model>
export EMBED_URL="<URL BASE>/ollama/api/embed"
export STUDY_AGENT_MCP_COMMAND=study-agent-mcp
export STUDY_AGENT_MCP_ARGS=""
study-agent-acp
```

2. Run `phenotype_recommendation`
```bash
curl -s -X POST http://127.0.0.1:8765/flows/phenotype_recommendation \
  -H 'Content-Type: application/json' \
  -d '{"study_intent":"Identify clinical risk factors for older adult patients who experience an adverse event of acute gastro-intenstinal (GI) bleeding", "top_k":20, "max_results":10,"candidate_limit":10}'
```

## Roadmap

### near term

- `phenotype_improvements`
- `phenotype_validation_review`

Show these tools in use to design, run, and interpret the results of an OHDSI incidence rate analysis using the [CohortIncidenceModule](https://raw.githubusercontent.com/OHDSI/Strategus/main/inst/doc/CreatingAnalysisSpecification.pdf) of  [OHDSI Strategus](https://github.com/OHDSI/Strategus) 
