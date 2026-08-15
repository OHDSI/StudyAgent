.studyAgentSlashNowTimestamp <- function() {
  format(as.POSIXct(Sys.time(), tz = "UTC"), "%Y-%m-%dT%H:%M:%SZ", tz = "UTC")
}

.studyAgentSlashRelativizeProjectPath <- function(path, base_dir) {
  path <- as.character(path %||% "")
  if (!nzchar(path)) return(NA_character_)
  base_dir <- normalizePath(base_dir, winslash = "/", mustWork = FALSE)
  normalized <- normalizePath(path, winslash = "/", mustWork = FALSE)
  prefix <- paste0(base_dir, "/")
  if (identical(normalized, base_dir)) return(".")
  if (startsWith(normalized, prefix)) {
    return(sub(paste0("^", gsub("([.|()\\^{}+$*?]|\\[|\\])", "\\\\\\1", prefix)), "", normalized))
  }
  normalized
}

.studyAgentSlashResolveProjectPath <- function(path, base_dir) {
  path <- as.character(path %||% "")
  if (!nzchar(path) || identical(path, ".")) return(normalizePath(base_dir, winslash = "/", mustWork = FALSE))
  if (grepl("^(/|[A-Za-z]:[\\\\/])", path)) {
    return(normalizePath(path, winslash = "/", mustWork = FALSE))
  }
  normalizePath(file.path(base_dir, path), winslash = "/", mustWork = FALSE)
}

.studyAgentSlashReadProjectJson <- function(path) {
  jsonlite::fromJSON(path, simplifyVector = FALSE)
}

.studyAgentSlashWriteProjectJson <- function(x, path) {
  jsonlite::write_json(x, path, pretty = TRUE, auto_unbox = TRUE, null = "null")
}

.studyAgentSlashNewProjectArtifact <- function(id,
                                               path,
                                               base_dir,
                                               type = NULL,
                                               step_id = NULL,
                                               role = NULL,
                                               status = NULL,
                                               metadata = list()) {
  normalized_path <- .studyAgentSlashRelativizeProjectPath(path, base_dir)
  Filter(Negate(is.null), list(
    id = as.character(id),
    path = normalized_path,
    type = if (is.null(type)) NULL else as.character(type),
    step_id = if (is.null(step_id)) NULL else as.character(step_id),
    role = if (is.null(role)) NULL else as.character(role),
    status = if (is.null(status)) NULL else as.character(status),
    exists = isTRUE(file.exists(.studyAgentSlashResolveProjectPath(normalized_path, base_dir))),
    metadata = metadata %||% list()
  ))
}

.studyAgentSlashNewProjectState <- function(workflow_type,
                                            base_dir,
                                            output_dir = file.path(base_dir, "outputs"),
                                            scripts_dir = file.path(base_dir, "scripts"),
                                            execution_plan = list(),
                                            study_context = list(),
                                            dialogue_context = list(),
                                            artifacts = list(),
                                            project_id = NULL) {
  base_dir <- normalizePath(base_dir, winslash = "/", mustWork = FALSE)
  now <- .studyAgentSlashNowTimestamp()
  list(
    schema_version = 1L,
    project_id = if (!is.null(project_id) && nzchar(trimws(project_id))) {
      as.character(project_id)
    } else {
      paste0(as.character(workflow_type), "-", format(Sys.time(), "%Y%m%d%H%M%S", tz = "UTC"))
    },
    workflow_type = as.character(workflow_type),
    created_at = now,
    updated_at = now,
    base_dir_layout = list(
      outputs = .studyAgentSlashRelativizeProjectPath(output_dir, base_dir),
      scripts = .studyAgentSlashRelativizeProjectPath(scripts_dir, base_dir)
    ),
    artifacts = artifacts %||% list(),
    execution_plan = execution_plan %||% list(),
    study_context = study_context %||% list(),
    dialogue_context = dialogue_context %||% list(),
    resume = list(
      current_step_id = NULL,
      last_completed_step_id = NULL,
      ready_for_execution = FALSE
    )
  )
}

