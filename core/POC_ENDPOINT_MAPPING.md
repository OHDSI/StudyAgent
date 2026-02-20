# POC Endpoint -> Core Function Mapping

Purpose: capture the current proof-of-concept ACP endpoints and map them to pure, deterministic core function signatures. IO, model calls, and filesystem/network access stay outside core.

## Endpoint mappings

- `POST /health`
  - Pure core: `health_status() -> {"status": "ok"}`
  - Notes: trivial status check.

- `POST /actions/execute_llm`
  - Current inputs: `{artifactRef, actions[], write, overwrite, backup}`
  - Pure core: `execute_llm_actions(concept_set, actions) -> {plan, preview_changes, counts, ignored, updated_concept_set}`
  - Notes: wrapper resolves `artifactRef` + optional persistence.

- `POST /tools/propose_concept_set_diff`
  - Current inputs: `{conceptSetRef, studyIntent}`
  - Pure core: `propose_concept_set_diff(concept_set, study_intent, llm_result=None) -> {plan, findings, patches, actions, risk_notes}`
  - Notes: deterministic findings + optional merge of LLM output.

- `POST /tools/cohort_lint`
  - Current inputs: `{cohortRef}`
  - Pure core: `lint_cohort_design(cohort, llm_result=None) -> {plan, findings, patches, actions, risk_notes}`
  - Notes: deterministic checks (washout, inverted windows) + optional merge.

- `POST /actions/concept_set_edit`
  - Current inputs: `{artifactRef, ops[], write, backup, outputPath, overwrite}`
  - Pure core: `edit_concept_set(concept_set, ops) -> {plan, preview_changes, updated_concept_set, ops}`
  - Notes: wrapper handles `artifactRef` + optional persistence.

- `POST /tools/phenotype_recommendations`
  - Current inputs: `{protocolRef, cohortsCatalogRef, maxResults}`
  - Pure core: `recommend_phenotypes(protocol_text, catalog_rows, max_results, llm_result=None, preview_limits=...) -> {plan, phenotype_recommendations, mode, catalog_stats, invalid_ids_filtered}`
  - Notes: wrapper reads protocol + CSV catalog; core filters/validates IDs.

- `POST /tools/phenotype_improvements`
  - Current inputs: `{protocolRef, cohortRefs[], characterizationRefs[]}`
  - Pure core: `improve_phenotypes(protocol_text, cohorts, characterization_previews, llm_result=None, preview_limits=...) -> {plan, phenotype_improvements, code_suggestion, mode, invalid_targets_filtered}`
  - Notes: wrapper loads cohort JSONs + previews; core validates target IDs.

- `POST /assist/analyze`
  - Current inputs: `{caller, task, artifact, study_intent, preimage}`
  - Pure core: `assist_analyze_concept_set(task, artifact, study_intent, caller=None, llm_result=None) -> {plan, findings, patches, actions, risk_notes, prepared_mutations, artifact, preimage, mode}`
  - Notes: builds prepared WebAPI mutations when `caller == "WebAPI"`.

## Helper functions (core-appropriate)

- `canonicalize_concept_items(concept_set_or_expression) -> (items, src_items)`
- `apply_set_include_descendants(concept_set_or_expression, where, value=True) -> (updated, preview)`
- `summarize_cohort(cohort, ref=None, snippet_limit=...) -> dict`
- `filter_catalog_recs(recs, catalog_rows, max_results) -> list`
- `cohort_id_from_ref(ref) -> int|None`
- `sha256_json(obj) -> str`
- `truncate_text(text, limit) -> str`
