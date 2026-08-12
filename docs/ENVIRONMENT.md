# Environment Reference

This file is the central reference for environment variables used by the implemented ACP, MCP, retrieval, Keeper, and R-shell workflows in this repo.

Not every deployment needs every variable. Most local setups only need:

- ACP runtime and MCP connection settings
- LLM settings for LLM-backed flows
- phenotype retrieval settings if you use phenotype search
- Keeper / vocabulary / PHOEBE / OMOP settings if you use Keeper flows

## Deployment Configuration

`config.yaml` is the primary home for all non-secret Python service configuration. It is versioned, validated, supports profiles, and resolves relative filesystem paths from its own directory, which avoids shell- and platform-specific path expansion. Copy [`config.example.yaml`](../config.example.yaml) to `config.yaml`, or use `study-agent-setup` to create it interactively.

Secrets must remain outside YAML. Use process environment variables for native services and `secrets.env` for Docker Compose. The supported secret variables include `LLM_API_KEY`, `EMBED_API_KEY`, `OMOP_DB_ENGINE` (or legacy `ENGINE`), `STUDY_AGENT_MCP_TOKEN`, and PV Copilot token variables. The loader rejects any YAML key that looks like a token, API key, password, connection string, or database URL.

Start native services with an explicit file (preferred) or set the bootstrap-only `STUDY_AGENT_CONFIG` path:

```bash
study-agent-mcp --config config.yaml
study-agent-acp --config config.yaml
```

The configuration precedence is: explicit CLI options, `config.yaml`, secret environment variables, legacy non-secret environment variables, then built-in defaults. When YAML is loaded, its non-secret values override stale legacy shell settings. Environment-only deployments continue to work during the compatibility period.

`config.yaml` and `secrets.env` are ignored by Git. `config.yaml` contains no secrets and must be readable by the container service user; the wizard writes it with ordinary read permissions. `secrets.env` remains private. Use `study-agent-setup --migrate-env .env` to split an existing environment file without displaying its values. Docker Compose mounts `config.yaml` read-only and loads `secrets.env`; its `docker` profile sets container bind addresses and ACP's internal MCP URL. This Python-service configuration does not configure the separately deployed R packages; their remote-client configuration remains independent.

### Docker host services

Within a container, `localhost` is the container itself. For an LLM or embedding service running on the Docker host, configure `http://host.docker.internal:<port>/...`. Compose maps that name to Docker's `host-gateway` on Linux, macOS, and Windows. You can verify the mapping after startup with `docker compose exec acp-agent getent hosts host.docker.internal`; to inspect the current bridge gateway directly, use `docker compose exec acp-agent sh -c "ip route show default"`. Do not copy a bridge IP such as `172.17.0.1` into `config.yaml`, because it can change between hosts and networks.

Use full filesystem paths where practical, especially for index paths, generated-output roots, and Windows deployments. `paths.runtime` is the configuration-relative directory used by `doit` tasks and timeout calibration for logs and generated recommendations; it defaults to `.study-agent-runtime` instead of a Linux-only `/tmp` location.

## ACP Runtime

| Variable | Used by | Notes |
|---|---|---|
| `STUDY_AGENT_HOST` | ACP server | ACP bind host. Default `127.0.0.1`. |
| `STUDY_AGENT_PORT` | ACP server | ACP bind port. Default `8765`. |
| `STUDY_AGENT_MCP_URL` | ACP server | Preferred MCP endpoint for HTTP MCP, for example `http://127.0.0.1:8790/mcp`. When set, ACP uses HTTP MCP. |
| `STUDY_AGENT_MCP_COMMAND` | ACP server | Command used to launch MCP as a managed subprocess in stdio mode. |
| `STUDY_AGENT_MCP_ARGS` | ACP server | Optional arguments passed to the managed MCP command. |
| `STUDY_AGENT_MCP_CWD` | ACP server | Working directory for the managed MCP subprocess. Defaults to the ACP process cwd. |
| `STUDY_AGENT_MCP_TOKEN` | ACP server | Optional bearer token for MCP HTTP requests. |
| `STUDY_AGENT_MCP_TIMEOUT` | ACP server | MCP request timeout in seconds. Default `240`. |
| `STUDY_AGENT_MCP_ONESHOT` | ACP server | Rebuild MCP stdio session per call when set to `1`. Mainly useful for diagnostics. |
| `STUDY_AGENT_THREADING` | ACP server | Enables threaded Flask serving when set truthy. |
| `STUDY_AGENT_ALLOW_CORE_FALLBACK` | ACP server | Allows ACP to fall back to core logic in paths that support it. |
| `STUDY_AGENT_SERVICE_REGISTRY` | ACP server | Optional override path for the service registry YAML. |
| `STUDY_AGENT_HEALTH_DEEP` | ACP server | Enables deeper health checks by default when set to `1`. |
| `ACP_TIMEOUT` | ACP server and R client | End-to-end ACP request timeout. Recommended to keep above `LLM_TIMEOUT`. |