.studyAgentSlashNewRuntimeState <- function(project_state, shell_session_metadata = list()) {
  list(
    schema_version = 1L,
    project_id = as.character(project_state$project_id %||% ""),
    workflow_type = as.character(project_state$workflow_type %||% ""),
    current_step = NULL,
    step_status = list(),
    step_history = list(),
    last_error = NULL,
    last_run_started_at = NULL,
    last_run_finished_at = NULL,
    script_runs = list(),
    artifacts_detected = list(),
    shell_session_metadata = shell_session_metadata %||% list()
  )
}

.studyAgentSlashProjectStatePath <- function(base_dir) {
  file.path(base_dir, "study-agent-project.json")
}

.studyAgentSlashRuntimeStatePath <- function(base_dir) {
  file.path(base_dir, "outputs", "study_agent_runtime_state.json")
}

.studyAgentSlashReadProjectState <- function(base_dir) {
  .studyAgentSlashReadProjectJson(.studyAgentSlashProjectStatePath(base_dir))
}

.studyAgentSlashWriteProjectState <- function(project_state, base_dir) {
  project_state$updated_at <- .studyAgentSlashNowTimestamp()
  .studyAgentSlashWriteProjectJson(project_state, .studyAgentSlashProjectStatePath(base_dir))
}

.studyAgentSlashReadRuntimeState <- function(base_dir) {
  .studyAgentSlashReadProjectJson(.studyAgentSlashRuntimeStatePath(base_dir))
}

.studyAgentSlashWriteRuntimeState <- function(runtime_state, base_dir) {
  .studyAgentSlashWriteProjectJson(runtime_state, .studyAgentSlashRuntimeStatePath(base_dir))
}

.studyAgentSlashPathLooksLikeNestedProjectRelative <- function(path, base_dir) {
  path <- trimws(as.character(path %||% ""))
  if (!nzchar(path)) return(FALSE)
  if (grepl("^(?:/|~|[A-Za-z]:[/\\])", path)) return(FALSE)
  normalized <- chartr("\\", "/", path)
  prefix <- paste0(basename(normalizePath(base_dir, winslash = "/", mustWork = FALSE)), "/")
  startsWith(normalized, prefix)
}

.studyAgentSlashConfiguredExecutionRoots <- function(base_dir,
                                                     project_state = NULL,
                                                     prefer_confirmed = TRUE) {
  project_state <- project_state %||% tryCatch(.studyAgentSlashReadProjectState(base_dir), error = function(e) NULL)
  study_context <- (project_state %||% list())$study_context %||% list()
  confirmed <- study_context$execution_roots %||% list()

  resolve_saved_path <- function(path) {
    path <- trimws(as.character(path %||% ""))
    if (!nzchar(path)) return(NULL)
    .studyAgentSlashResolveProjectPath(path, base_dir)
  }

  confirmed_results <- resolve_saved_path(confirmed$results_root %||% "")
  confirmed_work <- resolve_saved_path(confirmed$work_root %||% "")

  configured_results_input <- ""
  configured_work_input <- ""
  configured_results <- NULL
  configured_work <- NULL
  exec_settings_path <- file.path(base_dir, "strategus-execution-settings.json")
  if (file.exists(exec_settings_path)) {
    exec_cfg <- tryCatch(readStrategusExecutionSettings(exec_settings_path), error = function(e) NULL)
    if (is.list(exec_cfg)) {
      configured_results_input <- trimws(as.character(exec_cfg$resultsFolder %||% ""))
      configured_work_input <- trimws(as.character(exec_cfg$workFolder %||% ""))
      if (nzchar(configured_results_input)) configured_results <- .studyAgentSlashResolveProjectPath(configured_results_input, base_dir)
      if (nzchar(configured_work_input)) configured_work <- .studyAgentSlashResolveProjectPath(configured_work_input, base_dir)
    }
  }

  warnings <- character(0)
  if (.studyAgentSlashPathLooksLikeNestedProjectRelative(configured_results_input, base_dir)) {
    warnings <- c(warnings, sprintf("resultsFolder looks project-relative and may duplicate the project root: %s", configured_results_input))
  }
  if (.studyAgentSlashPathLooksLikeNestedProjectRelative(configured_work_input, base_dir)) {
    warnings <- c(warnings, sprintf("workFolder looks project-relative and may duplicate the project root: %s", configured_work_input))
  }

  preferred_results <- if (isTRUE(prefer_confirmed) && !is.null(confirmed_results)) confirmed_results else configured_results
  preferred_work <- if (isTRUE(prefer_confirmed) && !is.null(confirmed_work)) confirmed_work else configured_work
  if (is.null(preferred_results)) preferred_results <- configured_results %||% confirmed_results
  if (is.null(preferred_work)) preferred_work <- configured_work %||% confirmed_work

  list(
    results_root = preferred_results,
    work_root = preferred_work,
    confirmed_results_root = confirmed_results,
    confirmed_work_root = confirmed_work,
    configured_results_root = configured_results,
    configured_work_root = configured_work,
    configured_results_input = configured_results_input,
    configured_work_input = configured_work_input,
    warnings = as.list(unique(warnings))
  )
}

