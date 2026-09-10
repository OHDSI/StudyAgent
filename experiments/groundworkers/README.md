# Groundworkers pilot environment

This directory defines a reproducible, isolated test environment for evaluating
Groundworkers as an optional concept-grounding provider for
`phenotype_make_computable`.

It deliberately does not alter StudyAgent's runtime dependencies, `config.yaml`,
or secret-handling policy. The pilot service must use a dedicated environment
and read-only access to the OMOP vocabulary.

## Published compatible release line

The initially supplied v0.4.0 package set cannot load the public configuration
API required at runtime: Groundworkers v0.4.0 references an unreleased
`oa-configurator` branch. `requirements-pinned.txt` and
`archive-provenance.sha256` remain as evidence of that supplied stack.

The runnable public-release substitute is recorded in
`requirements-published-compatible.txt`, its tag commits in
`tag-provenance-v0.5.txt`, and the locally built wheel hashes in
`wheels-v0.5.sha256`. It adds `groundskeeping` because Groundworkers v0.5.0
imports its runtime plugin contract even when the service is run headlessly.

## Checkpoints

1. Record package artifacts and SHA-256 hashes, then install the published
   compatible release line in the separate service environment.
2. Perform read-only database and MCP health checks.
3. Run the lexical-only comparison. Do not configure embeddings, pgvector, or
   graph traversal before this checkpoint demonstrates material value.
4. If approved, build a reviewed targeted embedding corpus that validates
   against `embedding-corpus-manifest.schema.json`; never embed the full OMOP
   vocabulary by default.

Groundworkers returns ranked candidates and provenance only. StudyAgent retains
scope confirmation, explicit concept-policy approval, Capr emission, and
Capr/Circe validation.

## Pre-ACP readiness smoke

After the one-time relationship-classification bootstrap, run the opt-in smoke
before configuring a long-running ACP process. It starts no ACP process, uses
`--config-read-only`, and verifies the same streamable-HTTP MCP client contract
that ACP will use. The fixed test query is non-PHI and forces lexical-only
retrieval (`include_embedding = false`).

```sh
GROUNDWORKERS_CONFIG_PATH=/absolute/path/to/groundworkers-test.toml \
GROUNDWORKERS_COMMAND=/absolute/path/to/.groundworkers-venv/bin/groundworkers \
STUDY_AGENT_GROUNDWORKERS_MCP_URL=http://127.0.0.1:8010/mcp \
uv run doit smoke_groundworkers_readiness
```

The task refuses to share a port with an unknown listener. To validate a
Groundworkers process you intentionally started yourself, retain the MCP URL and
run with `GROUNDWORKERS_MCP_MANAGED=0`; in that mode the smoke does not require
its config path or command and never stops the service.

A passing result verifies: the `concept_ground` and `system_status` MCP tools,
the configured OMOP graph database connection, and one bounded standard active
Condition lookup for `type 2 diabetes mellitus`. It does not claim full-text or
embedding availability, clinical validation, or ACP flow integration.
