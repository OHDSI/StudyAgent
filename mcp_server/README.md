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
- `phenotype_prompt_bundle`

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
