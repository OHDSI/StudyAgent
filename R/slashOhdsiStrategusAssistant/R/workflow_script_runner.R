.studyAgentSlashFindPlanStep <- function(project_state, step_id) {
  for (step in project_state$execution_plan %||% list()) {
    if (identical(as.character(step$step_id %||% ""), as.character(step_id))) return(step)
  }
  NULL
}

.studyAgentSlashWorkflowTerminalStatuses <- function() {
  c("completed", "completed_with_failures", "skipped")
}

.studyAgentSlashWorkflowPlanSteps <- function(base_dir) {
  reconciled <- .studyAgentSlashReconcileProjectState(base_dir, write = TRUE)
  reconciled$project_state$execution_plan %||% list()
}

.studyAgentSlashWorkflowIsComplete <- function(base_dir) {
  steps <- .studyAgentSlashWorkflowPlanSteps(base_dir)
  if (length(steps) == 0) return(FALSE)
  all(vapply(steps, function(step) {
    as.character(step$status %||% "not_started") %in% .studyAgentSlashWorkflowTerminalStatuses()
  }, logical(1)))
}

.studyAgentSlashResolveWorkflowStepId <- function(base_dir, step_ref) {
  entered <- trimws(as.character(step_ref %||% ""))
  if (!nzchar(entered)) return(NULL)
  steps <- .studyAgentSlashWorkflowPlanSteps(base_dir)
  if (grepl("^[0-9]+$", entered)) {
    idx <- suppressWarnings(as.integer(entered))
    if (!is.na(idx) && idx >= 1L && idx <= length(steps)) {
      return(as.character(steps[[idx]]$step_id %||% ""))
    }
  }
  for (step in steps) {
    if (identical(as.character(step$step_id %||% ""), entered)) {
      return(as.character(step$step_id %||% ""))
    }
  }
  NULL
}

.studyAgentSlashWorkflowBuildOnlyStepIds <- function() {
  c("recommend_and_select")
}

.studyAgentSlashWorkflowSkippableStepIds <- function() {
  c("apply_improvements", "keeper_concept_sets", "keeper_case_review", "diagnostics")
}

.studyAgentSlashWorkflowStepIsSkippable <- function(step) {
  step_id <- as.character(step$step_id %||% "")
  nzchar(step_id) && step_id %in% .studyAgentSlashWorkflowSkippableStepIds()
}

.studyAgentSlashSafeConditionMessage <- function(condition) {
  message_text <- tryCatch(
    conditionMessage(condition),
    error = function(message_error) {
      raw <- tryCatch(as.character(condition$message %||% ""), error = function(...) "")
      raw <- trimws(raw)
      if (nzchar(raw)) return(raw)
      fallback <- tryCatch(as.character(message_error$message %||% ""), error = function(...) "")
      fallback <- trimws(fallback)
      if (nzchar(fallback)) {
        return(sprintf("Workflow step failed; original condition message could not be rendered cleanly: %s", fallback))
      }
      "Workflow step failed; original condition message could not be rendered cleanly."
    }
  )
  trimws(as.character(message_text %||% ""))
}

.studyAgentSlashWorkflowStepRunAvailability <- function(base_dir, step) {
  step_id <- as.character(step$step_id %||% "")
  script_rel_path <- as.character(step$script_path %||% "")
  script_exists <- nzchar(script_rel_path) &&
    file.exists(.studyAgentSlashResolveProjectPath(script_rel_path, base_dir))
  if (isTRUE(script_exists)) {
    return(list(
      runnable = TRUE,
      mode = "script",
      message = NULL
    ))
  }
  if (step_id %in% .studyAgentSlashWorkflowBuildOnlyStepIds()) {
    return(list(
      runnable = FALSE,
      mode = "build_only",
      message = sprintf(
        "Step %s was completed interactively during build mode and cannot be rerun from the execution menu. Use 'revise' to return to build mode.",
        step_id
      )
    ))
  }
  list(
    runnable = FALSE,
    mode = "missing_script",
    message = sprintf(
      "Workflow script not found: %s",
      .studyAgentSlashResolveProjectPath(script_rel_path, base_dir)
    )
  )
}

