# R Package Architecture Plan

## Purpose

This document expands sprint item 3 in `CURRENT-SPRINT-PLAN.md` into a concrete architecture plan for the R side of the project.

The current `R/OHDSIAssistant/` package mixes three responsibilities:

- ACP transport and call/response helpers
- thin R wrappers around ACP flows and actions
- high-level Strategus workflow orchestration and interactive shells

That coupling is already visible in the current code:

- [`R/OHDSIAssistant/R/acp_client.R`](/ai-agent/HadesProject/OHDSI-Study-Agent/R/OHDSIAssistant/R/acp_client.R) owns connection state and raw POST behavior
- [`R/OHDSIAssistant/R/phenotype_workflow.R`](/ai-agent/HadesProject/OHDSI-Study-Agent/R/OHDSIAssistant/R/phenotype_workflow.R), [`R/OHDSIAssistant/R/cohort_methods_workflow.R`](/ai-agent/HadesProject/OHDSI-Study-Agent/R/OHDSIAssistant/R/cohort_methods_workflow.R), [`R/OHDSIAssistant/R/lintStudyDesign.R`](/ai-agent/HadesProject/OHDSI-Study-Agent/R/OHDSIAssistant/R/lintStudyDesign.R), and [`R/OHDSIAssistant/R/concept_set_actions.R`](/ai-agent/HadesProject/OHDSI-Study-Agent/R/OHDSIAssistant/R/concept_set_actions.R) are flow/action wrappers but still depend directly on the transport internals
- [`R/OHDSIAssistant/R/strategus_incidence_shell.R`](/ai-agent/HadesProject/OHDSI-Study-Agent/R/OHDSIAssistant/R/strategus_incidence_shell.R) and [`R/OHDSIAssistant/R/strategus_cohort_methods_shell.R`](/ai-agent/HadesProject/OHDSI-Study-Agent/R/OHDSIAssistant/R/strategus_cohort_methods_shell.R) directly call ACP endpoints while also owning interactive workflow state, checkpoints, artifact layout, and script generation

The package split should isolate those concerns before more `/ohdsi` dialogue work, incidence-shell extension, and concept-set generation integration are added.

## Goals

1. Create a small ACP-focused R package with a stable, testable HTTP interface and typed request/response helpers.
2. Move Strategus shells and workflow orchestration into a separate higher-level package that depends on the ACP package rather than internal transport functions.
3. Define one small workflow-stage contract that all shells use when asking ACP for contextual dialogue or recommendations.
4. Keep the migration incremental so the existing `OHDSIAssistant` package can continue to work during the transition.

## Non-Goals

- Rewriting the ACP server API
- Reworking the generated Strategus script content unless required by the package split
- Solving future Atlas integration now beyond defining the contract seam

## Proposed Package Split

### Package A: ACP client package

Working name: `slashOhdsiAcpClient`

Responsibility:

- manage ACP connection configuration
- perform authenticated HTTP requests
- expose thin, documented wrappers around ACP flows and actions
- normalize request payloads and response parsing
- provide error handling, timeout handling, and optional retry helpers

This package should not:

- own interactive shell state
- write Strategus project folders or scripts
- decide workflow progression
- embed stage-specific assumptions about cohort methods vs incidence workflows beyond request payload fields

### Package B: Strategus workflow package

Working name: `slashOhdsiStrategusAssistant`

Responsibility:

- own user-facing workflow shells
- collect inputs, manage checkpoints, and maintain local artifact layout
- interpret ACP responses in workflow context
- generate Strategus-ready scripts and analysis assets
- decide when to call dialogue, recommendation, improvement, or concept-set flows

This package should depend on Package A only through exported functions and response objects.

## Proposed Ownership Mapping

### Move into ACP client package

- `R/acp_client.R`
- `R/ops_llm_actions.R`
- thin ACP wrappers now embedded in:
  - `R/phenotype_workflow.R`
  - `R/cohort_methods_workflow.R`
  - `R/lintStudyDesign.R`
  - `R/concept_set_actions.R`

Target exports in the ACP client package should look more like:

