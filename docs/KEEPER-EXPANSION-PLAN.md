  Target Design

  Do not run the Keeper R package from the Strategus shells.

  Use the Keeper 2.0 subfolder only as a semantic reference for:

  - concept-set domain names
  - row field names
  - expected review workflow shape

  The actual R runtime path should be:

  1. keeper_concept_sets_generate
  2. user review/approval of concept sets
  3. keeper_profiles_generate
  4. row-by-row phenotype_validation_review
  5. /ohdsi available during concept-set generation and row-review steps

  Plan

  1. Complete the R ACP client surface.

  - Expand R/slashOhdsiAcpClient/R/flows.R:138 so acp_keeper_concept_sets_generate() matches the full ACP contract: vocab_search_provider, phoebe_provider, min_record_count, and the
    existing fields.
  - Add acp_keeper_profiles_generate(...).
  - Add acp_phenotype_validation_review(...).
  - Add matching runtime passthrough helpers in R/slashOhdsiStrategusAssistant/R/slash_ohdsi_runtime.R:1 so the workflow package stays on the public ACP seam.

  2. Add one shared R helper module for Keeper workflow orchestration.

  - Create a shared helper file in R/slashOhdsiStrategusAssistant/R/, not duplicated shell logic.
  - Responsibilities:
      - derive default phenotype labels from selected cohort names/statements
      - call the three ACP flows
      - persist raw concept-set responses, approved concept sets, generated rows, and per-row review results
      - implement row selection/review loops
      - print concise summaries and surface ACP errors clearly
  - This helper should be reused by both cohort-method and incidence shells.

  3. Wire Keeper stages into the interactive shells.

  - Insert an optional Keeper phase after cohort selection/improvements are finalized and before final script generation.
  - Recommended flow per selected role/cohort:
      - choose which roles to review
      - generate concept sets
      - accept/edit/rerun concept sets
      - generate Keeper rows
      - review rows one by one
  - Default behavior should probably be:
      - outcomes first
      - target/comparator optional
  - Use the existing stage names already reserved in R/slashOhdsiStrategusAssistant/R/workflow_stage_context.R:3:
      - keeper_concept_set_generation
      - keeper_case_review
  - Update R/slashOhdsiStrategusAssistant/R/workflow_dialogue_mapping.R:1 so /ohdsi has proper step labels for these stages.

  4. Keep /ohdsi safe during Keeper work.

  - /ohdsi during Keeper stages should send only workflow metadata, not patient row contents.
  - Good stage context for /ohdsi:
      - phenotype name
      - role
      - cohort id
      - concept-set artifact paths
      - row count
      - current row index
      - review status
  - Do not embed Keeper row payloads into workflow_context_dialogue. Row-specific adjudication should go only through phenotype_validation_review.

  5. Replace generated 04_keeper_review.R in both shells.

  - Remove library(Keeper), DatabaseConnector, and createKeeper(...) from the generated script path in both shells.
  - New 04_keeper_review.R should:
      - read selected cohort ids from cohort_id_map.json
      - read schema/table info from strategus-execution-settings.json
      - call ACP wrappers only
      - write JSON artifacts under keeper-case-review/
      - optionally write convenience CSV summaries for human scanning
  - It should not require databaseId, and it should no longer depend on strategus-db-details.json unless you deliberately keep that for unrelated reasons.

  6. Define the Keeper artifact layout explicitly.

  - Keep keeper-case-review/, but make it structured:
      - keeper-case-review/concept-sets-generated/
      - keeper-case-review/concept-sets-approved/
      - keeper-case-review/rows/
      - keeper-case-review/reviews/
  - Persist shell summary state in a new output artifact such as outputs/keeper_review_state.json, and echo the important paths in outputs/study_agent_state.json.
  - In cohort methods, keep these separate from the existing concept-sets/ directory, which is already being used for negative-control/covariate placeholder material.

  7. Land this in low-risk slices.

  - Slice 1:
      - ACP wrappers
      - shared Keeper helper
      - direct demo scripts for the three flows
  - Slice 2:
      - replace generated 04_keeper_review.R in both shells
      - add artifact/state persistence
  - Slice 3:
      - inline interactive Keeper phase in both shells
      - /ohdsi Keeper-stage wiring
      - resume/cache behavior

  Testing Plan

  1. R wrapper tests.

  - Add source-level tests for new wrappers in R/slashOhdsiAcpClient/R/flows.R.
  - Verify request-field coverage for all three Keeper flows.

  2. Generated-script regression tests.

  - Extend tests/test_cohort_methods_generated_scripts.py:1.
  - Add an incidence counterpart if needed.
  - Assert:
      - no library(Keeper)
      - no createKeeper(
      - no DatabaseConnector
      - presence of ACP wrapper calls and JSON artifact writes

  3. Shell workflow/state tests.

  - Add shell regression tests for:
      - Keeper stage insertion
      - study_agent_state.json Keeper fields
      - /ohdsi stage mapping during Keeper concept-set generation and case review
      - resume using approved concept sets / saved rows

  4. ACP-side contract tests.

  - Reuse existing ACP flow coverage in tests/test_acp_server.py:430.
  - Add only what is missing on the R integration boundary; the server flows themselves already have basic coverage.

  5. Manual demos.

  - Add:
      - scripts/demo_keeper_concept_sets_generate.R
      - scripts/demo_keeper_profiles_generate.R
      - scripts/demo_keeper_review_row.R
      - optional end-to-end scripts/demo_keeper_review_pipeline.R
  - Reuse scripts/test_phenotype_validation_review.R:1 as the seed for the row-review demo.

  6. Live manual checklist.

  - Run 03_generate_cohorts.R.
  - Run new 04_keeper_review.R.
  - Confirm:
      - concept-set generation artifacts exist
      - approved concept sets are consumed
      - row files are generated
      - individual row reviews save correctly
      - /ohdsi works in Keeper stages
      - ACP failure modes are readable:
          - omop_db_engine_unconfigured
          - phi_detected
          - zero rows returned
          - row index out of range

  Recommended Decisions Before Coding

  - Default Keeper review scope: outcomes only by default, target/comparator optional.
  - Enforce remove_pii = TRUE for shell-driven review paths.
  - Keep 04_keeper_review.R as one script to avoid renumbering downstream docs/scripts.
  - Treat the vendored Keeper/ folder as reference-only, not runtime.

  Main Risk

  The only real architectural trap is letting generic /ohdsi dialogue see row contents. Avoid that, and the migration is mostly plumbing plus workflow/state work rather than a hard
  redesign.

