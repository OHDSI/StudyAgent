
from _repo_paths import repo_path
import pytest


FLOWS_SOURCE = repo_path("R", "slashOhdsiAcpClient", "R", "flows.R")
DEMO_SOURCE = repo_path("scripts", "demo_ohdsi_dialogue.R")
DIALOGUE_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "workflow_dialogue.R")
INCIDENCE_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "strategus_incidence_shell.R")
COHORT_METHODS_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "strategus_cohort_methods_shell.R")

pytestmark = pytest.mark.r_shell

def test_r_workflow_context_dialogue_wrapper_flattens_stage_context() -> None:
    source = FLOWS_SOURCE.read_text(encoding="utf-8")

    assert ".flatten_workflow_context_dialogue_payload <- function(stage_context, message)" in source
    assert 'user_prompt = trimws(as.character(message))' in source
    assert 'study_intent = trimws(as.character(stage_context$user_goal %||% ""))' in source
    assert 'workflow_type = trimws(as.character(stage_context$workflow_type %||% ""))' in source
    assert 'current_step = trimws(as.character(stage_context$current_step %||% ""))' in source
    assert 'current_role = trimws(as.character(current_role))' in source
    assert 'current_context = .normalize_acp_body(current_context)' in source
    assert "workflow_stage_context =" not in source


def test_ohdsi_demo_script_exercises_shell_equivalent_handler() -> None:
    source = DEMO_SOURCE.read_text(encoding="utf-8")

    assert 'slashOhdsiStrategusAssistant::new_workflow_dialogue_session(' in source
    assert 'slashOhdsiAcpClient::acp_workflow_context_dialogue(' in source
    assert 'handled <- dialogue$handle_command(paste("/ohdsi", question))' in source
    assert 'workflow = "incidence"' in source
    assert 'workflow = "cohort_methods"' in source

def test_workflow_dialogue_reader_supports_back_navigation() -> None:
    source = DIALOGUE_SOURCE.read_text(encoding="utf-8")

    assert 'new_workflow_navigation_signal <- function(action)' in source
    assert 'workflow_dialogue_prompt_width <- function() {' in source
    assert 'wrap_workflow_dialogue_prompt <- function(prompt) {' in source
    assert 'readline_with_dialogue <- function(prompt, allow_back = FALSE)' in source
    assert 'entered <- readline(wrap_workflow_dialogue_prompt(prompt))' in source
    assert 'if (isTRUE(allow_back) && identical(trimmed, "/back")) {' in source


def test_incidence_shell_wires_back_at_major_stage_boundaries() -> None:
    source = INCIDENCE_SOURCE.read_text(encoding="utf-8")

    assert 'readline_with_navigation <- function(prompt) readline_with_dialogue(prompt, allow_back = TRUE)' in source
    assert 'prompt_yesno_navigation <- function(prompt, default = TRUE)' in source
    assert 'Press Enter to continue to target cohort selection, or type /back: ' in source
    assert 'Press Enter to continue to outcome cohort selection, or type /back: ' in source
    assert 'run_keeper_review_now <- prompt_yesno_navigation(' in source
    assert 'Use /ohdsi for contextual guidance. Type /back at supported stage boundaries to return to the previous step.' in source

def test_cohort_methods_analysis_label_limit_is_100_chars() -> None:
    source = COHORT_METHODS_SOURCE.read_text(encoding="utf-8")

    assert 'analysis_label_max_chars <- 100L' in source


    assert 'if (isTRUE(resume) && file.exists(manual_inputs_path)) {' in source
    assert 'cached_inputs <- tryCatch(read_json(manual_inputs_path), error = function(e) {' in source
    assert 'resolve_single_selection <- function(selected_ids,' in source

def test_cohort_methods_shell_wires_back_at_major_stage_boundaries() -> None:
    source = COHORT_METHODS_SOURCE.read_text(encoding="utf-8")

    assert 'readline_with_navigation <- function(prompt) readline_with_dialogue(prompt, allow_back = TRUE)' in source
    assert 'prompt_yesno_navigation <- function(prompt, default = TRUE)' in source
    assert 'Press Enter to continue to target cohort selection, or type /back: ' in source
    assert 'Press Enter to continue to comparator cohort selection, or type /back: ' in source
    assert 'Press Enter to continue to outcome cohort selection, or type /back: ' in source
    assert 'Press Enter to continue to study configuration, or type /back: ' in source
    assert 'Press Enter to continue to Keeper review options, or type /back: ' in source
    assert 'Use /ohdsi for contextual guidance. Type /back at supported stage boundaries to return to the previous step.' in source