.studyAgentSlashFormatWorkflowStepChoices <- function(base_dir) {
  steps <- .studyAgentSlashWorkflowPlanSteps(base_dir)
  vapply(seq_along(steps), function(i) {
    step <- steps[[i]]
    availability <- .studyAgentSlashWorkflowStepRunAvailability(base_dir, step)
    action_text <- if (isTRUE(availability$runnable)) {
      sprintf("run %s", as.character(step$step_id %||% ""))
    } else if (identical(availability$mode, "build_only")) {
      "build-only; use revise"
    } else {
      sprintf("script missing for %s", as.character(step$step_id %||% ""))
    }
    sprintf(
      "%s. %s [%s] - %s",
      i,
      as.character(step$label %||% step$step_id %||% ""),
      as.character(step$status %||% "not_started"),
      action_text
    )
  }, character(1))
}

.studyAgentSlashStepDependenciesSatisfied <- function(project_state, step) {
  deps <- as.character(unlist(step$depends_on %||% character(0), use.names = FALSE))
  if (length(deps) == 0) return(TRUE)
  for (dep in deps) {
    dep_step <- .studyAgentSlashFindPlanStep(project_state, dep)
    dep_status <- as.character(dep_step$status %||% "not_started")
    if (is.null(dep_step) || !(dep_status %in% .studyAgentSlashWorkflowTerminalStatuses())) {
      return(FALSE)
    }
  }
  TRUE
}

.studyAgentSlashReadStrategusExecuteSummary <- function(base_dir, step_id) {
  step_id <- as.character(step_id %||% "")
  if (!(step_id %in% c("cm_spec", "incidence_spec"))) return(NULL)
  summary_path <- file.path(base_dir, "analysis-settings", "strategus_execute_summary.json")
  if (!file.exists(summary_path)) return(NULL)
  tryCatch(
    jsonlite::fromJSON(summary_path, simplifyVector = FALSE),
    error = function(e) NULL
  )
}

.studyAgentSlashPersistStrategusExecutionRoots <- function(base_dir, project_state, summary) {
  if (is.null(summary) || !is.list(summary)) return(project_state)
  results_root <- trimws(as.character(summary$results_root %||% ""))
  work_root <- trimws(as.character(summary$work_root %||% ""))
  if (!nzchar(results_root) && !nzchar(work_root)) return(project_state)
  .studyAgentSlashPersistExecutionRoots(
    base_dir = base_dir,
    project_state = project_state,
    results_root = if (nzchar(results_root)) results_root else NULL,
    work_root = if (nzchar(work_root)) work_root else NULL,
    source = "strategus_execute_summary",
    write = FALSE
  )
}

.studyAgentSlashResolvePostRunStepResult <- function(base_dir, step_id, default_status, default_error = NULL) {
  summary <- .studyAgentSlashReadStrategusExecuteSummary(base_dir, step_id)
  if (is.null(summary)) {
    return(list(status = default_status, error = default_error, summary = NULL))
  }
  overall_status <- as.character(summary$overall_status %||% "")
  modules <- summary$modules %||% list()
  failed_modules <- Filter(function(item) {
    as.character(item$status %||% "") %in% c("FAILED", "ERROR")
  }, modules)
  failed_names <- vapply(failed_modules, function(item) as.character(item$module_name %||% ""), character(1))
  failed_names <- failed_names[nzchar(failed_names)]
  error_message <- trimws(as.character(summary$error_message %||% default_error %||% ""))
  if (!nzchar(error_message) && length(failed_names) > 0) {
    error_message <- sprintf(
      "One or more Strategus modules failed: %s",
      paste(failed_names, collapse = ", ")
    )
  }
  if (identical(overall_status, "partial_failure")) {
    return(list(status = "completed_with_failures", error = error_message %||% NULL, summary = summary))
  }
  if (identical(overall_status, "failure")) {
    return(list(status = "failed", error = error_message %||% default_error, summary = summary))
  }
  list(status = default_status, error = default_error, summary = summary)
}

