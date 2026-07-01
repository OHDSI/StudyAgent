from _repo_paths import repo_path


RUNNER_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "workflow_script_runner.R")
STATE_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "workflow_project_state.R")
STEP_STATE_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "workflow_step_state.R")
COHORT_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "strategus_cohort_methods_shell.R")
INCIDENCE_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "strategus_incidence_shell.R")
DIALOGUE_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "workflow_dialogue.R")
EXPLORATION_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "workflow_exploration_registry.R")


def test_dependency_check_treats_skipped_steps_as_satisfied() -> None:
    source = RUNNER_SOURCE.read_text(encoding="utf-8")
    assert 'dep_status %in% c("completed", "skipped")' in source


def test_runner_marks_build_only_steps_as_non_runnable() -> None:
    source = RUNNER_SOURCE.read_text(encoding="utf-8")
    assert '.studyAgentSlashWorkflowBuildOnlyStepIds <- function() {' in source
    assert 'build-only; use revise' in source
    assert "completed interactively during build mode and cannot be rerun from the execution menu" in source


def test_runner_reconciles_derived_state_and_persists_step_state() -> None:
    source = RUNNER_SOURCE.read_text(encoding="utf-8")
    assert '.studyAgentSlashReconcileProjectState(base_dir, write = TRUE)' in source
    assert '.studyAgentSlashWriteStepState(' in source
    assert 'status = "running"' in source
    assert 'status = result$status' in source


def test_project_state_supports_build_phase_status_finalization() -> None:
    source = STATE_SOURCE.read_text(encoding="utf-8")
    assert '.studyAgentSlashFinalizeBuildProjectState <- function(' in source
    assert 'completed_steps = character(0)' in source
    assert 'skipped_steps = character(0)' in source
    assert 'failed_steps = character(0)' in source
    assert 'runtime_state$current_step <- project_state$resume$current_step_id %||% NULL' in source


def test_step_state_module_defines_backup_restore_reset_primitives() -> None:
    source = STEP_STATE_SOURCE.read_text(encoding="utf-8")
    assert '.studyAgentSlashStepStateDir <- function(base_dir) {' in source
    assert '.studyAgentSlashWriteStepState <- function(' in source
    assert '.studyAgentSlashBackupWorkflowState <- function(' in source
    assert '.studyAgentSlashRestoreWorkflowState <- function(' in source
    assert '.studyAgentSlashResolveDerivedWorkflowStatuses <- function(' in source
    assert '.studyAgentSlashReconcileProjectState <- function(' in source
    assert '.studyAgentSlashResetWorkflowStepState <- function(' in source
    assert '"stale"' in source
    assert '"blocked"' in source


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


def _assert_execution_menu_help_and_exit_guards(source: str) -> None:
    assert 'print_execution_help <- function() {' in source
    assert 'current_study_intent <- function() {' in source
    assert 'project_state$study_context' in source
    assert '.studyAgentSlashFormatWorkflowStepChoices(base_dir)' in source
    assert '.studyAgentSlashResolveWorkflowStepId(base_dir, step_ref)' in source
    assert 'confirm_execution_menu_exit <- function() {' in source
    assert '.studyAgentSlashWorkflowIsComplete(base_dir)' in source
    assert 'Exit execution menu and return to the R prompt?' in source
    assert 'h=help' in source
    assert 'rev or revise' in source
    assert 'rev or revise' in source
    assert 'startsWith(lowered, "rev " )' not in source
    assert '/ohdsi <question>' in source
    assert 'q or quit' in source
    assert 'Step number or step id to inspect (? for choices):' in source
    assert 'Step number or step id to inspect in viewer (? for choices):' in source
    assert 'Step %s could not be run: %s' in source
    assert 'Leave execution mode and return to build mode to revise' in source
    assert 'Revision cache posture' in source
    assert 'Switch to temporary revision cache mode for this pass?' in source


def test_cohort_method_shell_execution_menu_has_help_and_exit_confirmation() -> None:
    _assert_execution_menu_help_and_exit_guards(COHORT_SOURCE.read_text(encoding="utf-8"))


def test_incidence_shell_execution_menu_has_help_and_exit_confirmation() -> None:
    _assert_execution_menu_help_and_exit_guards(INCIDENCE_SOURCE.read_text(encoding="utf-8"))


def test_cohort_method_shell_exposes_backup_reset_restore_menu_surface() -> None:
    source = COHORT_SOURCE.read_text(encoding="utf-8")
    assert 'backup' in source
    assert 'backups' in source
    assert 'reset <step>' in source
    assert 'restore <snapshot-id>' in source
    assert '.studyAgentSlashBackupWorkflowState(base_dir, label = "manual")' in source
    assert '.studyAgentSlashListWorkflowBackups(base_dir)' in source
    assert '.studyAgentSlashRestoreWorkflowState(base_dir, snapshot_id = snapshot_id, restore_artifacts = TRUE, backup_current = TRUE)' in source
    assert '.studyAgentSlashResetWorkflowStepState(base_dir, step_id = step_id, cascade = TRUE, backup = TRUE, delete_outputs = TRUE)' in source


