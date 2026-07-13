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

Use the actual package exports and tests as the best indicator of current core functionality:

- [`core/study_agent_core/__init__.py`](./study_agent_core/__init__.py)
- [`core/study_agent_core/tools.py`](./study_agent_core/tools.py)
- [`tests/test_core_tools.py`](../tests/test_core_tools.py)

## Where To Look

For service and workflow orientation, start with:

- [`docs/SERVICE_REGISTRY.yaml`](../docs/SERVICE_REGISTRY.yaml)
- [`docs/WORKFLOW_PHENOTYPE_RECOMMENDATION.md`](../docs/WORKFLOW_PHENOTYPE_RECOMMENDATION.md)
- [`docs/WORKFLOW_CONTEXT_DIALOGUE_SLASH_OHDSI.md`](../docs/WORKFLOW_CONTEXT_DIALOGUE_SLASH_OHDSI.md)
- [`docs/WORKFLOW_COHORT_METHODS.md`](../docs/WORKFLOW_COHORT_METHODS.md)
- [`docs/WORKFLOW_INCIDENCE.md`](../docs/WORKFLOW_INCIDENCE.md)
- [`docs/SPEC_KEEPER_INTERFACE.md`](../docs/SPEC_KEEPER_INTERFACE.md)
- [`docs/PHENOTYPE_VALIDATION_REVIEW.md`](../docs/PHENOTYPE_VALIDATION_REVIEW.md)

Use `SERVICE_REGISTRY.yaml` as an important metadata surface, but not as the only source of truth for runtime behavior.
