# study-agent MCP server

Exposes core tools via MCP for reuse across agents, plus phenotype retrieval and prompt bundle tools.

## Tool Inventory

Phenotype retrieval + metadata:
- `phenotype_search`
- `phenotype_recommendations`
- `phenotype_improvements`
- `phenotype_fetch_summary`
- `phenotype_fetch_definition`
- `phenotype_list_similar`
- `phenotype_reindex`
- `phenotype_index_status`
- `phenotype_prompt_bundle`
- `phenotype_recommendation_advice`

Study design linting:
- `propose_concept_set_diff`
- `cohort_lint`
- `lint_prompt_bundle`

Keeper validation:
- `keeper_prompt_bundle`
- `keeper_sanitize_row`
- `keeper_build_prompt`
- `keeper_parse_response`

Authoring new MCP tools: see `docs/MCP_TOOL_AUTHORING.md`.

## Running MCP over HTTP (recommended for cross-platform stability)

```bash
export MCP_TRANSPORT=http
export MCP_HOST=127.0.0.1
export MCP_PORT=8790
export MCP_PATH=/mcp
study-agent-mcp
```

ACP connects via:

```bash
export STUDY_AGENT_MCP_URL="http://127.0.0.1:8790/mcp"
```