## MCP Runtime

| Variable | Used by | Notes |
|---|---|---|
| `MCP_TRANSPORT` | MCP server, ACP startup docs | MCP transport. Typical values: `stdio` or `http`. |
| `MCP_HOST` | MCP server | MCP bind host for HTTP mode. Default `127.0.0.1`. |
| `MCP_PORT` | MCP server | MCP bind port for HTTP mode. Default `8790`. |
| `MCP_PATH` | MCP server | MCP HTTP path. Typical value `/mcp`. |

## ACP And MCP Connection Modes

ACP can attach to MCP in two different runtime modes:

1. HTTP mode
   ACP connects to a separately running MCP server using `STUDY_AGENT_MCP_URL`.
2. Managed stdio mode
   ACP launches MCP itself using `STUDY_AGENT_MCP_COMMAND`, optional `STUDY_AGENT_MCP_ARGS`, and optional `STUDY_AGENT_MCP_CWD`.

In code, `StudyAgent` accepts an optional `mcp_client` that satisfies the `MCPClient` protocol. ACP startup is responsible for instantiating the concrete transport client and injecting it into `StudyAgent`.

Practical selection rules:

- If `STUDY_AGENT_MCP_URL` is set, ACP uses HTTP MCP
- Else if `STUDY_AGENT_MCP_COMMAND` is set, ACP uses managed stdio MCP
- Else ACP starts without an MCP client and only limited core or fallback paths are available

## LLM Provider

| Variable | Used by | Notes |
|---|---|---|
| `LLM_API_URL` | ACP LLM client | OpenAI-compatible chat or responses endpoint. Default `http://localhost:3000/api/chat/completions`. |
| `LLM_API_KEY` | ACP LLM client | Required for most providers. |
| `LLM_MODEL` | ACP LLM client | Model name passed through to the provider. |
| `LLM_TIMEOUT` | ACP LLM client | LLM request timeout in seconds. Default `300`. |
| `LLM_USE_RESPONSES` | ACP LLM client | Use Responses API payload shape when set to `1`. Keep `0` for `/api/chat/completions` style endpoints. |
| `LLM_DRY_RUN` | ACP LLM client | Disables real LLM calls and returns mock behavior where supported. |
| `LLM_LOG` | ACP LLM client | Enables verbose LLM logging. |
| `LLM_LOG_PROMPT` | ACP LLM client | Logs prompt text. |
| `LLM_LOG_RESPONSE` | ACP LLM client | Logs raw response payloads. |
| `LLM_LOG_JSON` | ACP LLM client | Logs JSON payloads in more detail. |

## Phenotype Retrieval And Recommendation Tuning

