.studyAgentSlashFindPlanStep <- function(project_state, step_id) {
  for (step in project_state$execution_plan %||% list()) {
    if (identical(as.character(step$step_id %||% ""), as.character(step_id))) return(step)
  }
  NULL
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
  project_state <- .studyAgentSlashReadProjectState(base_dir)
  runtime_state <- .studyAgentSlashReadRuntimeState(base_dir)
  step <- .studyAgentSlashFindPlanStep(project_state, step_id)
  if (is.null(step)) stop(sprintf("Unknown workflow step: %s", step_id))
  if (!.studyAgentSlashStepDependenciesSatisfied(project_state, step)) {
    stop(sprintf("Dependencies are not satisfied for step: %s", step_id))
  }

  script_path <- .studyAgentSlashResolveProjectPath(step$script_path %||% "", base_dir)
  if (!file.exists(script_path)) stop(sprintf("Workflow script not found: %s", script_path))

  started_at <- .studyAgentSlashNowTimestamp()
  project_state <- .studyAgentSlashSetProjectStepStatus(project_state, step_id, "running")
  project_state$resume$current_step_id <- as.character(step_id)
  runtime_state$last_run_started_at <- started_at
  runtime_state <- .studyAgentSlashRecordRuntimeStepStatus(runtime_state, step_id, "running")
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
  project_state <- .studyAgentSlashReadProjectState(base_dir)
  for (step in project_state$execution_plan %||% list()) {
    status <- as.character(step$status %||% "not_started")
    if (status %in% c("completed", "skipped")) next
    if (!.studyAgentSlashStepDependenciesSatisfied(project_state, step)) next
    return(.studyAgentSlashRunWorkflowPlanStep(base_dir = base_dir, step_id = step$step_id, env = env))
  }
  list(status = "completed", step_id = NULL, message = "No remaining runnable workflow steps.")
}

.studyAgentSlashInspectWorkflowStepOutputs <- function(base_dir, step_id) {
  project_state <- .studyAgentSlashReadProjectState(base_dir)
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
  project_state <- .studyAgentSlashReadProjectState(base_dir)
  vapply(project_state$execution_plan %||% list(), function(step) {
    sprintf("%s [%s]", as.character(step$label %||% step$step_id %||% ""), as.character(step$status %||% "not_started"))
  }, character(1))
}