.studyAgentSlashPersistExecutionRoots <- function(base_dir,
                                                  project_state = NULL,
                                                  results_root = NULL,
                                                  work_root = NULL,
                                                  source = "user_confirmed",
                                                  warnings = character(0),
                                                  write = TRUE) {
  project_state <- project_state %||% .studyAgentSlashReadProjectState(base_dir)
  configured <- .studyAgentSlashConfiguredExecutionRoots(base_dir, project_state = project_state, prefer_confirmed = FALSE)

  resolve_root <- function(path, fallback = NULL) {
    path <- trimws(as.character(path %||% ""))
    if (!nzchar(path)) return(fallback)
    .studyAgentSlashResolveProjectPath(path, base_dir)
  }

  resolved_results <- resolve_root(results_root, fallback = configured$configured_results_root %||% NULL)
  resolved_work <- resolve_root(work_root, fallback = configured$configured_work_root %||% NULL)
  warning_values <- unique(c(
    as.character(unlist(configured$warnings %||% character(0), use.names = FALSE)),
    as.character(warnings %||% character(0))
  ))
  warning_values <- warning_values[nzchar(warning_values)]

  if (is.null(project_state$study_context) || !is.list(project_state$study_context)) {
    project_state$study_context <- list()
  }
  project_state$study_context$execution_roots <- Filter(Negate(is.null), list(
    results_root = if (!is.null(resolved_results) && nzchar(as.character(resolved_results))) .studyAgentSlashRelativizeProjectPath(resolved_results, base_dir) else NULL,
    work_root = if (!is.null(resolved_work) && nzchar(as.character(resolved_work))) .studyAgentSlashRelativizeProjectPath(resolved_work, base_dir) else NULL,
    source = as.character(source %||% "user_confirmed"),
    confirmed_at = .studyAgentSlashNowTimestamp(),
    warnings = if (length(warning_values) > 0) as.list(warning_values) else NULL
  ))

  if (!isTRUE(write)) return(project_state)
  .studyAgentSlashWriteProjectState(project_state, base_dir)
  if (file.exists(.studyAgentSlashRuntimeStatePath(base_dir))) {
    reconciled <- .studyAgentSlashReconcileProjectState(base_dir, project_state = project_state, write = TRUE)
    return(reconciled$project_state %||% project_state)
  }
  project_state
}

.studyAgentSlashRegisterProjectArtifact <- function(project_state,
                                                    artifact_id,
                                                    path,
                                                    base_dir,
                                                    type = NULL,
                                                    step_id = NULL,
                                                    role = NULL,
                                                    status = NULL,
                                                    metadata = list()) {
  if (is.null(project_state$artifacts) || !is.list(project_state$artifacts)) {
    project_state$artifacts <- list()
  }
  project_state$artifacts[[as.character(artifact_id)]] <- .studyAgentSlashNewProjectArtifact(
    id = artifact_id,
    path = path,
    base_dir = base_dir,
    type = type,
    step_id = step_id,
    role = role,
    status = status,
    metadata = metadata
  )
  project_state
}