| Variable | Used by | Notes |
|---|---|---|
| `PHENOTYPE_INDEX_DIR` | MCP retrieval, ACP preflight, R wrappers | Path to the built phenotype index directory. Use an absolute path when possible. |
| `EMBED_URL` | MCP retrieval, indexing scripts | Embedding endpoint URL. |
| `EMBED_MODEL` | MCP retrieval, indexing scripts | Embedding model name. |
| `EMBED_API_KEY` | MCP retrieval, indexing scripts | Optional embedding API key. |
| `EMBED_TIMEOUT` | MCP retrieval | Embedding request timeout in seconds. Default `120`. |
| `EMBED_LOG` | MCP retrieval | Enables embedding-layer debug logging. |
| `PHENOTYPE_DENSE_WEIGHT` | MCP retrieval | Weight assigned to dense retrieval when blending dense and sparse scores. |
| `PHENOTYPE_SPARSE_WEIGHT` | MCP retrieval | Weight assigned to sparse retrieval when blending dense and sparse scores. |
| `PHENOTYPE_REINDEX_ALLOW` | MCP retrieval / indexing safety | Allows reindex behaviors that are otherwise guarded. |
| `LLM_CANDIDATE_LIMIT` | ACP phenotype recommendation | Default candidate shortlist budget sent into recommendation planning. |
| `LLM_RECOMMENDATION_TOP_K` | ACP phenotype recommendation | Default retrieval `top_k` for recommendation flows. |
| `LLM_RECOMMENDATION_MAX_RESULTS` | ACP phenotype recommendation | Default final result count cap for recommendation flows. |
| `LLM_PLANNING_CANDIDATE_LIMIT` | ACP phenotype recommendation | Hidden planning-window budget used before final shortlist enforcement. |
| `LLM_PLANNING_TOP_BAND` | ACP phenotype recommendation | Hidden planner-visible top band after reranking. |

## Keeper, Vocabulary, PHOEBE, And OMOP

| Variable | Used by | Notes |
|---|---|---|
| `VOCAB_SEARCH_PROVIDER` | Keeper concept-set tools | Vocabulary search backend selector, for example `hecate_api` or `generic_search_api`. |
| `VOCAB_SEARCH_URL` | Keeper concept-set tools | Vocabulary search endpoint. |
| `VOCAB_SEARCH_TIMEOUT` | Keeper concept-set tools | Vocabulary search timeout in seconds. |
| `VOCAB_SEARCH_QUERY_PREFIX` | Keeper concept-set tools | Optional prefix prepended to generic search queries. |
| `VOCAB_SEARCH_QUERY_ID` | Keeper concept-set tools | Query id field used by some generic search APIs. |
| `VOCAB_METADATA_PROVIDER` | Keeper concept-set tools | Metadata backend selector, for example `db`. |
| `VOCAB_DATABASE_SCHEMA` | Keeper concept-set tools | OMOP vocabulary schema name. Default `vocabulary`. |
| `VOCAB_CONCEPT_TABLE` | Keeper concept-set tools | OMOP concept table name. Default `concept`. |
| `PHOEBE_PROVIDER` | Keeper concept-set tools | PHOEBE backend selector, for example `hecate_api` or `db`. |
| `PHOEBE_BULK_URL` | Keeper concept-set tools | Bulk PHOEBE endpoint used by the Hecate provider. |
| `PHOEBE_TIMEOUT` | Keeper concept-set tools | PHOEBE request timeout in seconds. Default `30`. |
| `PHOEBE_HTTP_RETRIES` | Keeper concept-set tools | Optional retry count for HTTP PHOEBE calls. |
| `PHOEBE_HTTP_BACKOFF_MS` | Keeper concept-set tools | Optional retry backoff in milliseconds for HTTP PHOEBE calls. |
| `PHOEBE_MAX_CONCEPTS` | Keeper concept-set tools | Optional total cap for PHOEBE-related concepts returned. |
| `PHOEBE_MAX_CONCEPTS_PER_RELATIONSHIP` | Keeper concept-set tools | Optional per-relationship PHOEBE cap. |
| `PHOEBE_RELATIONSHIP_IDS` | Keeper concept-set tools | Optional CSV list of relationship ids to request from PHOEBE. |
| `PHOEBE_DB_TABLE` | Keeper concept-set tools | Database table name for PHOEBE-backed concept recommendations. Default `concept_recommended`. |
| `OMOP_DB_ENGINE` | Keeper tools, profile extraction | SQLAlchemy engine URL for OMOP database access. |
| `ENGINE` | Keeper tools, profile extraction | Legacy fallback for `OMOP_DB_ENGINE`. Prefer `OMOP_DB_ENGINE`. |
| `PHOEBE_URL_TEMPLATE` | Keeper concept-set tools | Legacy variable. The Hecate HTTP provider no longer supports it; use `PHOEBE_BULK_URL` instead. |

## Logging

These are implemented through the shared logging utilities in `core/study_agent_core/logging_utils.py`.

