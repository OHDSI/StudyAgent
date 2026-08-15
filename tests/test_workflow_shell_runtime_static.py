from _repo_paths import repo_path
import pytest


RUNNER_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "workflow_script_runner.R")
PLAN_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "workflow_execution_plan.R")
STATE_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "workflow_project_state.R")
STEP_STATE_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "workflow_step_state.R")
COHORT_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "strategus_cohort_methods_shell.R")
INCIDENCE_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "strategus_incidence_shell.R")
DIALOGUE_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "workflow_dialogue.R")
MAPPING_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "workflow_dialogue_mapping.R")
EXPLORATION_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "workflow_exploration_registry.R")

pytestmark = pytest.mark.r_shell


def test_dependency_check_treats_skipped_steps_as_satisfied() -> None:
    source = RUNNER_SOURCE.read_text(encoding="utf-8")
    assert '.studyAgentSlashWorkflowTerminalStatuses <- function() {' in source
    assert 'dep_status %in% .studyAgentSlashWorkflowTerminalStatuses()' in source
    assert '"completed_with_failures"' in source


def test_runner_marks_build_only_steps_as_non_runnable() -> None:
    source = RUNNER_SOURCE.read_text(encoding="utf-8")
    assert '.studyAgentSlashWorkflowBuildOnlyStepIds <- function() {' in source
    assert '.studyAgentSlashWorkflowSkippableStepIds <- function() {' in source
    assert '.studyAgentSlashWorkflowStepIsSkippable <- function(step) {' in source
    assert 'build-only; use revise' in source
    assert "completed interactively during build mode and cannot be rerun from the execution menu" in source


def test_runner_reconciles_derived_state_and_persists_step_state() -> None:
    source = RUNNER_SOURCE.read_text(encoding="utf-8")
    assert '.studyAgentSlashReconcileProjectState(base_dir, write = TRUE)' in source
    assert '.studyAgentSlashWriteStepState(' in source
    assert 'status = "running"' in source
    assert 'status = result$status' in source
    assert '.studyAgentSlashSkipWorkflowStep <- function(base_dir,' in source
    assert 'status = "skipped"' in source
    assert 'skip_reason = as.character(reason %||% "user_skipped")' in source
    assert '.studyAgentSlashResolvePostRunStepResult <- function(base_dir, step_id, default_status, default_error = NULL) {' in source
    assert '.studyAgentSlashPersistStrategusExecutionRoots <- function(base_dir, project_state, summary) {' in source
    assert 'source = "strategus_execute_summary"' in source
    assert 'status = "completed_with_failures"' in source


def test_runner_uses_safe_condition_message_fallback() -> None:
    source = RUNNER_SOURCE.read_text(encoding="utf-8")
    assert '.studyAgentSlashSafeConditionMessage <- function(condition) {' in source
    assert 'conditionMessage(condition)' in source
    assert 'condition$message %||% ""' in source
    assert 'original condition message could not be rendered cleanly' in source
    assert 'error = .studyAgentSlashSafeConditionMessage(e)' in source


def test_execution_plan_allows_optional_review_steps_to_be_skipped_before_specs() -> None:
    source = PLAN_SOURCE.read_text(encoding="utf-8")
    assert 'step_id = "generate_cohorts"' in source
    assert 'depends_on = "recommend_and_select"' in source
    assert 'step_id = "diagnostics"' in source
    assert 'depends_on = "generate_cohorts"' in source
    assert 'step_id = "incidence_spec"' in source
    assert 'step_id = "cm_spec"' in source
    assert 'produces_artifacts = c("outputs/cohort_roles.json", "outputs/cohort_id_map.json")' in source


def test_project_state_supports_build_phase_status_finalization() -> None:
    source = STATE_SOURCE.read_text(encoding="utf-8")
    assert '.studyAgentSlashFinalizeBuildProjectState <- function(' in source
    assert '.studyAgentSlashConfiguredExecutionRoots <- function(' in source
    assert '.studyAgentSlashPersistExecutionRoots <- function(' in source
    assert 'completed_steps = character(0)' in source
    assert 'skipped_steps = character(0)' in source
    assert 'failed_steps = character(0)' in source
    assert 'runtime_state$current_step <- project_state$resume$current_step_id %||% NULL' in source
    assert 'execution_status_detail = strategus_summary$overall_status %||% NULL' in source
    assert 'failed_module_names = failed_module_names' in source
    assert 'module_failure_count = length(failed_module_names)' in source


