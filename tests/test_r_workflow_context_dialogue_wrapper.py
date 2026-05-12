from pathlib import Path

from _repo_paths import repo_path


FLOWS_SOURCE = repo_path("R", "slashOhdsiAcpClient", "R", "flows.R")
DEMO_SOURCE = repo_path("scripts", "demo_ohdsi_dialogue.R")

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