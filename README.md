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

## Phenotype Recommendation Flow (ACP + MCP + LLM)

1. ACP calls MCP `phenotype_search` to retrieve candidates.
2. ACP calls MCP `phenotype_prompt_bundle` to fetch prompt assets and output schema.
3. ACP calls an OpenAI-compatible LLM API to rank candidates.
4. Core validates and filters LLM output.

See `docs/PHENOTYPE_RECOMMENDATION_DESIGN.md` for details.

## Getting started

See `docs/TESTING.md` for install and CLI smoke tests.

## Roadmap (near term)

- ACP: session lifecycle, confirmations, and audit trail integration.
- MCP: expand tool surface area and schemas; add portable validation utilities.
- Core: enrich deterministic checks and improve coverage with synthetic fixtures.
