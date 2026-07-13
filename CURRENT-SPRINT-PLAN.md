# Current Sprint Plan

## Preparation Note: Service Registry and Integration

### Current finding

`workflow_context_dialogue` is an implemented ACP flow and is documented in `docs/WORKFLOW_CONTEXT_DIALOGUE_SLASH_OHDSI.md`, but it is missing from `docs/SERVICE_REGISTRY.yaml`. That appears to be a real omission rather than an intentional exclusion.

### Why the omission matters

- The flow exists in ACP runtime routing at `/flows/workflow_context_dialogue`.
- It has a real ACP implementation and is used by R wrappers, Strategus shells, and the demo shell.
- If it is missing from the registry, service discovery and integration metadata drift away from the actual implemented surface.

### What the registry does today

The service registry currently has a real but limited role:

- ACP `/services` uses `docs/SERVICE_REGISTRY.yaml` as a metadata source.
- ACP also keeps a separate hard-coded runtime `SERVICES` list.
- `/services` merges the registry-defined services with the runtime-defined services.
- If a flow exists at runtime but is missing from the registry, ACP still exposes it and emits a warning.
- The registry is also used for at least one real runtime configuration purpose outside ACP service listing: `mcp_server/study_agent_mcp/tools/_service_registry.py` reads validation metadata such as controlled identifier keys.

### Current conclusion

The registry is not currently the operational source of truth for implemented services.

It behaves more like:

- a declarative metadata overlay for service discovery
- a partial configuration source for selected validation behavior
- a completeness target for internal/external integration surfaces

This explains how a mature flow like `workflow_context_dialogue` could be missing without breaking the flow itself.

### Integration concern

If the registry is expected to support integration with other agentic tooling, then a missing flow is not a small documentation issue. It is evidence that the project currently has two service catalogs:

1. runtime truth in ACP code
2. declarative metadata truth in the registry

That split creates drift risk for:

- external orchestration
- service discovery
- client generation
- UI capability introspection
- cross-project integration contracts

### Recommendation for next session

Treat this as part of a broader integration design discussion, not just a one-off registry patch.

Topics to cover:

1. Should the registry become the single source of truth for services?
2. Should runtime `/services` be generated from the registry, or should the registry be generated from runtime definitions?
3. What contract fields are required for serious integration with other agentic tooling?
4. What parity checks or tests should be added so implemented flows cannot be omitted from the registry?
5. How should validation/configuration metadata be separated from service discovery metadata, if at all?

### Immediate factual note

Before editing the registry entry for `workflow_context_dialogue`, confirm:

- the exact MCP tool or prompt-bundle dependency used by the flow
- the exact normalized response shape returned by `run_workflow_context_dialogue_flow(...)`

Those should be captured precisely if and when the registry entry is added.
