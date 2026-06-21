.studyAgentSlashFindPlanStep <- function(project_state, step_id) {
  for (step in project_state$execution_plan %||% list()) {
    if (identical(as.character(step$step_id %||% ""), as.character(step_id))) return(step)
  }
  NULL
}

.studyAgentSlashWorkflowPlanSteps <- function(base_dir) {
  reconciled <- .studyAgentSlashReconcileProjectState(base_dir, write = TRUE)
  reconciled$project_state$execution_plan %||% list()
}

.studyAgentSlashWorkflowIsComplete <- function(base_dir) {
  steps <- .studyAgentSlashWorkflowPlanSteps(base_dir)
  if (length(steps) == 0) return(FALSE)
  all(vapply(steps, function(step) {
    as.character(step$status %||% "not_started") %in% c("completed", "skipped")
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
    if (is.null(dep_step) || !(dep_status %in% c("completed", "skipped"))) {
      return(FALSE)
    }
  }
  TRUE
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
    list(status = "failed", error = conditionMessage(e))
  })

  finished_at <- .studyAgentSlashNowTimestamp()
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
    if (status %in% c("completed", "skipped")) next
    if (!.studyAgentSlashStepDependenciesSatisfied(project_state, step)) next
    return(.studyAgentSlashRunWorkflowPlanStep(base_dir = base_dir, step_id = step$step_id, env = env))
  }
  list(status = "completed", step_id = NULL, message = "No remaining runnable workflow steps.")
}

.studyAgentSlashInspectWorkflowStepOutputs <- function(base_dir, step_id) {
  project_state <- .studyAgentSlashReconcileProjectState(base_dir, write = TRUE)$project_state
  step <- .studyAgentSlashFindPlanStep(project_state, step_id)
  if (is.null(step)) stop(sprintf("Unknown workflow step: %s", step_id))
  artifacts <- Filter(function(item) {
    identical(as.character(item$step_id %||% ""), as.character(step_id))
  }, project_state$artifacts %||% list())
  lapply(artifacts, function(item) {
    item$absolute_path <- .studyAgentSlashResolveProjectPath(item$path %||% "", base_dir)
    item$exists <- isTRUE(file.exists(item$absolute_path))
    item
  })
}

.studyAgentSlashSummarizeWorkflowStatus <- function(base_dir) {
  project_state <- .studyAgentSlashReconcileProjectState(base_dir, write = TRUE)$project_state
  vapply(project_state$execution_plan %||% list(), function(step) {
    sprintf("%s [%s]", as.character(step$label %||% step$step_id %||% ""), as.character(step$status %||% "not_started"))
  }, character(1))
}