| Variable | Used by | Notes |
|---|---|---|
| `STUDY_AGENT_LOG_DIR` | ACP, MCP | Directory for rotating log files when file logging is enabled. |
| `STUDY_AGENT_LOG_LEVEL` | ACP, MCP | Shared default log level when service-specific levels are not set. |
| `STUDY_AGENT_LOG_MAX_BYTES` | ACP, MCP | Rotation size threshold. Default `10485760`. |
| `STUDY_AGENT_LOG_BACKUP_COUNT` | ACP, MCP | Number of rotated files to keep. Default `5`. |
| `ACP_LOG_LEVEL` | ACP | ACP-specific log level override. |
| `MCP_LOG_LEVEL` | MCP | MCP-specific log level override. |
| `ACP_LOG_FILE` | ACP | Explicit ACP log file path. Overrides `STUDY_AGENT_LOG_DIR` for ACP. |
| `MCP_LOG_FILE` | MCP | Explicit MCP log file path. Overrides `STUDY_AGENT_LOG_DIR` for MCP. |
| `ACP_LOG_TO_CONSOLE` | ACP | Set falsy to suppress ACP console logging. |
| `MCP_LOG_TO_CONSOLE` | MCP | Set falsy to suppress MCP console logging. |

## Network And Container Rewriting

| Variable | Used by | Notes |
|---|---|---|
| `STUDY_AGENT_REWRITE_CONTAINER_HOSTS` | Shared networking helpers | Controls localhost-to-container-host rewriting. Default enabled. |
| `STUDY_AGENT_HOST_GATEWAY` | Shared networking helpers, compose | Replacement host used when rewriting container-localhost URLs. Default `host.docker.internal`. |

## Demo Shell And R Workflows

| Variable | Used by | Notes |
|---|---|---|
| `STUDY_AGENT_DEMO_ACP_URL` | Python demo shell | ACP URL used by the thin Python demo shell. |
| `STUDY_AGENT_DEMO_OUTPUT_DIR` | Python demo shell | Output directory used by the thin Python demo shell. |
| `ACP_URL` | R Keeper and Strategus flows | ACP base URL used by generated R scripts and shell-side helpers. Default `http://127.0.0.1:8765`. |
| `STUDY_AGENT_BASE_DIR` | R Strategus shells | Base directory override when launching shells from outside the repo root. |

## Recommended Minimal Local Setup

MCP over HTTP:

```bash
export MCP_TRANSPORT=http
export MCP_HOST=127.0.0.1
export MCP_PORT=8790
export MCP_PATH=/mcp
study-agent-mcp
```

ACP over HTTP:

```bash
export STUDY_AGENT_MCP_URL="http://127.0.0.1:8790/mcp"
export STUDY_AGENT_HOST=127.0.0.1
export STUDY_AGENT_PORT=8765
study-agent-acp
```

LLM-backed flows:

```bash
export LLM_API_KEY="..."
export LLM_API_URL="http://localhost:3000/api/chat/completions"
export LLM_MODEL="..."
```

Phenotype retrieval:

```bash
export PHENOTYPE_INDEX_DIR="/absolute/path/to/phenotype_index"
export EMBED_URL="http://localhost:3000/ollama/api/embed"
export EMBED_MODEL="qwen3-embedding:4b"
```

Recommended timeout ladder:

- `ACP_TIMEOUT > LLM_TIMEOUT > STUDY_AGENT_MCP_TIMEOUT`
- Typical starting point: `ACP_TIMEOUT=360`, `LLM_TIMEOUT=300`, `STUDY_AGENT_MCP_TIMEOUT=240`, `EMBED_TIMEOUT=120`

## Related Docs

- [`README.md`](../README.md)
- [`docs/TESTING.md`](./TESTING.md)
- [`docs/PHENOTYPE_INDEXING.md`](./PHENOTYPE_INDEXING.md)
- [`docs/SERVICE_REGISTRY.yaml`](./SERVICE_REGISTRY.yaml)
- [`docs/WORKFLOW_PHENOTYPE_RECOMMENDATION.md`](./WORKFLOW_PHENOTYPE_RECOMMENDATION.md)
- [`docs/WORKFLOW_CONTEXT_DIALOGUE_SLASH_OHDSI.md`](./WORKFLOW_CONTEXT_DIALOGUE_SLASH_OHDSI.md)
