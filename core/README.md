# study-agent core

`core/` contains the deterministic, non-IO business logic used by the ACP and MCP layers. This is where pure validation, normalization, and helper logic should live when it does not require network calls, filesystem side effects, or direct model invocation.

This README is intentionally thin. The higher-level service surface and workflow contracts evolve faster than the core package layout, so the maintained documentation under [`docs/`](../docs/) should be treated as the primary reference surface.

## What Lives Here

The current Python package is under [`core/study_agent_core/`](./study_agent_core/).

It currently includes the shared core logic for implemented flows such as:

- phenotype recommendation
- phenotype improvements
- phenotype intent splitting
- phenotype recommendation advice
- phenotype validation review
- cohort methods intent splitting
- concept-set diffing and cohort linting

`phenotype_make_computable` is intentionally not exported as a single core tool. Its public flow combines ACP orchestration with MCP prompt, retrieval, and R-based technical validation; its shared request/response models live in `core/study_agent_core/models.py`.

Use the actual package exports and tests as the best indicator of current core functionality:

- [`core/study_agent_core/__init__.py`](./study_agent_core/__init__.py)
- [`core/study_agent_core/tools.py`](./study_agent_core/tools.py)
- [`tests/test_core_tools.py`](../tests/test_core_tools.py)

## Where To Look

For service and workflow orientation, start with the maintained [`docs/`](../docs/) directory, especially [`SERVICE_REGISTRY.yaml`](../docs/SERVICE_REGISTRY.yaml) and the relevant `WORKFLOW_*.md` document. Implementation and tests remain the runtime source of truth.
