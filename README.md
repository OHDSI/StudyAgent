# OHDSI Study Assistant proof of concept Jan 2026

This repo contains:
- A tiny **ACP-like bridge** (`acp/server.py`) exposing:
  - `/tools/propose_concept_set_diff` (Review concept set for gaps and inconsistencies given the study intent)
  - `/tools/cohort_lint` (Review cohort JSON for general design issues (washout/time-at-risk, inverted windows, empty or conflicting criteria))
  - `/tools/phenotype_recommendations` (Suggest relevant phenotypes from catalog for the study intent (stub if no LLM))
  - `/tools/phenotype_improvements` (Review selected phenotypes for improvements against study intent (stub if no LLM))
- An **R package** `that calls the bridge (or uses a local fallback).
- A **demo** study in `demo/`.

Currently, this is a minimalistic demo
- basic concept set and cohort definition checks
- early and limited version of phenotype suggestion and linting relative to a study intent

## Quick start

1) Start bridge:

```bash
./scripts/start_acp.sh
```

Optional) Use OpenWebUI HTTP backend (recommended):

```bash
export OPENWEBUI_API_KEY="..."  # required
export OPENWEBUI_API_URL="http://localhost:3000/api/chat/completions"  # default
export OPENWEBUI_MODEL="agentstudyassistant"  # default
export FLASK_DEBUG=1 # Optional but helpful
./scripts/start_acp.sh
```

In R, [run the demo R script](scripts/test_llm_actions.R)

