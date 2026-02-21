# study-agent ACP agent
Orchestrates user interaction and calls MCP tools. No direct data plane access unless explicitly required.

## ACP Server Configuration

- `STUDY_AGENT_HOST` (default `127.0.0.1`)
- `STUDY_AGENT_PORT` (default `8765`)

## LLM Configuration (OpenAI-compatible)

Set these environment variables to enable LLM calls from ACP:

- `LLM_API_URL` (default `http://localhost:3000/api/chat/completions`)
- `LLM_API_KEY` (required)
- `LLM_MODEL` (default `agentstudyassistant`)
- `LLM_TIMEOUT` (default `180`)
- `LLM_LOG` (default `0`)
- `LLM_DRY_RUN` (default `0`)
- `LLM_USE_RESPONSES` (default `0`, use OpenAI Responses API payload/parse instead of Chat Completions; unrelated to MCP tool use)
- `LLM_CANDIDATE_LIMIT` (default `10`)

See `docs/TESTING.md` for CLI smoke tests.
