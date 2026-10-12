# Atlas3 and WebAPI Integration

## Purpose

Study Agent can support review-gated phenotype selection, concept-set authoring, and a bounded set of cohort-definition authoring workflows in Atlas3. Atlas3 and WebAPI remain independent applications: Study Agent exposes ACP/MCP capabilities, while WebAPI owns Atlas-facing authorization, persistence, and API contracts.

This document describes the demonstrated integration boundary. It is not a claim that every Atlas cohort feature, Circe construct, or narrative cohort request is supported.

## Component responsibilities

| Component | Responsibility |
|---|---|
| Study Agent ACP | Orchestrates `/ohdsi` dialogue, phenotype recommendation, and review-gated workflow decisions. |
| Study Agent MCP | Serves prompt bundles, phenotype retrieval, vocabulary-backed candidate slices, and technical Capr/Circe validation tools. |
| WebAPI | Enforces Atlas permissions, persists workflow/review state and provenance, and brokers Atlas requests to ACP. |
| Atlas3 | Presents the established concept-set and cohort-definition UI, including review, save, provenance, and recovery affordances. |

Study Agent does not require Atlas3 or WebAPI to run. Atlas3/WebAPI integration is an optional client deployment of the Study Agent services.

## Demonstrated Atlas paths

- **Concept-set assistance:** `/ohdsi` provides advisory dialogue and bounded candidate proposals. A user explicitly selects inclusion/exclusion, descendant, and mapped policies before anything changes in the Atlas concept set.
- **Phenotype selection:** AI-supported search and phenotype-library browse show computability and source-status information. Executable OHDSI candidates can open an unsaved draft; non-computable candidates can be used as evidence for new authoring.
- **Cohort authoring:** the current supported slice covers a reviewed primary index concept-set asset with a bounded set of reviewed supporting Condition or Visit bindings. Advanced Boolean, recurrence, and temporal logic must remain clearly unsupported or review-only until separately implemented.

The saved cohort embeds the accepted concept-set expression snapshot/checksum. A later edit to the standalone concept set must not silently alter that saved cohort.

## Authorization and persistence

WebAPI must expose the Study Agent permissions used by the Atlas UI, including separate concept-set and cohort-definition assistance permissions. An administrator assigns these permissions through Atlas configuration; a user without the required permission must receive an authorization failure rather than an incomplete or silently degraded workflow.

The WebAPI database migrations that create Study Agent permissions and workflow/provenance state must be applied before testing Atlas controls. The UI should only present capabilities enabled by the deployed WebAPI configuration.

## Deployment notes

- Configure the ACP endpoint in WebAPI using its deployment configuration; do not embed service URLs or credentials in Atlas client code.
- Configure CORS and reverse-proxy behavior for the actual public Atlas origin.
- Treat browser-visible candidates as a bounded retrieval/review slice, never proof that a complete clinical concept set was found.
- Restart services after their own code or configuration changes: MCP after tool/prompt/retrieval changes; ACP after its server/client contract changes; WebAPI after its deployment configuration or migrations change.

For service configuration and startup details, see [ENVIRONMENT.md](ENVIRONMENT.md). For phenotype authoring guardrails, see [WORKFLOW_PHENOTYPE_MAKE_COMPUTABLE.md](WORKFLOW_PHENOTYPE_MAKE_COMPUTABLE.md) and [WORKFLOW_CONTEXT_DIALOGUE_SLASH_OHDSI.md](WORKFLOW_CONTEXT_DIALOGUE_SLASH_OHDSI.md).
