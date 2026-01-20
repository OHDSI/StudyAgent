# ACP Bridge (Prototype)

- Python 3.9+
- Install deps: `python3 -m pip install flask requests`
- Optional OpenWebUI HTTP model:
  - `export OPENWEBUI_API_URL="http://localhost:3000/api/chat/completions"` (default)
  - `export OPENWEBUI_API_KEY="..."` (required)
  - `export OPENWEBUI_MODEL="agentstudyassistant"` (default)
- Optional generic CLI model (reads prompt from stdin, returns JSON): `export ACP_MODEL_CMD="my-cli --flag"`
- Set `ACP_MODEL_LOG=1` (default) to see OUTGOING/INCOMING/STDERR traces for model calls.
- Endpoints:
  - `GET /health`
  - `POST /tools/propose_concept_set_diff`
  - `POST /tools/cohort_lint`
  - `POST /actions/concept_set_edit`
  - `POST /actions/execute_llm` (executes LLM-proposed actions for concept sets)

Example action payload (dry-run):

```json
{
  "artifactRef": "path-or-url-to-concept-set.json",
  "ops": [
    {
      "op": "set_include_descendants",
      "where": { "domainId": "Drug", "conceptClassId": "Ingredient", "includeDescendants": false },
      "value": true
    }
  ],
  "write": false
}
```
