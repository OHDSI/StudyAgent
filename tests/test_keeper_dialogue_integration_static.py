from pathlib import Path

from _repo_paths import repo_path


MAPPING_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "workflow_dialogue_mapping.R")
HELPER_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "keeper_review_workflow.R")
COHORT_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "strategus_cohort_methods_shell.R")
INCIDENCE_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "strategus_incidence_shell.R")

def test_keeper_stage_labels_exist_for_both_shells() -> None:
    source = MAPPING_SOURCE.read_text(encoding="utf-8")

    assert 'keeper_concept_set_generation = if (nzchar(role_label)) paste0(role_label, "Keeper concept-set generation") else "Keeper concept-set generation"' in source
    assert 'keeper_case_review = if (nzchar(role_label)) paste0(role_label, "Keeper case review") else "Keeper case review"' in source


def test_keeper_helper_emits_metadata_only_stage_callbacks() -> None:
    source = HELPER_SOURCE.read_text(encoding="utf-8")

    assert "acp_timeout_seconds = as.numeric(Sys.getenv(\"ACP_TIMEOUT\", \"300\"))" in source
    assert "previous_acp_timeout <- Sys.getenv(\"ACP_TIMEOUT\", unset = NA_character_)" in source
    assert "Sys.setenv(ACP_TIMEOUT = as.character(acp_timeout_seconds))" in source
    assert "acp_timeout_seconds = as.numeric(acp_timeout_seconds)" in source
    assert "stage_callback = NULL" in source
    assert "overwrite_approved_concept_sets = FALSE" in source
    assert "resume_reviews = TRUE" in source
    assert "review_row_selection = NULL" in source
    assert "parse_row_selection <- function(selection, total_rows, default_limit)" in source
    assert 'tolower(selection_text) %in% c("all", "*")' in source
    assert 'selected_row_indices <- parse_row_selection(review_row_selection, length(row_records), review_row_limit)' in source
    assert 'pending_row_indices <- selected_row_indices[!selected_row_indices %in% reviewed_indices]' in source
    assert 'approved_source <- "overwritten_from_generated"' in source
    assert 'approved_concept_sets_source = approved_source' in source
    assert 'selected_row_indices = as.list(selected_row_indices)' in source
    assert 'pending_row_indices = as.list(pending_row_indices)' in source
    assert "keeper_row = keeper_row" in source
    assert "emit_stage(" in source


def _assert_shell_keeper_controls(source: str) -> None:
    assert 'keeper_acp_timeout_seconds <- as.numeric(Sys.getenv("ACP_TIMEOUT", "300"))' in source
    assert 'prompt_yesno("Run ACP-based Keeper review now?", default = FALSE)' in source
    assert 'readline_with_dialogue("Keeper review roles [outcome]: ")' in source
    assert 'prompt_yesno("Reuse existing Keeper generated artifacts?", default = TRUE)' in source
    assert 'prompt_yesno("Replace approved concept sets with current generated output?", default = FALSE)' in source
    assert 'prompt_yesno("Resume existing Keeper row reviews?", default = TRUE)' in source
    assert 'readline_with_dialogue("Keeper row selection [default first N or e.g. 1-3,5]: ")' in source
    assert 'runKeeperReviewWorkflow(' in source
    assert 'acp_timeout_seconds = keeper_acp_timeout_seconds' in source
    assert 'overwrite_approved_concept_sets = keeper_overwrite_approved_concept_sets' in source
    assert 'reuse_generated_concept_sets = keeper_reuse_generated_artifacts' in source
    assert 'reuse_rows = keeper_reuse_generated_artifacts' in source
    assert 'resume_reviews = keeper_resume_reviews' in source
    assert 'review_row_selection = keeper_review_row_selection' in source
    assert 'state$keeper_acp_timeout_seconds <- as.numeric(keeper_acp_timeout_seconds)' in source
    assert 'state$keeper_reuse_generated_artifacts <- isTRUE(keeper_reuse_generated_artifacts)' in source
    assert 'state$keeper_overwrite_approved_concept_sets <- isTRUE(keeper_overwrite_approved_concept_sets)' in source
    assert 'state$keeper_resume_reviews <- isTRUE(keeper_resume_reviews)' in source
    assert 'state$keeper_review_row_selection <- keeper_review_row_selection' in source


def test_cohort_method_shell_offers_inline_keeper_phase() -> None:
    source = COHORT_SOURCE.read_text(encoding="utf-8")
    _assert_shell_keeper_controls(source)
    assert 'intent_path = cohort_methods_intent_split_path' in source
    assert 'stage_callback = stage_callback' in source
    assert 'set_dialogue_context("workflow_summary", context = list(study_intent = studyIntent, keeper_review_state_path = keeper_review_state_path))' in source


def test_incidence_shell_offers_inline_keeper_phase() -> None:
    source = INCIDENCE_SOURCE.read_text(encoding="utf-8")
    _assert_shell_keeper_controls(source)
    assert 'intent_path = intent_split_path' in source
    assert 'stage_callback = stage_callback' in source
    assert 'set_dialogue_context("workflow_summary", context = list(study_intent = studyIntent, keeper_review_state_path = keeper_review_state_path))' in source