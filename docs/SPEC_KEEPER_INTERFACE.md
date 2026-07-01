# Keeper Interface Spec

This document captures the current concrete interface layer for the ACP-based Keeper workflow used by the OHDSI Study Agent.

## Flows

### `/flows/keeper_concept_sets_generate`

Request model: `KeeperConceptSetsGenerateInput`

- `phenotype`: clinical event of interest
- `domain_keys`: optional subset of Keeper generation domains
- `vocab_search_provider`: optional provider override such as `hecate_api`, `generic_search_api`, or `db`
- `phoebe_provider`: optional provider override such as `hecate_api`, `db`, or `none`; when `hecate_api` is selected the MCP always uses the Hecate bulk PHOEBE endpoint
- `candidate_limit`: max candidate concepts per term/domain
- `min_record_count`: optional candidate filter
- `include_diagnostics`: include per-step counts and provider metadata

Response model: `KeeperConceptSetsGenerateOutput`

- `concept_sets`: flat list of normalized Keeper concept rows
- `domains`: per-domain structured results including seed terms and step diagnostics
- `diagnostics`: top-level provider/config/timing metadata

### `/flows/keeper_profiles_generate`

Request model: `KeeperProfilesGenerateInput`

- `cohort_database_schema`
- `cohort_table`
- `cohort_definition_id`
- `cdm_database_schema`
- `sample_size`
- `person_ids`
- `keeper_concept_sets`
- `phenotype_name`
- `use_descendants`
- `remove_pii`

Response model: `KeeperProfilesGenerateOutput`

- `rows`: Keeper-style review rows suitable for downstream review
- `row_count`
- `sample_size_requested`
- `sample_size_returned`
- `diagnostics`

This flow is deterministic only. It must not call an LLM.

### `/flows/phenotype_validation_review`

Request model: `PhenotypeValidationReviewInput`

- `disease_name`
- `keeper_row`

Response model: `PhenotypeValidationReviewOutput`

- `label`
- `rationale`
- `mode`

`keeper_row` must be sanitized before any LLM call.


### `/flows/case_causal_review`

Request model: `CaseCausalReviewInput`

- `adverse_event_name`
- `source_type`
- `case_row`
- `allowed_domains`

`case_row` is a compact canonical representation shaped upstream by pv-copilot and should contain:

- `case_id`
- `case_summary`
- `index_event`
- `candidate_items`
- `context_items`
- `case_metadata`
- `annotations`
- `tool_hints`

Structured ranking is limited to `candidate_items` only.
`context_items` and `case_metadata` may influence reasoning but are not automatically ranked.
`index_event` is assumed to have occurred and must never be ranked as a cause.

Response model: `CaseCausalReviewOutput`

- `flow_name`
- `mode`
- `candidates_by_domain`
- `narrative`
- `diagnostics`

Optional MCP enrichment tools may be used, but successful execution must not depend on them.

## Shared Row And Concept Models

### `KeeperConceptSetItem`

Normalized concept-set row:

- `conceptId`
- `conceptName`
- `vocabularyId`
- `conceptSetName`
- `target`
- `domainId`
- `conceptClassId`
- `standardConcept`
- `recordCount`
- `score`
- `sourceTerm`
- `sourceStage`

`conceptSetName` is constrained to:

- `doi`
- `alternativeDiagnosis`
- `symptoms`
- `drugs`
- `diagnosticProcedures`
- `measurements`
- `treatmentProcedures`
- `complications`

### `KeeperProfileRow`

This model intentionally spans both:

- the current ACP review payload used by `phenotype_validation_review`
- the canonical row-oriented output produced after Keeper profile extraction

Supported fields include:

- demographics: `phenotype`, `generatedId`, `age`, `sex`, `gender`, `observationPeriod`, `race`, `ethnicity`
- evidence fields: `presentation`, `visits`, `visitContext`, `symptoms`, `priorDisease`, `postDisease`, `afterDisease`, `priorDrugs`, `postDrugs`, `afterDrugs`, `priorTreatmentProcedures`, `postTreatmentProcedures`, `afterTreatmentProcedures`, `alternativeDiagnoses`, `alternativeDiagnosis`, `diagnosticProcedures`, `measurements`, `death`
- metadata: `cohortPrevalence`

The duplicate legacy and canonical names are deliberate for the transition period:

- `sex` and `gender`
- `visits` and `visitContext`
- `alternativeDiagnoses` and `alternativeDiagnosis`
- `postDisease` and `afterDisease`
- `postDrugs` and `afterDrugs`
- `postTreatmentProcedures` and `afterTreatmentProcedures`

## MCP Tool Signatures

### Prompt/config tools

`keeper_concept_set_bundle(phenotype: str, domain_key: str) -> dict`

- returns prompt/config assets for one Keeper concept-set domain

`keeper_prompt_bundle(disease_name: str) -> dict`

- existing prompt bundle for patient-row adjudication

`keeper_build_prompt(disease_name: str, sanitized_row: dict) -> dict`

- existing patient-row prompt builder

`keeper_parse_response(llm_output: dict | str) -> dict`

- existing adjudication parser

### Vocabulary/provider tools

`vocab_search_standard(query: str, domains: list[str], concept_classes: list[str], limit: int, provider: str = "") -> dict`

- provider-backed candidate search
- must return normalized concept rows

`phoebe_related_concepts(concept_ids: list[int], relationship_ids: list[str] = [], provider: str = "") -> dict`

- provider-backed related concept retrieval

`vocab_filter_standard_concepts(concepts: list[dict], domains: list[str], concept_classes: list[str]) -> dict`

- deterministic OMOP vocabulary filtering

`vocab_remove_descendants(concept_ids: list[int]) -> dict`

- deterministic `concept_ancestor` pruning

`vocab_add_nonchildren(base_concept_ids: list[int], candidate_concepts: list[dict]) -> dict`

- adds candidates that are not descendants of already included concepts

`vocab_fetch_concepts(concept_ids: list[int]) -> dict`

- deterministic enrichment from local OMOP vocabulary

### Profile extraction tools

`keeper_profile_extract(cdm_database_schema: str, cohort_database_schema: str, cohort_table: str, cohort_definition_id: int, keeper_concept_sets: list[dict], sample_size: int = 20, person_ids: list[str] = [], use_descendants: bool = True, remove_pii: bool = True) -> dict`

- deterministic OMOP extraction using `OMOP_Alchemy`
- no LLM use

`keeper_profile_to_rows(profile_records: list[dict], remove_pii: bool = True) -> dict`

- converts extracted long-form Keeper profile records into row-oriented review payloads

`keeper_sanitize_profile_row(row: dict) -> dict`

- fail-closed sanitization gate before any row reaches `keeper_build_prompt`

## Audit Envelope

`LLMAuditEnvelope` contains `LLMAuditRecord` entries with:

- `flow_name`
- `tool_name`
- `timestamp`
- `actor_id`
- `provider`
- `model`
- `endpoint`
- `egress_mode`
- `sanitization_status`
- `sanitization_version`
- `policy_decision`
- `prompt_sha256`
- `response_sha256`
- `artifact_ids`
- `metadata`

This envelope is intended for outbound LLM audit logging. It must never contain raw unsanitized patient rows.
