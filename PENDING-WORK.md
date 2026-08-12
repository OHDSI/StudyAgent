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

## Preparation Note: Flexible Cohort Acquisition In R Shells

### Current findings

There are two real gaps in the current R shell design.

1. The incidence shell supports importing existing cohort definitions from a database schema, but the CohortMethod shell does not expose that path.
2. The current Strategus runtime assumes one shared database-connection profile for multiple jobs that may need to be separate in real deployments.

Relevant evidence:

- The incidence shell has explicit source-mode selection and DB cohort import helpers in `R/slashOhdsiStrategusAssistant/R/strategus_incidence_shell.R`.
- The CohortMethod shell currently validates target, comparator, and outcome cohort IDs only against local index-backed cohort JSONs in `R/slashOhdsiStrategusAssistant/R/strategus_cohort_methods_shell.R`.
- Shared DB cohort import helpers already exist in `R/slashOhdsiStrategusAssistant/R/cohort_definition_import.R`.
- Shared Strategus DB connection creation currently centers on a single `strategus-db-details.json` via `createStrategusConnectionDetails()` in `R/slashOhdsiStrategusAssistant/R/db_details.R`.

### Additional deployment requirement

The shell design also needs to support users who already have cohort definition JSON artifacts outside the phenotype index and outside direct database import.

Important real-world cases:

- a user exported or copied a cohort definition JSON from Atlas and wants to point the shell at that file
- a user has one or more cohort definition JSON files from another project directory and wants to reuse them directly
- a user wants to skip study-intent splitting and recommendation entirely and move straight to providing target/comparator/outcome cohort definitions

### Current architectural problem

The current shells treat cohort selection too narrowly.

Today the workflow is biased toward:

- derive role statements from a study intent
- run ACP recommendation or manual ID entry
- resolve selected cohort IDs against local index-backed cohort JSONs

That model is too restrictive for:

- airgapped deployments
- Atlas-derived cohort JSON reuse
- project-to-project cohort reuse
- environments where the cohort-definition source DB differs from the OMOP/patient-data execution DB

### Proposed design shift

Reframe both shells around a shared cohort-acquisition stage rather than around recommendation-only cohort selection.

For each required role, the shell should support multiple cohort-definition acquisition modes:

- `recommend`: ACP recommendation plus index-backed cohort selection
- `database`: import an existing cohort definition from a database schema exposing `cohort_definition` plus `cohort_definition_details`
- `file`: import a single local cohort definition JSON file
- `directory`: choose from a directory of cohort definition JSON files or imported project artifacts
- `reuse`: reuse already normalized local cohort-definition artifacts in the current workflow directory

The key simplification is that all of these sources should normalize into the same local managed artifact format before downstream workflow generation continues.

### Normalized cohort artifact model

Each acquired cohort definition should be represented locally with consistent metadata, regardless of source.

Suggested metadata fields:

- `source_type`: `index` | `database` | `file` | `directory` | `reuse`
- `source_id`
- `source_path`
- `source_schema`
- `cohort_definition_id`
- `cohort_name`
- `logic_description`
- `cache_path`
- `role`

This extends the same general pattern already used for database imports in `cohort_definition_import.R` and the incidence-shell selection records.

### Intent-split and recommendation should become optional earlier

The shells should expose an explicit workflow-entry mode instead of making users discover skip behavior only later.

Recommended entry modes:

1. `guided`
   - derive role statements from study intent
   - continue into cohort acquisition per role
2. `semi_guided`
   - user enters role statements manually
   - skip ACP intent split
   - continue into cohort acquisition per role
3. `direct`
   - skip study-intent splitting and role-statement derivation entirely
   - go straight to cohort acquisition per role

This should apply to both shells:

- CohortMethod: target, comparator, outcome
- Incidence: target, outcome

### Separate database connection roles

Treat these as separate first-class configuration surfaces.

1. Execution DB connection
- used by generated Strategus scripts
- used for CDM / work / results / vocabulary access
- used for diagnostics and cohort-method execution
- should continue to use `strategus-db-details.json`

2. Cohort source DB connection
- used only to import existing cohort definitions from a database schema
- should use a separate file such as `strategus-cohort-source-db-details.json`

Do not overload one JSON file with both roles. The airgapped deployment case is a strong reason to keep them separate:

- cohort-definition source DB may be postgres with username/password
- patient/work/results execution DB may be SQL Server with Windows auth

### Important additional connection nuance

There is also an ACP/MCP-side OMOP connectivity surface used by Keeper profile generation.

That means there are effectively three relevant connection concepts in some deployments:

- R Strategus execution DB
- cohort-definition source DB
- MCP OMOP DB used by Keeper flows

The shells and docs should make this distinction clearer, especially because Keeper profile generation needs to point at the same effective cohort/work database context used by the generated workflow artifacts.

### Shared helper direction

Do not duplicate source-mode logic separately in each shell.

Recommended shared helper areas:

- source-mode prompt / dispatch
- file import helper
- directory import helper
- database import helper reuse from `cohort_definition_import.R`
- cohort-definition validation and normalization
- selection-record metadata helpers

The incidence shell already provides useful patterns for:

- `choose_selection_source_mode()`
- `selection_record_from_recommendation()`
- `selection_record_from_import()`
- `imported-cohort-definitions/` caching

These should be generalized and reused by the CohortMethod shell rather than reimplemented from scratch.

### Recommended implementation phases

1. Introduce a shared cohort-acquisition abstraction
- shared source modes
- shared normalized artifact metadata
- shared cache conventions

2. Add local file and directory acquisition modes first
- lower operational complexity than DB import
- immediately useful in airgapped settings
- supports Atlas-export and cross-project reuse scenarios

3. Add separate cohort-source DB config support
- introduce `strategus-cohort-source-db-details.json`
- reuse `cohort_definition_import.R`
- wire DB cohort import into the CohortMethod shell

4. Move intent split behind an explicit shell-start mode choice
- `guided`
- `semi_guided`
- `direct`

5. Update docs and state/resume behavior
- document the new acquisition modes
- document the split DB configuration roles
- persist normalized cohort-source metadata so resume and inspection remain coherent

### Practical UX recommendation

Keep prompts shallow.

For each role, the shell should ask only one initial acquisition question, for example:

- `Source for target cohort [Enter=recommend, db=database, file=JSON file, dir=directory, reuse=existing local]:`

Then branch only into the prompts required for that mode.

Defaults should follow the shell-start mode:

- `guided` defaults to `recommend`
- `direct` defaults to `file` or `dir`
- if reusable local artifacts already exist, surface `reuse` clearly

### Important behavioral decision to preserve clarity

When a cohort definition is imported from a database, file, or directory and later modified by shell-side improvement steps, the shell should make it explicit that it is editing a local managed working copy, not mutating the upstream Atlas definition or the original source file automatically.

### Recommendation for next implementation session

Treat this as a shared shell-design improvement, not a one-off CohortMethod patch.

Immediate concrete target:

1. define the normalized cohort-acquisition model
2. add file / directory acquisition support in shared helpers
3. add separate cohort-source DB config support
4. port database acquisition into the CohortMethod shell using the incidence-shell pattern
5. only then refine the shell-start mode UX for optional intent splitting