.studyAgentSlashSetProjectStepStatus <- function(project_state,
                                                 step_id,
                                                 status,
                                                 error = NULL) {
  if (is.null(project_state$execution_plan) || !is.list(project_state$execution_plan)) {
    return(project_state)
  }
  for (i in seq_along(project_state$execution_plan)) {
    step <- project_state$execution_plan[[i]]
    if (identical(as.character(step$step_id %||% ""), as.character(step_id))) {
      step$status <- as.character(status)
      step$updated_at <- .studyAgentSlashNowTimestamp()
      if (is.null(error) || !nzchar(trimws(as.character(error)))) {
        step$error <- NULL
      } else {
        step$error <- as.character(error)
      }
      project_state$execution_plan[[i]] <- step
      break
    }
  }
  project_state
}

.studyAgentSlashAdvanceResumePointer <- function(project_state) {
  plan <- project_state$execution_plan %||% list()
  current_step_id <- NULL
  last_completed_step_id <- NULL
  for (step in plan) {
    status <- as.character(step$status %||% "not_started")
    step_id <- as.character(step$step_id %||% "")
    if (status %in% c("completed", "completed_with_failures")) {
      last_completed_step_id <- step_id
      next
    }
    if (is.null(current_step_id) && !identical(status, "skipped")) {
      current_step_id <- step_id
    }
  }
  project_state$resume <- list(
    current_step_id = current_step_id,
    last_completed_step_id = last_completed_step_id,
    ready_for_execution = length(plan) > 0
  )
  project_state
}

.studyAgentSlashRecordRuntimeStepStatus <- function(runtime_state,
                                                    step_id,
                                                    status,
                                                    error = NULL) {
  if (is.null(runtime_state$step_status) || !is.list(runtime_state$step_status)) {
    runtime_state$step_status <- list()
  }
  runtime_state$step_status[[as.character(step_id)]] <- list(
    status = as.character(status),
    updated_at = .studyAgentSlashNowTimestamp(),
    error = if (is.null(error) || !nzchar(trimws(as.character(error)))) NULL else as.character(error)
  )
  runtime_state$current_step <- as.character(step_id)
  runtime_state
}

.studyAgentSlashFinalizeBuildProjectState <- function(base_dir,
                                                      completed_steps = character(0),
                                                      skipped_steps = character(0),
                                                      failed_steps = character(0)) {
  project_state <- .studyAgentSlashReadProjectState(base_dir)
  runtime_state <- .studyAgentSlashReadRuntimeState(base_dir)
  if (is.null(runtime_state$step_status) || !is.list(runtime_state$step_status)) {
    runtime_state$step_status <- list()
  }

  set_runtime_status <- function(step_id, status, error = NULL) {
    runtime_state$step_status[[as.character(step_id)]] <<- list(
      status = as.character(status),
      updated_at = .studyAgentSlashNowTimestamp(),
      error = if (is.null(error) || !nzchar(trimws(as.character(error)))) NULL else as.character(error)
    )
  }

  for (step_id in as.character(completed_steps %||% character(0))) {
    if (!nzchar(step_id)) next
    project_state <- .studyAgentSlashSetProjectStepStatus(project_state, step_id, "completed")
    set_runtime_status(step_id, "completed")
  }
  for (step_id in as.character(skipped_steps %||% character(0))) {
    if (!nzchar(step_id)) next
    project_state <- .studyAgentSlashSetProjectStepStatus(project_state, step_id, "skipped")
    set_runtime_status(step_id, "skipped")
  }
  for (step_id in as.character(failed_steps %||% character(0))) {
    if (!nzchar(step_id)) next
    project_state <- .studyAgentSlashSetProjectStepStatus(project_state, step_id, "failed")
    set_runtime_status(step_id, "failed")
  }

  project_state <- .studyAgentSlashAdvanceResumePointer(project_state)
  runtime_state$current_step <- project_state$resume$current_step_id %||% NULL
  runtime_state <- .studyAgentSlashUpdateArtifactDetection(runtime_state, project_state, base_dir)
  .studyAgentSlashWriteProjectState(project_state, base_dir)
  .studyAgentSlashWriteRuntimeState(runtime_state, base_dir)
  invisible(list(project_state = project_state, runtime_state = runtime_state))
}

