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
    if (identical(status, "completed")) {
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
    if (nzchar(script_name)) {
      project_state <- .studyAgentSlashRegisterProjectArtifact(
        project_state = project_state,
        artifact_id = paste0(step_id, "_script"),
        path = file.path(scripts_dir, script_name),
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