.studyAgentSlashUpdateArtifactDetection <- function(runtime_state, project_state, base_dir) {
  artifacts <- project_state$artifacts %||% list()
  detected <- list()
  for (name in names(artifacts)) {
    artifact <- artifacts[[name]] %||% list()
    path <- artifact$path %||% ""
    if (!nzchar(path)) next
    detected[[name]] <- list(
      path = as.character(path),
      exists = isTRUE(file.exists(.studyAgentSlashResolveProjectPath(path, base_dir))),
      checked_at = .studyAgentSlashNowTimestamp()
    )
  }
  runtime_state$artifacts_detected <- detected
  runtime_state
}

.studyAgentSlashRefreshProjectArtifactsAfterStep <- function(project_state, base_dir, step_id = NULL) {
  artifacts <- project_state$artifacts %||% list()
  for (name in names(artifacts)) {
    artifact <- artifacts[[name]]
    if (!is.null(step_id) && !identical(as.character(artifact$step_id %||% ""), as.character(step_id))) next
    path <- artifact$path %||% ""
    artifact$exists <- if (nzchar(path)) isTRUE(file.exists(.studyAgentSlashResolveProjectPath(path, base_dir))) else FALSE
    artifacts[[name]] <- artifact
  }
  project_state$artifacts <- artifacts
  project_state
}

.studyAgentSlashRunWorkflowPlanStep <- function(base_dir,
                                                step_id,
                                                env = NULL) {
  reconciled <- .studyAgentSlashReconcileProjectState(base_dir, write = TRUE)
  project_state <- reconciled$project_state
  runtime_state <- reconciled$runtime_state
  step <- .studyAgentSlashFindPlanStep(project_state, step_id)
  if (is.null(step)) stop(sprintf("Unknown workflow step: %s", step_id))
  if (!.studyAgentSlashStepDependenciesSatisfied(project_state, step)) {
    stop(sprintf("Dependencies are not satisfied for step: %s", step_id))
  }

  availability <- .studyAgentSlashWorkflowStepRunAvailability(base_dir, step)
  if (!isTRUE(availability$runnable)) stop(as.character(availability$message %||% "Workflow step is not runnable."))
  script_path <- .studyAgentSlashResolveProjectPath(step$script_path %||% "", base_dir)

  started_at <- .studyAgentSlashNowTimestamp()
  project_state <- .studyAgentSlashSetProjectStepStatus(project_state, step_id, "running")
  project_state$resume$current_step_id <- as.character(step_id)
  runtime_state$last_run_started_at <- started_at
  runtime_state <- .studyAgentSlashRecordRuntimeStepStatus(runtime_state, step_id, "running")
  .studyAgentSlashWriteStepState(
    base_dir = base_dir,
    step_id = step_id,
    status = "running",
    started_at = started_at,
    parameters = list(script_path = .studyAgentSlashRelativizeProjectPath(script_path, base_dir)),
    artifacts = list(required = as.list(.studyAgentSlashStepRequiredArtifacts(project_state, base_dir, step_id)))
  )
  .studyAgentSlashWriteProjectState(project_state, base_dir)
  .studyAgentSlashWriteRuntimeState(runtime_state, base_dir)

  exec_env <- env
  if (is.null(exec_env)) exec_env <- new.env(parent = globalenv())
  exec_env$`%||%` <- function(x, y) if (is.null(x)) y else x

  result <- tryCatch({
    sys.source(script_path, envir = exec_env, keep.source = FALSE)
    list(status = "completed", error = NULL)
  }, error = function(e) {
    list(status = "failed", error = .studyAgentSlashSafeConditionMessage(e))
  })
  result <- .studyAgentSlashResolvePostRunStepResult(
    base_dir = base_dir,
    step_id = step_id,
    default_status = result$status,
    default_error = result$error
  )

  finished_at <- .studyAgentSlashNowTimestamp()
  project_state <- .studyAgentSlashPersistStrategusExecutionRoots(
    base_dir = base_dir,
    project_state = project_state,
    summary = result$summary
  )
  project_state <- .studyAgentSlashSetProjectStepStatus(project_state, step_id, result$status, error = result$error)
  project_state <- .studyAgentSlashRefreshProjectArtifactsAfterStep(project_state, base_dir, step_id = step_id)
  project_state <- .studyAgentSlashAdvanceResumePointer(project_state)

  runtime_state$last_run_finished_at <- finished_at
  runtime_state$last_error <- result$error
  runtime_state <- .studyAgentSlashRecordRuntimeStepStatus(runtime_state, step_id, result$status, error = result$error)
  runtime_state$script_runs[[length(runtime_state$script_runs) + 1L]] <- Filter(Negate(is.null), list(
    step_id = as.character(step_id),
    script_path = .studyAgentSlashRelativizeProjectPath(script_path, base_dir),
    started_at = started_at,
    finished_at = finished_at,
    status = as.character(result$status),
    error = result$error
  ))
  runtime_state <- .studyAgentSlashUpdateArtifactDetection(runtime_state, project_state, base_dir)

  .studyAgentSlashWriteStepState(
    base_dir = base_dir,
    step_id = step_id,
    status = result$status,
    started_at = started_at,
    finished_at = finished_at,
    parameters = list(script_path = .studyAgentSlashRelativizeProjectPath(script_path, base_dir)),
    artifacts = list(required = as.list(.studyAgentSlashStepRequiredArtifacts(project_state, base_dir, step_id))),
    error = result$error
  )
  .studyAgentSlashWriteProjectState(project_state, base_dir)
  .studyAgentSlashWriteRuntimeState(runtime_state, base_dir)

  list(
    status = result$status,
    step_id = as.character(step_id),
    script_path = script_path,
    started_at = started_at,
    finished_at = finished_at,
    error = result$error
  )
}

