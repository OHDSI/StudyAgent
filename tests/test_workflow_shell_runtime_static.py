from _repo_paths import repo_path


RUNNER_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "workflow_script_runner.R")
STATE_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "workflow_project_state.R")
COHORT_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "strategus_cohort_methods_shell.R")
INCIDENCE_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "strategus_incidence_shell.R")


def test_dependency_check_treats_skipped_steps_as_satisfied() -> None:
    source = RUNNER_SOURCE.read_text(encoding="utf-8")
    assert 'dep_status %in% c("completed", "skipped")' in source


def test_project_state_supports_build_phase_status_finalization() -> None:
    source = STATE_SOURCE.read_text(encoding="utf-8")
    assert '.studyAgentSlashFinalizeBuildProjectState <- function(' in source
    assert 'completed_steps = character(0)' in source
    assert 'skipped_steps = character(0)' in source
    assert 'failed_steps = character(0)' in source
    assert 'runtime_state$current_step <- project_state$resume$current_step_id %||% NULL' in source


def _assert_shell_finalizes_build_phase_steps(source: str) -> None:
    assert 'build_completed_steps <- c("recommend_and_select")' in source
    assert 'build_skipped_steps <- character(0)' in source
    assert 'if (isTRUE(improvements_applied)) {' in source
    assert 'build_skipped_steps <- c(build_skipped_steps, "apply_improvements")' in source
    assert 'state$keeper_concept_set_status %||% "not_run"' in source
    assert 'state$keeper_case_review_status %||% "not_run"' in source
    assert '.studyAgentSlashFinalizeBuildProjectState(' in source


def test_cohort_method_shell_finalizes_build_phase_steps_before_run_mode() -> None:
    _assert_shell_finalizes_build_phase_steps(COHORT_SOURCE.read_text(encoding="utf-8"))


def test_incidence_shell_finalizes_build_phase_steps_before_run_mode() -> None:
    _assert_shell_finalizes_build_phase_steps(INCIDENCE_SOURCE.read_text(encoding="utf-8"))