def test_step_state_module_defines_backup_restore_reset_primitives() -> None:
    source = STEP_STATE_SOURCE.read_text(encoding="utf-8")
    assert '.studyAgentSlashStepStateDir <- function(base_dir) {' in source
    assert '.studyAgentSlashWriteStepState <- function(' in source
    assert '.studyAgentSlashBackupWorkflowState <- function(' in source
    assert '.studyAgentSlashRestoreWorkflowState <- function(' in source
    assert '.studyAgentSlashResolveDerivedWorkflowStatuses <- function(' in source
    assert '.studyAgentSlashReconcileProjectState <- function(' in source
    assert '.studyAgentSlashResetWorkflowStepState <- function(' in source
    assert 'file.exists(legacy_path)' in source
    assert '"stale"' in source
    assert '"blocked"' in source
    assert 'derived_status %in% c("completed", "ok", "completed_with_failures")' in source
    assert '"analysis-settings/strategus_execute_result.rds"' in source
    assert '"analysis-settings/strategus_execute_summary.json"' in source


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


def test_shells_prompt_to_confirm_execution_roots_on_resume() -> None:
    cohort_source = COHORT_SOURCE.read_text(encoding="utf-8")
    incidence_source = INCIDENCE_SOURCE.read_text(encoding="utf-8")
    for source in (cohort_source, incidence_source):
        assert 'confirm_resume_execution_roots <- function() {' in source
        assert 'Use these execution roots for resumed artifact discovery?' in source
        assert 'Results root [' in source
        assert 'Work root [' in source
        assert 'Use full paths here if the configured roots are ambiguous.' in source
        assert '.studyAgentSlashPersistExecutionRoots(' in source


def test_cohort_method_shell_exposes_backup_reset_restore_menu_surface() -> None:
    source = COHORT_SOURCE.read_text(encoding="utf-8")
    assert 'backup' in source
    assert 'backups' in source
    assert 'reset <step>' in source
    assert 'skip <step>' in source
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
    assert 'skipped_steps = skipped_step_summaries' in source
    assert 'skip_reason = summary$skip_reason %||% NULL' in source
    assert 'requestable_artifact_ids = requestable_artifact_ids' in source
    assert 'artifact_request_policy = compact_workflow_dialogue_context(list(' in source


def test_shells_use_shared_enriched_execution_dialogue_context() -> None:
    cohort_source = COHORT_SOURCE.read_text(encoding="utf-8")
    incidence_source = INCIDENCE_SOURCE.read_text(encoding="utf-8")
    expected = '.studyAgentSlashBuildExecutionDialogueContext('
    assert expected in cohort_source
    assert expected in incidence_source


def test_dialogue_mapping_builds_nonblank_user_goal_fallbacks() -> None:
    source = MAPPING_SOURCE.read_text(encoding="utf-8")
    assert '.studyAgentSlashResolveDialogueUserGoal <- function(' in source
    assert '.studyAgentSlashCollapseDialogueText <- function(value) {' in source
    assert 'user_goal = .studyAgentSlashResolveDialogueUserGoal(' in source
    assert 'time_at_risk_configuration = "Configure time-at-risk definitions and strata settings for the incidence study."' in source
    assert 'analytic_settings_collection = "Configure analytic settings for the cohort-method study."' in source


def _assert_exploration_menu_surface(source: str) -> None:
    assert 'artifacts' in source
    assert 'x=explore[_v]' in source
    assert 'inspect' in source
    assert 'Execution command [h=help/show commands, Enter=finish, x=explore[_v], s=status, /ohdsi=AI assistance]:' in source
    assert 'Choose h, s, art, x[_v],' in source
    assert 'skip <step>' in source
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


def test_cohort_method_step_by_step_analytic_settings_supports_back_navigation() -> None:
    source = COHORT_SOURCE.read_text(encoding="utf-8")
    assert 'navigation_back_error <- function() {' in source
    assert 'abort_if_back_signal <- function(value) {' in source
    assert 'study_agent_navigation_back = function(e) {' in source
    assert 'new_workflow_navigation_signal("back")' in source
    assert 'prompt_yesno_navigation(prompt, default = default)' in source
    assert 'if (is_back_signal(step_by_step_result)) next' in source
    assert 'analytic_settings_back_requested <- FALSE' in source
    assert 'if (isTRUE(analytic_settings_back_requested)) next' in source


