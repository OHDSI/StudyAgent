# Study Design Assistant - ACP + MCP Prototype

This repo refactors the initial proof of concept into a clean separation between an ACP server (agent UX + policy) and MCP servers (tools). It demonstrates how an interactive client can rely on ACP for orchestration while keeping tool logic portable and reusable via MCP.

## What this prototype demonstrates

- ACP server owns interaction policy: confirmations, safe summaries, and tool invocation routing.
- MCP server owns tool contracts: JSON schemas + deterministic tool outputs.
- Core logic stays pure and reusable across both ACP and MCP layers.

## Architecture (current scaffold)

- **ACP agent** (`acp_agent/`): interaction policy + routing; calls MCP tools or falls back to core.
- **MCP server** (`mcp_server/`): exposes tool APIs (`cohort_lint`, `propose_concept_set_diff`, `phenotype_recommendations`, `phenotype_improvements`).
- **Core** (`core/`): pure, deterministic business logic (no IO, no network).

## Why this separation matters

ACP provides consistent UX and control across environments (R, Atlas/WebAPI, notebooks), while MCP provides a shared tool bus that can be reused across agents and institutions. This prototype shows how the same core tools can be accessed via MCP or directly by ACP without coupling to datasets or local files.

## Getting started

See `docs/TESTING.md` for install and CLI smoke tests.

## Roadmap (near term)

- ACP: session lifecycle, confirmations, and audit trail integration.
- MCP: expand tool surface area and schemas; add portable validation utilities.
- Core: enrich deterministic checks and improve coverage with synthetic fixtures.