- `acp_connect()`
- `acp_is_connected()`
- `acp_call_flow(flow_name, body)`
- `acp_call_action(action_name, body)`
- `acp_suggest_phenotypes(...)`
- `acp_review_phenotypes(...)`
- `acp_suggest_cohort_method_specs(...)`
- `acp_workflow_context_dialogue(...)`
- `acp_keeper_concept_sets_generate(...)`
- `acp_lint_study_design(...)`

The important change is not only moving code. The workflow package must stop depending on unexported transport internals such as `.acp_post` and `acp_state`.

### Keep or move into Strategus workflow package

- `R/strategus_incidence_shell.R`
- `R/strategus_cohort_methods_shell.R`
- `R/db_details.R`
- `R/execution_settings.R`
- `R/utils_json.R`
- local script-generation helpers
- selection helpers that are meaningful only in workflow context
- artifact copy/apply helpers for selected cohorts and patched cohorts

### Likely split between both packages

Current files that mix concerns should be decomposed:

- `R/phenotype_workflow.R`
  - ACP client package: request/response wrappers
  - workflow package: interactive selection and local definition-pull orchestration if still needed there
- `R/cohort_methods_workflow.R`
  - ACP client package: spec recommendation call
  - workflow package: any shell-facing summary rendering or default reconciliation
- `R/lintStudyDesign.R`
  - ACP client package if retained as a generic ACP consumer
  - workflow package only if it remains positioned as a Strategus-shell utility
- `R/concept_set_actions.R`
  - ACP client package for generic concept-set action calls
  - workflow package only for shell-local convenience wrappers if required

## Workflow Stage Contract

This is the key foundation for items 1, 2, and 4.

The workflow package should pass a single small object into the ACP client package whenever context-aware dialogue or stage-specific recommendations are needed.

Proposed R shape:

```r
workflow_stage_context <- list(
  workflow_type = "strategus_cohort_methods",   # or "strategus_incidence"
  current_step = "target_selection",  # or others shown in the "Shared stages" and workflow-sepecific sections below
  step_label = "Target cohort selection", # and others mentioned below
  user_goal = studyIntent,
  entities = list(
    target = NULL,
    comparator = NULL,
    outcomes = list()
  ),
  available_artifacts = list(
    protocol_path = NULL,
    selected_target_ids = list(),
    selected_comparator_ids = list(),
    selected_outcome_ids = list(),
    analysis_settings_path = NULL,
    concept_set_paths = list()
  ),
  dialogue = list(
    prior_questions = list(),
    prior_answers = list(), # each item could be an identifiers of a JSONL record and a short ~50 character summary that the  LLM could use to request more details if needed so context does not grow 
    last_user_message = NULL
  ),
  constraints = list(
    interactive = TRUE,
    allow_recommendations = TRUE,
    allow_generation = FALSE
  )
)
```

Required fields for the first pass:

- `workflow_type`
- `current_step`
- `user_goal`

Recommended fields for the first pass:

- `entities`
- `available_artifacts`
- `dialogue$last_user_message`
- `constraints`

Rules for the contract:

1. `current_step` must be a small controlled vocabulary owned by the workflow package.
2. ACP client functions should forward the object without embedding shell-specific branching into the transport layer.
3. The contract must be versionable. Add `contract_version = 1L` when this is implemented.
4. The same top-level fields must work for cohort-method, incidence shells, and other worflow shells, with some fields empty when irrelevant.

## Controlled Vocabulary for `current_step`

Use a stable step vocabulary now so item 2 does not invent a second shape later.

Shared stages:

- `study_intent_capture`
- `intent_split`      # incidence analysis splits to "target" and "outcome" while cohort method adds "comparator"
- `target_selection`
- `outcome_selection`
- `phenotype_review`
- `keeper_concept_set_generation`
- `keeper_case_review`
- `workflow_summary`

Cohort-method-specific stages:
- `comparator_selection` 
- `analytic_settings_collection`
- `cohort_method_spec_recommendation`
- `cohort_method_spec_confirmation`

Incidence-specific stages:

- `incidence_design_setup`
- `time_at_risk_configuration`

These labels do not need to be identical to UI labels. They should be stable machine-facing identifiers.

## API Shape Between Packages

The workflow package should not build raw endpoint paths. Instead it should call exported ACP package functions such as:

```r
client <- acp_client(url = acpUrl, token = NULL)

resp <- acp_workflow_context_dialogue(
  client = client,
  stage_context = workflow_stage_context,
  message = user_message
)
```