.studyAgentSlashRunNextWorkflowPlanStep <- function(base_dir, env = NULL) {
  project_state <- .studyAgentSlashReconcileProjectState(base_dir, write = TRUE)$project_state
  for (step in project_state$execution_plan %||% list()) {
    status <- as.character(step$status %||% "not_started")
    if (status %in% .studyAgentSlashWorkflowTerminalStatuses()) next
    if (!.studyAgentSlashStepDependenciesSatisfied(project_state, step)) next
    return(.studyAgentSlashRunWorkflowPlanStep(base_dir = base_dir, step_id = step$step_id, env = env))
  }
  list(status = "completed", step_id = NULL, message = "No remaining runnable workflow steps.")
}

.studyAgentSlashSkipWorkflowStep <- function(base_dir,
                                             step_id,
                                             reason = "user_skipped") {
  reconciled <- .studyAgentSlashReconcileProjectState(base_dir, write = TRUE)
  project_state <- reconciled$project_state
  runtime_state <- reconciled$runtime_state
  step <- .studyAgentSlashFindPlanStep(project_state, step_id)
  if (is.null(step)) stop(sprintf("Unknown workflow step: %s", step_id))
  if (!isTRUE(.studyAgentSlashWorkflowStepIsSkippable(step))) {
    stop(sprintf("Step %s cannot be skipped.", step_id))
  }
  if (!.studyAgentSlashStepDependenciesSatisfied(project_state, step)) {
    stop(sprintf("Dependencies are not satisfied for step: %s", step_id))
  }

  current_status <- as.character(step$status %||% "not_started")
  if (current_status %in% .studyAgentSlashWorkflowTerminalStatuses()) {
    return(list(
      status = current_status,
      step_id = as.character(step_id),
      skipped = identical(current_status, "skipped"),
      message = if (identical(current_status, "skipped")) {
        sprintf("Step %s is already skipped.", step_id)
      } else {
        sprintf("Step %s is already completed.", step_id)
      }
    ))
  }

  skipped_at <- .studyAgentSlashNowTimestamp()
  project_state <- .studyAgentSlashSetProjectStepStatus(project_state, step_id, "skipped")
  project_state <- .studyAgentSlashAdvanceResumePointer(project_state)

  runtime_state$last_run_finished_at <- skipped_at
  runtime_state$last_error <- NULL
  runtime_state <- .studyAgentSlashRecordRuntimeStepStatus(runtime_state, step_id, "skipped")
  runtime_state$current_step <- project_state$resume$current_step_id %||% NULL
  runtime_state <- .studyAgentSlashUpdateArtifactDetection(runtime_state, project_state, base_dir)

  .studyAgentSlashWriteStepState(
    base_dir = base_dir,
    step_id = step_id,
    status = "skipped",
    finished_at = skipped_at,
    summary = list(
      skipped = TRUE,
      skip_reason = as.character(reason %||% "user_skipped")
    ),
    artifacts = list(required = as.list(.studyAgentSlashStepRequiredArtifacts(project_state, base_dir, step_id))),
    error = NULL
  )
  .studyAgentSlashWriteProjectState(project_state, base_dir)
  .studyAgentSlashWriteRuntimeState(runtime_state, base_dir)

  list(
    status = "skipped",
    step_id = as.character(step_id),
    skipped = TRUE,
    skipped_at = skipped_at,
    reason = as.character(reason %||% "user_skipped")
  )
}