def test_project_state_builds_enriched_execution_dialogue_context() -> None:
    source = STATE_SOURCE.read_text(encoding="utf-8")
    assert '.studyAgentSlashBuildExecutionDialogueContext <- function(' in source
    assert 'target_statement = study_context$target_statement %||% NULL' in source
    assert 'comparator_statement = study_context$comparator_statement %||% NULL' in source
    assert 'selected_target_ids = selected_target_ids' in source
    assert 'selected_comparator_ids = selected_comparator_ids' in source
    assert 'selected_outcome_ids = selected_outcome_ids' in source
    assert 'analysis_settings_path = study_context$cm_analysis_json_path %||% study_context$analysis_settings_path %||% study_context$time_at_risk_settings_path %||% NULL' in source
    assert 'artifact_summary <- .studyAgentSlashCompactExecutionArtifactSummary(' in source
    assert 'requestable_artifact_ids = requestable_artifact_ids' in source
    assert 'artifact_request_policy = compact_workflow_dialogue_context(list(' in source


def test_shells_use_shared_enriched_execution_dialogue_context() -> None:
    cohort_source = COHORT_SOURCE.read_text(encoding="utf-8")
    incidence_source = INCIDENCE_SOURCE.read_text(encoding="utf-8")
    expected = '.studyAgentSlashBuildExecutionDialogueContext('
    assert expected in cohort_source
    assert expected in incidence_source


def _assert_exploration_menu_surface(source: str) -> None:
    assert 'artifacts' in source
    assert 'x=explore[_v]' in source
    assert 'inspect' in source
    assert 'Execution command [Enter=finish, x=explore[_v], s=status, h=help/show commands, /ohdsi=AI assistance]:' in source
    assert 'Choose h, s, art, x[_v],' in source
    assert 'number: run the numbered exploration command shown by x' in source
    assert 'x <command-id> or explore <command-id>: run an approved exploration command' in source
    assert 'x_v <command-id> or explore_v <command-id>: run an approved exploration command and try to open tabular output in a viewer' in source
    assert 'display <- if (isTRUE(viewer)) NULL else execution_table_display' in source
    assert 'if (grepl("^[0-9]+$", lowered)) {' in source
    assert 'print_artifact_inventory <- function(viewer = FALSE) {' in source
    assert 'print_exploration_commands <- function(viewer = FALSE) {' in source
    assert 'run_exploration_command <- function(command_ref, viewer = FALSE) {' in source
    assert '.studyAgentSlashRunExplorationCommand(base_dir, command_id = command_id)' in source
    assert 'inspect_execution_outputs <- function(step_id, viewer = FALSE) {' in source
    assert 'artifacts known to the current workflow project' in source


def test_cohort_method_shell_exposes_exploration_menu_surface() -> None:
    _assert_exploration_menu_surface(COHORT_SOURCE.read_text(encoding="utf-8"))


def test_incidence_shell_exposes_exploration_menu_surface() -> None:
    _assert_exploration_menu_surface(INCIDENCE_SOURCE.read_text(encoding="utf-8"))


def test_cohort_method_shell_revision_mode_can_force_stage_reselection() -> None:
    source = COHORT_SOURCE.read_text(encoding="utf-8")
    assert 'revision_state <- new.env(parent = emptyenv())' in source
    assert 'should_force_role_reselection <- function(role_key) {' in source
    assert 'Revision will force reopening of:' in source
    assert 'should_force_role_reselection("comparator")' in source
    assert 'should_force_role_reselection("target")' in source
    assert 'should_force_role_reselection("outcome")' in source


def test_dialogue_session_supports_reusable_ask_method() -> None:
    source = DIALOGUE_SOURCE.read_text(encoding="utf-8")
    assert 'ask_dialogue <- function(question, render = TRUE) {' in source
    assert 'ask = ask_dialogue' in source


def test_exploration_registry_defines_first_slice_commands() -> None:
    source = EXPLORATION_SOURCE.read_text(encoding="utf-8")
    assert '.studyAgentSlashBuildArtifactRegistry <- function(base_dir) {' in source
    assert '.studyAgentSlashResolveArtifactPath <- function(path, base_dir) {' in source
    assert '.studyAgentSlashRunExplorationCommand <- function(base_dir, command_id) {' in source
    assert '.studyAgentSlashSupportsDataViewer <- function() {' in source
    assert '.studyAgentSlashOpenTableViewer <- function(data, title = "Study Agent") {' in source
    assert '.studyAgentSlashPrepareViewerTable <- function(data, preferred_order = NULL) {' in source
    assert '.studyAgentSlashRenderExplorationResult <- function(result, viewer = FALSE, display = NULL) {' in source
    assert 'command_id = "artifact_inventory"' in source
    assert 'command_id = "cohort_counts_summary"' in source
    assert 'command_id = "diagnostics_inventory"' in source
    assert 'command_id = "diagnostics_run_settings"' in source
    assert 'command_id = "diagnostics_orphan_concepts_summary"' in source
    assert 'command_id = "diagnostics_source_concepts_summary"' in source
    assert 'command_id = "diagnostics_visit_context_summary"' in source
    assert 'command_id = "keeper_case_review_metrics"' in source
    assert 'command_id = "inclusion_rules_preview"' in source
    assert 'command_id = "cohort_stats_preview"' in source


def test_execution_dialogue_context_includes_exploration_fields() -> None:
    source = STATE_SOURCE.read_text(encoding="utf-8")
    assert 'artifact_registry <- .studyAgentSlashBuildArtifactRegistry(base_dir)' in source
    assert '.studyAgentSlashCompactExecutionArtifactSummary(' in source
    assert '.studyAgentSlashCompactExplorationCommandSummary(' in source
    assert 'diagnostics_summary <- if (exists(".studyAgentSlashCompactDiagnosticsDialogueSummary", mode = "function")) {' in source
    assert 'diagnostics_summary = diagnostics_summary' in source
    assert 'artifact_summary = artifact_summary' in source
    assert 'available_exploration_commands = available_exploration_commands' in source