.studyAgentSlashWorkflowDialogueArtifactPaths <- function(project_state, base_dir) {
  artifacts <- project_state$artifacts %||% list()
  collected <- list()
  for (name in names(artifacts)) {
    artifact <- artifacts[[name]] %||% list()
    artifact_path <- as.character(artifact$path %||% "")
    if (!nzchar(artifact_path)) next
    collected[[name]] <- .studyAgentSlashResolveProjectPath(artifact_path, base_dir)
  }
  collected
}

.studyAgentSlashSelectExecutionDialogueArtifacts <- function(artifact_registry,
                                                            current_step_id = NULL,
                                                            max_items = 12L) {
  current_step_id <- as.character(current_step_id %||% "")
  priority_ids <- c(
    "selected_cohorts_csv",
    "diagnostics_results_module_dir",
    "diagnostics_work_module_dir",
    "cm_diagnostics_dir",
    "cm_results_dir",
    "analysis_settings_dir",
    "analysis_specification_json",
    "cm_analysis_state_json",
    "strategus_execute_result_rds",
    "strategus_results_dir",
    "strategus_work_dir",
    "cohort_generation_results_dir",
    "cohort_generation_module_dir",
    "cg_cohort_count_csv",
    "cg_cohort_definition_csv",
    "cg_cohort_inclusion_csv",
    "cg_cohort_inc_result_csv",
    "cg_cohort_inc_stats_csv",
    "cg_cohort_summary_stats_csv",
    "cm_analysis_json",
    "time_at_risk_settings",
    "db_details_json",
    "execution_settings_json"
  )
  items <- Filter(function(item) isTRUE(item$exists), artifact_registry %||% list())
  if (length(items) == 0) return(list())

  score_item <- function(item, idx) {
    item_id <- as.character(item$id %||% "")
    item_step <- as.character(item$step_id %||% "")
    step_rank <- if (nzchar(current_step_id) && identical(item_step, current_step_id)) {
      0L
    } else if (identical(item_step, "generate_cohorts")) {
      1L
    } else if (!nzchar(item_step)) {
      2L
    } else {
      3L
    }
    priority_rank <- match(item_id, priority_ids)
    if (is.na(priority_rank)) priority_rank <- 1000L + as.integer(idx)
    c(step_rank, priority_rank, as.integer(idx))
  }

  ordered_idx <- order(vapply(seq_along(items), function(i) score_item(items[[i]], i)[1], integer(1)),
                       vapply(seq_along(items), function(i) score_item(items[[i]], i)[2], integer(1)),
                       vapply(seq_along(items), function(i) score_item(items[[i]], i)[3], integer(1)))
  items[utils::head(ordered_idx, n = max_items)]
}

.studyAgentSlashCompactExecutionArtifactSummary <- function(artifact_registry,
                                                            current_step_id = NULL,
                                                            max_items = 12L) {
  selected <- .studyAgentSlashSelectExecutionDialogueArtifacts(
    artifact_registry = artifact_registry,
    current_step_id = current_step_id,
    max_items = max_items
  )
  lapply(selected, function(item) compact_workflow_dialogue_context(list(
    artifact_id = item$id %||% NULL,
    artifact_class = item$artifact_class %||% NULL,
    step_id = item$step_id %||% NULL,
    exists = item$exists %||% NULL
  )))
}

.studyAgentSlashReadStrategusExecuteSummaryCompact <- function(base_dir) {
  summary_path <- file.path(base_dir, "analysis-settings", "strategus_execute_summary.json")
  if (!file.exists(summary_path)) return(NULL)
  tryCatch(.studyAgentSlashReadProjectJson(summary_path), error = function(e) NULL)
}

.studyAgentSlashCompactExplorationCommandSummary <- function(commands, max_items = 6L) {
  commands <- commands %||% list()
  if (length(commands) == 0) return(list())
  commands <- utils::head(commands, n = max_items)
  lapply(commands, function(cmd) compact_workflow_dialogue_context(list(
    command_id = cmd$command_id %||% NULL,
    label = cmd$label %||% NULL,
    purpose = cmd$purpose %||% NULL
  )))
}

