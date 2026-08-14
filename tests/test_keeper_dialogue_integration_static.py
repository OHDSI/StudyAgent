from _repo_paths import repo_path
import pytest


MAPPING_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "workflow_dialogue_mapping.R")
HELPER_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "keeper_review_workflow.R")
COHORT_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "strategus_cohort_methods_shell.R")
INCIDENCE_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "strategus_incidence_shell.R")

pytestmark = pytest.mark.r_shell


def test_keeper_stage_labels_exist_for_both_shells() -> None:
    source = MAPPING_SOURCE.read_text(encoding="utf-8")

    assert 'keeper_concept_set_generation = if (nzchar(role_label)) paste0(role_label, "Keeper concept-set generation") else "Keeper concept-set generation"' in source
    assert 'keeper_case_review = if (nzchar(role_label)) paste0(role_label, "Keeper case review") else "Keeper case review"' in source
    assert 'keeper_concept_set_generation_before = "keeper_concept_set_generation"' in source
    assert 'keeper_concept_set_generation_after = "keeper_concept_set_generation"' in source
    assert 'keeper_case_review_before = "keeper_case_review"' in source
    assert 'keeper_case_review_after = "keeper_case_review"' in source


def test_keeper_helper_exports_split_workflows_and_stage_callbacks() -> None:
    source = HELPER_SOURCE.read_text(encoding="utf-8")

    assert 'runKeeperConceptSetWorkflow <- function(' in source
    assert 'runKeeperCaseReviewWorkflow <- function(' in source
    assert 'keeper_concept_set_state.json' in source
    assert 'keeper_case_review_state.json' in source
    assert 'remove_pii = TRUE' in source
    assert 'resume_reviews = TRUE' in source
    assert 'review_row_selection = NULL' in source
    assert '.studyAgentSlashParseRowSelection <- function(selection, total_rows, default_limit)' in source
    assert '.studyAgentSlashEmitKeeperStage(' in source
    assert 'keeper_concept_set_generation_before' in source
    assert 'keeper_concept_set_generation_after' in source
    assert 'keeper_case_review_before' in source
    assert 'keeper_case_review_after' in source
    assert 'approved_source <- "overwritten_from_generated"' in source
    assert 'pending_row_indices <- selected_row_indices[!selected_row_indices %in% reviewed_indices]' in source
    assert 'error_count = length(workflow_errors)' in source


def _assert_shell_keeper_controls(source: str) -> None:
    assert 'keeper_acp_timeout_seconds <- as.numeric(Sys.getenv("ACP_TIMEOUT", "300"))' in source
    assert 'Keeper review roles [outcome]: ' in source
    assert (
        'prompt_yesno("Reuse existing Keeper generated artifacts?", default = TRUE)' in source
        or 'prompt_yesno_strict("Reuse existing Keeper generated artifacts?", default = TRUE)' in source
        or 'prompt_yesno_navigation("Reuse existing Keeper generated artifacts?", default = TRUE)' in source
    )
    assert (
        'prompt_yesno("Replace approved concept sets with current generated output?", default = FALSE)' in source
        or 'prompt_yesno_strict("Replace approved concept sets with current generated output?", default = FALSE)' in source
        or 'prompt_yesno_navigation("Replace approved concept sets with current generated output?", default = FALSE)' in source
    )
    assert 'runKeeperConceptSetWorkflow(' in source
    assert 'runKeeperCaseReviewWorkflow(' in source
    assert 'acp_timeout_seconds = keeper_acp_timeout_seconds' in source
    assert 'overwrite_approved_concept_sets = keeper_overwrite_approved_concept_sets' in source
    assert 'reuse_generated_concept_sets = keeper_reuse_generated_artifacts' in source
    assert 'reuse_rows = keeper_reuse_generated_artifacts' in source
    assert 'resume_reviews = keeper_resume_reviews' in source
    assert 'review_row_selection = keeper_review_row_selection' in source
    assert 'candidate_limit = keeper_candidate_limit' in source
    assert 'sample_size = keeper_sample_size' in source
    assert 'review_row_limit = keeper_review_row_limit' in source
    assert 'stage_gate = keeper_stage_gate' in source
    assert 'keeper_concept_set_generation_before' in source
    assert 'keeper_concept_set_generation_after' in source
    assert 'keeper_case_review_before' in source
    assert 'keeper_case_review_after' in source
    assert 'state$keeper_acp_timeout_seconds <- as.numeric(keeper_acp_timeout_seconds)' in source
    assert 'state$keeper_candidate_limit <- as.integer(keeper_candidate_limit)' in source
    assert 'state$keeper_sample_size <- as.integer(keeper_sample_size)' in source
    assert 'state$keeper_review_row_limit <- as.integer(keeper_review_row_limit)' in source
    assert 'state$keeper_reuse_generated_artifacts <- isTRUE(keeper_reuse_generated_artifacts)' in source
    assert 'state$keeper_overwrite_approved_concept_sets <- isTRUE(keeper_overwrite_approved_concept_sets)' in source
    assert 'state$keeper_resume_reviews <- isTRUE(keeper_resume_reviews)' in source
    assert 'state$keeper_review_row_selection <- keeper_review_row_selection' in source
    assert 'state$keeper_concept_set_status <-' in source
    assert 'state$keeper_case_review_status <-' in source


def test_cohort_method_shell_offers_inline_keeper_phase() -> None:
    source = COHORT_SOURCE.read_text(encoding="utf-8")
    _assert_shell_keeper_controls(source)
    assert 'intent_path = cohort_methods_intent_split_path' in source
    assert 'stage_callback = stage_callback' in source
    assert 'keeper_concept_set_state_path = keeper_concept_set_state_path' in source
    assert 'keeper_case_review_state_path = keeper_case_review_state_path' in source


def test_incidence_shell_offers_inline_keeper_phase() -> None:
    source = INCIDENCE_SOURCE.read_text(encoding="utf-8")
    _assert_shell_keeper_controls(source)
    assert 'intent_path = intent_split_path' in source
    assert 'stage_callback = stage_callback' in source
    assert 'keeper_concept_set_state_path = keeper_concept_set_state_path' in source
    assert 'keeper_case_review_state_path = keeper_case_review_state_path' in source