Preferred client pattern:

- explicit client object returned from `acp_client()` or similar constructor
- no hidden global mutable state as the primary interface
- No need for a compatibility bridge for `acp_connect()` during migration - this can be a clean refactor

Why this matters:

- shells can hold their own client handle
- tests can inject mock clients
- multiple ACP endpoints can be targeted in one R session if needed
- the workflow package stops depending on package-global side effects

## Migration Plan

### Phase 0: Document and freeze the seam

- create this design note
- agree on package names or temporary names
- agree on the `workflow_stage_context` fields and `current_step` vocabulary

Deliverable:

- approved architecture note and contract

### Phase 1: Extract the ACP client surface without changing behavior

- create a new package directory for the ACP client
- move `acp_connect()` and `.acp_post()` behavior behind exported client functions
- add wrappers for the currently used flows and actions
- keep response shapes unchanged where possible

Deliverable:

- workflow code can call exported ACP helpers without using `.acp_post`

### Phase 2: Refactor shells to consume the ACP package

- replace direct `.acp_post()` usage in both Strategus shells
- replace checks against `acp_state$url` with explicit ACP client availability checks
- route all `/ohdsi` or stage-aware dialogue calls through `acp_workflow_context_dialogue()`

Deliverable:

- both shells depend only on the ACP package public API

### Phase 3: Introduce the stage-context contract

- define helper constructors in the workflow package for stage context objects
- update cohort-method workflow dialogue calls to use the contract
- extend `runStrategusIncidenceShell()` to use the same contract and `current_step` semantics

Deliverable:

- one shared stage-context payload across both shells

### Phase 4: Integrate `keeper_concept_sets_generate` through the new seam

- add a thin ACP wrapper in the ACP client package
- add workflow-package integration points for concept-set generation near covariate concept-set selection
- keep the function reusable outside shells

Deliverable:

- item 4 can land without reintroducing cross-layer coupling

### Phase 5: Compatibility cleanup

- This is a clean refactor that can replace the deprecated old combined exports from `OHDSIAssistant` 
- update README and examples
- add package-focused tests

Deliverable:

- clear public surface and lower maintenance cost

## Immediate Implementation Recommendations

These are the concrete next code tasks that should happen first.

1. Introduce an ACP client object and exported flow wrappers before any new incidence-shell `/ohdsi` work.
2. Extract a shared helper that builds `workflow_stage_context` objects from shell state.
3. Replace direct `.acp_post("/flows/workflow_context_dialogue", ...)` usage in the cohort-method shell with a wrapper call.
4. Extend the incidence shell to use the same wrapper and controlled `current_step` labels.
5. Only after that, add `keeper_concept_sets_generate` as another wrapper plus workflow insertion point.

## Risks

- If the split is attempted by moving files first without introducing a real public ACP API, the new package boundary will be cosmetic only.
- If the workflow-stage contract is too large, it will become a second shell implementation rather than a stable interface.
- If `current_step` labels diverge between shells, item 1 and item 2 will create parallel dialogue logic that is harder to maintain than the current state.

## Testing Strategy

Add tests at both package levels.

ACP client package:

- request payload tests
- response parsing tests
- error and timeout handling tests
- mock transport tests for each exported wrapper

Workflow package:

- stage-context builder tests
- shell checkpoint/resume tests
- integration tests that verify correct ACP wrapper calls per workflow stage
- regression tests for generated artifact layout and scripts

## How This Unblocks the Other Sprint Items

Item 1:

- stage-aware dialogue UX becomes a workflow concern backed by one shared context contract

Item 2:

- incidence-shell `/ohdsi` support can reuse the same ACP wrapper and `current_step` vocabulary

Item 4:

- `keeper_concept_sets_generate` becomes a thin ACP wrapper plus a workflow insertion point, not another direct shell-to-endpoint special case

Item 5:

- follow-on workflow features can add new stages or wrappers without deep edits to transport code

## Recommended Decision

Proceed with a two-package split, but implement it as an API-first extraction instead of a file-move-first refactor.

The first concrete coding milestone should be:

- a new ACP client package surface
- a shared `workflow_stage_context` helper
- refactoring the cohort-method shell to use those two abstractions before adding any more shell features