.studyAgentSlashBuildExecutionDialogueContext <- function(project_state,
                                                          base_dir,
                                                          step = NULL,
                                                          runtime_state = NULL) {
  study_context <- project_state$study_context %||% list()
  step <- step %||% list()
  runtime_state <- runtime_state %||% list()

  selected_target_ids <- study_context$selected_target_ids %||% study_context$selected_target_id %||% list()
  selected_comparator_ids <- study_context$selected_comparator_ids %||% study_context$selected_comparator_id %||% list()
  selected_outcome_ids <- study_context$selected_outcome_ids %||% list()
  if (!is.list(selected_target_ids)) selected_target_ids <- as.list(selected_target_ids)
  if (!is.list(selected_comparator_ids)) selected_comparator_ids <- as.list(selected_comparator_ids)
  if (!is.list(selected_outcome_ids)) selected_outcome_ids <- as.list(selected_outcome_ids)

  current_step_id <- step$step_id %||% project_state$resume$current_step_id %||% NULL
  skipped_steps <- Filter(function(plan_step) {
    identical(as.character(plan_step$status %||% ""), "skipped")
  }, project_state$execution_plan %||% list())
  skipped_step_summaries <- lapply(skipped_steps, function(plan_step) {
    step_id <- as.character(plan_step$step_id %||% "")
    step_state <- .studyAgentSlashReadStepState(base_dir, step_id) %||% list()
    summary <- step_state$summary %||% list()
    compact_workflow_dialogue_context(list(
      step_id = step_id,
      label = as.character(plan_step$label %||% step_id),
      skip_reason = summary$skip_reason %||% NULL
    ))
  })
  artifact_registry <- .studyAgentSlashBuildArtifactRegistry(base_dir)
  artifact_summary <- .studyAgentSlashCompactExecutionArtifactSummary(
    artifact_registry = artifact_registry,
    current_step_id = current_step_id,
    max_items = 12L
  )
  requestable_artifact_ids <- as.list(vapply(artifact_summary, function(item) {
    as.character(item$artifact_id %||% "")
  }, character(1)))
  available_exploration_commands <- .studyAgentSlashCompactExplorationCommandSummary(
    .studyAgentSlashListExplorationCommands(
      base_dir = base_dir,
      workflow_type = project_state$workflow_type %||% "",
      step_id = current_step_id
    ),
    max_items = 6L
  )
  diagnostics_summary <- if (exists(".studyAgentSlashCompactDiagnosticsDialogueSummary", mode = "function")) {
    .studyAgentSlashCompactDiagnosticsDialogueSummary(base_dir = base_dir, project_state = project_state, max_items = 6L)
  } else {
    list()
  }
  cm_spec_summary <- if (exists(".studyAgentSlashCompactCmSpecDialogueSummary", mode = "function")) {
    .studyAgentSlashCompactCmSpecDialogueSummary(base_dir = base_dir, project_state = project_state, max_items = 6L)
  } else {
    list()
  }
  strategus_summary <- .studyAgentSlashReadStrategusExecuteSummaryCompact(base_dir)
  failed_module_names <- as.list(vapply(Filter(function(item) {
    as.character(item$status %||% "") %in% c("FAILED", "ERROR")
  }, strategus_summary$modules %||% list()), function(item) {
    as.character(item$module_name %||% "")
  }, character(1)))

  compact_workflow_dialogue_context(list(
    study_intent = study_context$study_intent %||% NULL,
    target_statement = study_context$target_statement %||% NULL,
    comparator_statement = study_context$comparator_statement %||% NULL,
    outcome_statement = study_context$outcome_statement %||% NULL,
    outcome_statements = study_context$outcome_statements %||% NULL,
    comparison_label = study_context$comparison_label %||% NULL,
    analytic_settings_mode = study_context$analytic_settings_mode %||% NULL,
    analysis_settings_path = study_context$cm_analysis_json_path %||% study_context$analysis_settings_path %||% study_context$time_at_risk_settings_path %||% NULL,
    selected_target_ids = selected_target_ids,
    selected_comparator_ids = selected_comparator_ids,
    selected_outcome_ids = selected_outcome_ids,
    execution_step_id = current_step_id,
    execution_label = step$label %||% NULL,
    execution_status = step$status %||% NULL,
    execution_status_detail = strategus_summary$overall_status %||% NULL,
    execution_plan_summary = as.list(.studyAgentSlashSummarizeWorkflowStatus(base_dir)),
    skipped_steps = skipped_step_summaries,
    failed_module_names = failed_module_names,
    module_failure_count = length(failed_module_names),
    strategus_overall_status = strategus_summary$overall_status %||% NULL,
    available_exploration_commands = available_exploration_commands,
    diagnostics_summary = diagnostics_summary,
    cm_spec_summary = cm_spec_summary,
    artifact_summary = artifact_summary,
    requestable_artifact_ids = requestable_artifact_ids,
    artifact_request_policy = compact_workflow_dialogue_context(list(
      use_logical_artifact_ids = TRUE,
      ask_before_loading_more = TRUE,
      max_artifacts_per_request = 3L
    )),
    last_error = runtime_state$last_error %||% NULL
  ))
}