def test_cohort_method_shell_remap_and_keeper_setup_support_navigation() -> None:
    source = COHORT_SOURCE.read_text(encoding="utf-8")
    assert 'use_mapping <- prompt_yesno_navigation("Map cohort IDs to a new range (avoid collisions)?", default = isTRUE(remapCohortIds))' in source
    assert 'entered <- readline_with_navigation(sprintf("Cohort ID base [%s]: ", cohortIdBase))' in source
    assert 'run_keeper_review_now <- prompt_yesno_navigation("Run ACP-based Keeper review now?", default = FALSE)' in source
    assert 'keeper_config_confirmed <- FALSE' in source
    assert 'entered_roles <- readline_with_navigation("Keeper review roles [outcome]: ")' in source
    assert 'keeper_reuse_generated_artifacts <- prompt_yesno_navigation("Reuse existing Keeper generated artifacts?", default = TRUE)' in source
    assert 'entered_row_selection <- readline_with_navigation("Keeper row selection [default first N or e.g. 1-3,5]: ")' in source
    assert 'if (isTRUE(keeper_config_confirmed)) {' in source


def test_incidence_shell_reconciles_execution_state_before_explore_lookup() -> None:
    source = INCIDENCE_SOURCE.read_text(encoding="utf-8")
    assert 'refresh_execution_dialogue_context <- function(step_id = NULL) {' in source
    assert 'available_exploration_commands <- function() {' in source
    assert source.count('.studyAgentSlashReconcileProjectState(base_dir, write = TRUE)$project_state') >= 3


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


def test_workflow_dialogue_mapping_defines_build_help_lines() -> None:
    source = repo_path("R", "slashOhdsiStrategusAssistant", "R", "workflow_dialogue_mapping.R").read_text(encoding="utf-8")
    runtime = repo_path("R", "slashOhdsiStrategusAssistant", "R", "slash_ohdsi_runtime.R").read_text(encoding="utf-8")
    assert 'workflow_build_help_lines <- function(workflow_type, step, role = "", context = list()) {' in source
    assert '"Commands for this step:"' in source
    assert '"  - /ohdsi <question>: ask for workflow-aware OHDSI guidance"' in source
    assert '.studyAgentSlashWorkflowBuildHelpLines <- function(workflow_type, step, role = "", context = list()) {' in runtime


def test_exploration_registry_defines_first_slice_commands() -> None:
    source = EXPLORATION_SOURCE.read_text(encoding="utf-8")
    assert '.studyAgentSlashBuildArtifactRegistry <- function(base_dir) {' in source
    assert '.studyAgentSlashDiscoverStrategusExecutionRoots <- function(base_dir, project_state = NULL) {' in source
    assert '.studyAgentSlashResolveArtifactPath <- function(path, base_dir) {' in source
    assert '.studyAgentSlashRunExplorationCommand <- function(base_dir, command_id) {' in source
    assert '.studyAgentSlashSupportsDataViewer <- function() {' in source
    assert '.studyAgentSlashOpenTableViewer <- function(data, title = "Study Agent") {' in source
    assert 'cm_spec_overall_status = execute_summary$overall_status %||% NULL' in source
    assert 'cm_spec_execute_summary_path = file.path(base_dir, "analysis-settings", "strategus_execute_summary.json")' in source
    assert 'summary_path <- file.path(context$base_dir, "analysis-settings", "strategus_execute_summary.json")' in source


def test_exploration_registry_keeps_completed_and_skipped_steps_eligible_when_current_step_is_supplied() -> None:
    source = EXPLORATION_SOURCE.read_text(encoding="utf-8")
    assert 'requested_step_id,' in source
    assert 'statuses %in% c("completed", "failed", "stale", "running", "skipped")' in source
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
    assert 'command_id = "incidence_summary_preview"' in source
    assert 'artifact_requirements = c("incidence_summary_csv")' in source
    assert 'command_id = "incidence_analysis_settings_summary"' in source
    assert 'step_ids = c("generate_cohorts", "keeper_concept_sets", "keeper_case_review", "diagnostics", "incidence_spec", "cm_spec")' in source


def test_execution_dialogue_context_includes_exploration_fields() -> None:
    source = STATE_SOURCE.read_text(encoding="utf-8")
    assert 'artifact_registry <- .studyAgentSlashBuildArtifactRegistry(base_dir)' in source
    assert '.studyAgentSlashCompactExecutionArtifactSummary(' in source
    assert '.studyAgentSlashCompactExplorationCommandSummary(' in source
    assert 'diagnostics_summary <- if (exists(".studyAgentSlashCompactDiagnosticsDialogueSummary", mode = "function")) {' in source
    assert 'diagnostics_summary = diagnostics_summary' in source
    assert 'artifact_summary = artifact_summary' in source
    assert 'skipped_steps = skipped_step_summaries' in source
    assert 'available_exploration_commands = available_exploration_commands' in source