.studyAgentSlashInspectWorkflowStepOutputs <- function(base_dir, step_id) {
  project_state <- .studyAgentSlashReconcileProjectState(base_dir, write = TRUE)$project_state
  step <- .studyAgentSlashFindPlanStep(project_state, step_id)
  if (is.null(step)) stop(sprintf("Unknown workflow step: %s", step_id))
  artifacts <- Filter(function(item) {
    identical(as.character(item$step_id %||% ""), as.character(step_id))
  }, project_state$artifacts %||% list())
  required_paths <- .studyAgentSlashStepRequiredArtifacts(project_state, base_dir, step_id)
  existing_paths <- vapply(artifacts, function(item) as.character(item$path %||% ""), character(1))
  supplemental_paths <- setdiff(required_paths, existing_paths)
  if (length(supplemental_paths) > 0) {
    for (i in seq_along(supplemental_paths)) {
      supplemental_path <- supplemental_paths[[i]]
      artifacts[[paste0("derived_required_artifact_", i)]] <- list(
        id = paste0(step_id, "_derived_required_artifact_", i),
        path = supplemental_path,
        type = "derived_step_output",
        step_id = step_id,
        status = "expected"
      )
    }
  }
  lapply(artifacts, function(item) {
    item$absolute_path <- .studyAgentSlashResolveProjectPath(item$path %||% "", base_dir)
    item$exists <- isTRUE(file.exists(item$absolute_path) || dir.exists(item$absolute_path))
    item
  })
}

.studyAgentSlashSummarizeWorkflowStatus <- function(base_dir) {
  project_state <- .studyAgentSlashReconcileProjectState(base_dir, write = TRUE)$project_state
  vapply(project_state$execution_plan %||% list(), function(step) {
    status <- as.character(step$status %||% "not_started")
    run_hint <- ""
    if (identical(status, "not_started")) {
      availability <- .studyAgentSlashWorkflowStepRunAvailability(base_dir, step)
      if (isTRUE(availability$runnable)) run_hint <- sprintf(" — run %s", as.character(step$step_id %||% ""))
    }
    sprintf("%s [%s]%s", as.character(step$label %||% step$step_id %||% ""), status, run_hint)
  }, character(1))
}