.studyAgentSlashInitializeProjectFiles <- function(workflow_type,
                                                  base_dir,
                                                  output_dir,
                                                  scripts_dir,
                                                  execution_plan,
                                                  study_context = list(),
                                                  dialogue_context = list(),
                                                  artifact_specs = list(),
                                                  shell_session_metadata = list()) {
  project_state <- .studyAgentSlashNewProjectState(
    workflow_type = workflow_type,
    base_dir = base_dir,
    output_dir = output_dir,
    scripts_dir = scripts_dir,
    execution_plan = execution_plan,
    study_context = study_context,
    dialogue_context = dialogue_context
  )

  for (step in execution_plan %||% list()) {
    step_id <- as.character(step$step_id %||% "")
    script_name <- as.character(step$script_name %||% "")
    script_path <- if (nzchar(script_name)) file.path(scripts_dir, script_name) else NULL
    if (!is.null(script_path) && isTRUE(file.exists(script_path))) {
      project_state <- .studyAgentSlashRegisterProjectArtifact(
        project_state = project_state,
        artifact_id = paste0(step_id, "_script"),
        path = script_path,
        base_dir = base_dir,
        type = "script",
        step_id = step_id,
        status = "ready"
      )
    }
    produced <- as.character(unlist(step$produces_artifacts %||% character(0), use.names = FALSE))
    if (length(produced) == 0) next
    for (i in seq_along(produced)) {
      project_state <- .studyAgentSlashRegisterProjectArtifact(
        project_state = project_state,
        artifact_id = paste0(step_id, "_artifact_", i),
        path = file.path(base_dir, produced[[i]]),
        base_dir = base_dir,
        type = "step_output",
        step_id = step_id,
        status = "expected"
      )
    }
  }

  for (spec in artifact_specs %||% list()) {
    project_state <- .studyAgentSlashRegisterProjectArtifact(
      project_state = project_state,
      artifact_id = spec$id %||% paste0("artifact_", length(project_state$artifacts) + 1L),
      path = spec$path %||% "",
      base_dir = base_dir,
      type = spec$type %||% NULL,
      step_id = spec$step_id %||% NULL,
      role = spec$role %||% NULL,
      status = spec$status %||% NULL,
      metadata = spec$metadata %||% list()
    )
  }

  project_state <- .studyAgentSlashAdvanceResumePointer(project_state)
  runtime_state <- .studyAgentSlashNewRuntimeState(project_state, shell_session_metadata = shell_session_metadata)
  runtime_state <- .studyAgentSlashUpdateArtifactDetection(runtime_state, project_state, base_dir)
  .studyAgentSlashWriteProjectState(project_state, base_dir)
  .studyAgentSlashWriteRuntimeState(runtime_state, base_dir)
  invisible(list(project_state = project_state, runtime_state = runtime_state))
}
