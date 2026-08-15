.studyAgentSlashStepStateDir <- function(base_dir) {
  file.path(base_dir, "outputs", "step-state")
}

.studyAgentSlashStepStatePath <- function(base_dir, step_id) {
  file.path(.studyAgentSlashStepStateDir(base_dir), sprintf("%s.json", as.character(step_id %||% "")))
}

.studyAgentSlashEnsureStepStateDir <- function(base_dir) {
  dir_path <- .studyAgentSlashStepStateDir(base_dir)
  if (!dir.exists(dir_path)) dir.create(dir_path, recursive = TRUE, showWarnings = FALSE)
  dir_path
}

.studyAgentSlashReadStepState <- function(base_dir, step_id) {
  path <- .studyAgentSlashStepStatePath(base_dir, step_id)
  if (!file.exists(path)) return(NULL)
  .studyAgentSlashReadProjectJson(path)
}

.studyAgentSlashWriteStepState <- function(base_dir,
                                           step_id,
                                           status,
                                           started_at = NULL,
                                           finished_at = NULL,
                                           parameters = list(),
                                           artifacts = list(required = list(), optional = list()),
                                           summary = list(),
                                           error = NULL,
                                           upstream_fingerprint = list()) {
  .studyAgentSlashEnsureStepStateDir(base_dir)
  now <- .studyAgentSlashNowTimestamp()
  existing <- .studyAgentSlashReadStepState(base_dir, step_id) %||% list()
  payload <- list(
    step_id = as.character(step_id),
    status = as.character(status %||% "not_started"),
    started_at = started_at %||% existing$started_at %||% if (identical(status, "running")) now else NULL,
    finished_at = finished_at %||% if (identical(status, "running")) NULL else now,
    updated_at = now,
    parameters = parameters %||% list(),
    artifacts = list(
      required = as.list(as.character(unlist((artifacts$required %||% list()), use.names = FALSE))),
      optional = as.list(as.character(unlist((artifacts$optional %||% list()), use.names = FALSE)))
    ),
    summary = summary %||% list(),
    error = if (is.null(error) || !nzchar(trimws(as.character(error)))) NULL else as.character(error),
    upstream_fingerprint = upstream_fingerprint %||% list()
  )
  .studyAgentSlashWriteProjectJson(payload, .studyAgentSlashStepStatePath(base_dir, step_id))
  invisible(payload)
}

.studyAgentSlashDeleteStepState <- function(base_dir, step_id) {
  path <- .studyAgentSlashStepStatePath(base_dir, step_id)
  if (file.exists(path)) unlink(path, force = TRUE)
  invisible(path)
}

.studyAgentSlashBackupRoot <- function(base_dir) {
  file.path(base_dir, "outputs", "state-backups")
}

.studyAgentSlashSnapshotId <- function(label = NULL) {
  stamp <- format(as.POSIXct(Sys.time(), tz = "UTC"), "%Y%m%dT%H%M%SZ", tz = "UTC")
  label <- trimws(as.character(label %||% ""))
  if (!nzchar(label)) return(stamp)
  label <- gsub("[^A-Za-z0-9._-]+", "-", label)
  sprintf("%s-%s", stamp, label)
}

.studyAgentSlashCopyPathInto <- function(path, destination_root, base_dir) {
  absolute_path <- .studyAgentSlashResolveProjectPath(path, base_dir)
  if (!file.exists(absolute_path)) return(FALSE)
  relative_path <- .studyAgentSlashRelativizeProjectPath(absolute_path, base_dir)
  destination_path <- file.path(destination_root, relative_path)
  parent_dir <- dirname(destination_path)
  if (!dir.exists(parent_dir)) dir.create(parent_dir, recursive = TRUE, showWarnings = FALSE)
  file.copy(absolute_path, destination_path, recursive = TRUE, overwrite = TRUE)
}

.studyAgentSlashBackupWorkflowState <- function(base_dir,
                                                label = NULL,
                                                include_paths = character(0)) {
  root <- .studyAgentSlashBackupRoot(base_dir)
  if (!dir.exists(root)) dir.create(root, recursive = TRUE, showWarnings = FALSE)
  snapshot_id <- .studyAgentSlashSnapshotId(label)
  snapshot_dir <- file.path(root, snapshot_id)
  dir.create(snapshot_dir, recursive = TRUE, showWarnings = FALSE)

  project_path <- .studyAgentSlashProjectStatePath(base_dir)
  runtime_path <- .studyAgentSlashRuntimeStatePath(base_dir)
  step_state_dir <- .studyAgentSlashStepStateDir(base_dir)
  state_dir <- file.path(snapshot_dir, "state")
  dir.create(state_dir, recursive = TRUE, showWarnings = FALSE)

  if (file.exists(project_path)) file.copy(project_path, file.path(state_dir, "study-agent-project.json"), overwrite = TRUE)
  if (file.exists(runtime_path)) file.copy(runtime_path, file.path(state_dir, "study_agent_runtime_state.json"), overwrite = TRUE)
  if (dir.exists(step_state_dir)) file.copy(step_state_dir, file.path(state_dir, "step-state"), recursive = TRUE, overwrite = TRUE)

  include_paths <- unique(as.character(include_paths %||% character(0)))
  artifact_root <- file.path(snapshot_dir, "artifacts")
  copied <- character(0)
  if (length(include_paths) > 0) {
    dir.create(artifact_root, recursive = TRUE, showWarnings = FALSE)
    for (path in include_paths) {
      if (!nzchar(path)) next
      if (isTRUE(.studyAgentSlashCopyPathInto(path, artifact_root, base_dir))) {
        copied <- c(copied, path)
      }
    }
  }

  manifest <- list(
    snapshot_id = snapshot_id,
    created_at = .studyAgentSlashNowTimestamp(),
    base_dir = normalizePath(base_dir, winslash = "/", mustWork = FALSE),
    included_artifacts = as.list(copied)
  )
  .studyAgentSlashWriteProjectJson(manifest, file.path(snapshot_dir, "manifest.json"))
  invisible(list(snapshot_id = snapshot_id, snapshot_dir = snapshot_dir, included_artifacts = copied))
}

.studyAgentSlashListWorkflowBackups <- function(base_dir) {
  root <- .studyAgentSlashBackupRoot(base_dir)
  if (!dir.exists(root)) return(character(0))
  entries <- list.dirs(root, full.names = FALSE, recursive = FALSE)
  entries[nzchar(entries)]
}

.studyAgentSlashRestoreWorkflowState <- function(base_dir,
                                                 snapshot_id,
                                                 restore_artifacts = TRUE,
                                                 backup_current = TRUE) {
  snapshot_id <- trimws(as.character(snapshot_id %||% ""))
  if (!nzchar(snapshot_id)) stop("Provide a non-empty snapshot_id.")
  snapshot_dir <- file.path(.studyAgentSlashBackupRoot(base_dir), snapshot_id)
  if (!dir.exists(snapshot_dir)) stop("Workflow snapshot not found: ", snapshot_dir)
  if (isTRUE(backup_current)) {
    .studyAgentSlashBackupWorkflowState(base_dir, label = sprintf("pre-restore-%s", snapshot_id))
  }

  state_dir <- file.path(snapshot_dir, "state")
  project_src <- file.path(state_dir, "study-agent-project.json")
  runtime_src <- file.path(state_dir, "study_agent_runtime_state.json")
  step_state_src <- file.path(state_dir, "step-state")

  if (file.exists(project_src)) file.copy(project_src, .studyAgentSlashProjectStatePath(base_dir), overwrite = TRUE)
  if (file.exists(runtime_src)) file.copy(runtime_src, .studyAgentSlashRuntimeStatePath(base_dir), overwrite = TRUE)
  step_state_dest <- .studyAgentSlashStepStateDir(base_dir)
  if (dir.exists(step_state_dest)) unlink(step_state_dest, recursive = TRUE, force = TRUE)
  if (dir.exists(step_state_src)) file.copy(step_state_src, step_state_dest, recursive = TRUE, overwrite = TRUE)

  if (isTRUE(restore_artifacts)) {
    artifact_root <- file.path(snapshot_dir, "artifacts")
    if (dir.exists(artifact_root)) {
      for (path in list.files(artifact_root, full.names = TRUE, recursive = TRUE, all.files = TRUE, no.. = TRUE)) {
        rel <- sub(paste0("^", gsub("([.|()\\^{}+$*?]|\\[|\\])", "\\\\\\1", normalizePath(artifact_root, winslash = "/", mustWork = FALSE)), "/?"), "", normalizePath(path, winslash = "/", mustWork = FALSE))
        if (!nzchar(rel)) next
        dest <- file.path(base_dir, rel)
        parent_dir <- dirname(dest)
        if (!dir.exists(parent_dir)) dir.create(parent_dir, recursive = TRUE, showWarnings = FALSE)
        file.copy(path, dest, recursive = TRUE, overwrite = TRUE)
      }
    }
  }

  invisible(.studyAgentSlashReconcileProjectState(base_dir, write = TRUE))
}

.studyAgentSlashStepLegacyStatePath <- function(base_dir, workflow_type, step_id) {
  if (identical(step_id, "keeper_concept_sets")) return(file.path(base_dir, "outputs", "keeper_concept_set_state.json"))
  if (identical(step_id, "keeper_case_review")) return(file.path(base_dir, "outputs", "keeper_case_review_state.json"))
  if (identical(step_id, "recommend_and_select") && identical(workflow_type, "strategus_cohort_methods")) {
    return(file.path(base_dir, "outputs", "cohort_methods_intent_split.json"))
  }
  if (identical(step_id, "recommend_and_select") && identical(workflow_type, "strategus_incidence")) {
    return(file.path(base_dir, "outputs", "intent_split.json"))
  }
  NULL
}


.studyAgentSlashExecutionArtifactPaths <- function(base_dir, project_state = NULL) {
  roots <- .studyAgentSlashConfiguredExecutionRoots(base_dir, project_state = project_state, prefer_confirmed = TRUE)
  resolved <- unique(Filter(nzchar, trimws(as.character(c(
    roots$results_root %||% "",
    roots$work_root %||% ""
  )))))
  unique(vapply(resolved, function(path) {
    .studyAgentSlashRelativizeProjectPath(path, base_dir)
  }, character(1)))
}

.studyAgentSlashStepOverrideArtifacts <- function(project_state, base_dir, step_id) {
  step_id <- as.character(step_id %||% "")
  override_paths <- character(0)
  workflow_type <- as.character(project_state$workflow_type %||% "")
  legacy_path <- .studyAgentSlashStepLegacyStatePath(base_dir, workflow_type, step_id)
  if (!is.null(legacy_path) && nzchar(legacy_path) && file.exists(legacy_path)) {
    override_paths <- c(override_paths, .studyAgentSlashRelativizeProjectPath(legacy_path, base_dir))
  }
  if (identical(step_id, "keeper_case_review")) {
    override_paths <- c(
      override_paths,
      "keeper-case-review/rows",
      "keeper-case-review/reviews"
    )
  }
  if (identical(step_id, "keeper_concept_sets")) {
    override_paths <- c(
      override_paths,
      "keeper-case-review/concept-sets-generated",
      "keeper-case-review/concept-sets-approved"
    )
  }
  if (identical(step_id, "diagnostics")) {
    override_paths <- c(override_paths, .studyAgentSlashExecutionArtifactPaths(base_dir, project_state = project_state))
  }
  if (step_id %in% c("cm_spec", "incidence_spec")) {
    # A Strategus specification is complete when its durable, workflow-local
    # execution record is available. Configured results/work roots are useful
    # for discovery, but may be external or cleaned up after a successful run.
    override_paths <- c(
      override_paths,
      "analysis-settings/strategus_execute_result.rds",
      "analysis-settings/strategus_execute_summary.json"
    )
  }
  unique(override_paths[nzchar(override_paths)])
}

.studyAgentSlashStepRequiredArtifacts <- function(project_state, base_dir, step_id, step_state = NULL) {
  step_state <- step_state %||% .studyAgentSlashReadStepState(base_dir, step_id)
  override_paths <- .studyAgentSlashStepOverrideArtifacts(project_state, base_dir, step_id)
  required_from_state <- as.character(unlist((step_state$artifacts %||% list())$required %||% list(), use.names = FALSE))
  required_from_state <- unique(required_from_state[nzchar(required_from_state)])
  if (length(override_paths) > 0) {
    filtered_state <- setdiff(required_from_state, c("results", "work", "cm-results", "cm-diagnostics"))
    return(unique(c(override_paths, filtered_state)))
  }
  if (length(required_from_state) > 0) return(required_from_state)

  artifact_paths <- vapply(Filter(function(item) {
    identical(as.character(item$step_id %||% ""), as.character(step_id)) &&
      !identical(as.character(item$type %||% ""), "script")
  }, project_state$artifacts %||% list()), function(item) {
    as.character(item$path %||% "")
  }, character(1))

  unique(c(override_paths, artifact_paths[nzchar(artifact_paths)]))
}

.studyAgentSlashStepOwnedArtifacts <- function(project_state, base_dir, step_id) {
  required <- unique(.studyAgentSlashStepRequiredArtifacts(project_state, base_dir, step_id))
  base_dir_norm <- normalizePath(base_dir, winslash = "/", mustWork = FALSE)
  base_prefix <- paste0(base_dir_norm, "/")
  Filter(function(path) {
    absolute_path <- .studyAgentSlashResolveProjectPath(path, base_dir)
    identical(absolute_path, base_dir_norm) || startsWith(absolute_path, base_prefix)
  }, required)
}

.studyAgentSlashReadLegacyStepStatus <- function(base_dir, workflow_type, step_id) {
  legacy_path <- .studyAgentSlashStepLegacyStatePath(base_dir, workflow_type, step_id)
  if (is.null(legacy_path) || !file.exists(legacy_path)) return(NULL)
  if (!grepl("\\.json$", legacy_path)) return(list(status = "completed", error = NULL))
  payload <- tryCatch(.studyAgentSlashReadProjectJson(legacy_path), error = function(e) NULL)
  if (is.null(payload)) return(NULL)
  raw_status <- as.character(payload$status %||% "")
  if (identical(raw_status, "ok")) return(list(status = "completed", error = NULL))
  if (identical(raw_status, "error")) return(list(status = "failed", error = as.character(payload$message %||% payload$error %||% "")))
  NULL
}

.studyAgentSlashDependenciesSatisfiedByStatus <- function(project_state, statuses, step) {
  deps <- as.character(unlist(step$depends_on %||% character(0), use.names = FALSE))
  if (length(deps) == 0) return(TRUE)
  for (dep in deps) {
    dep_status <- as.character(statuses[[dep]] %||% "not_started")
    if (!(dep_status %in% c("completed", "completed_with_failures", "skipped"))) return(FALSE)
  }
  TRUE
}

.studyAgentSlashResolveDerivedWorkflowStatuses <- function(base_dir, project_state = NULL) {
  project_state <- project_state %||% .studyAgentSlashReadProjectState(base_dir)
  workflow_type <- as.character(project_state$workflow_type %||% "")
  statuses <- list()
  errors <- list()

  for (step in project_state$execution_plan %||% list()) {
    step_id <- as.character(step$step_id %||% "")
    step_state <- .studyAgentSlashReadStepState(base_dir, step_id)
    status <- as.character((step_state %||% list())$status %||% "")
    error <- as.character((step_state %||% list())$error %||% "")
    if (!nzchar(status)) {
      legacy <- .studyAgentSlashReadLegacyStepStatus(base_dir, workflow_type, step_id)
      status <- as.character((legacy %||% list())$status %||% "")
      error <- as.character((legacy %||% list())$error %||% error)
    }
    if (!nzchar(status)) {
      status <- as.character(step$status %||% "not_started")
      error <- as.character(step$error %||% error)
    }

    deps_ok <- .studyAgentSlashDependenciesSatisfiedByStatus(project_state, statuses, step)
    required <- .studyAgentSlashStepRequiredArtifacts(project_state, base_dir, step_id, step_state = step_state)
    required_exists <- if (length(required) == 0) TRUE else all(vapply(required, function(path) {
      isTRUE(file.exists(.studyAgentSlashResolveProjectPath(path, base_dir)))
    }, logical(1)))

    derived_status <- status
    if (derived_status %in% c("completed", "ok", "completed_with_failures")) {
      target_status <- if (identical(derived_status, "completed_with_failures")) "completed_with_failures" else "completed"
      derived_status <- if (isTRUE(deps_ok) && isTRUE(required_exists)) target_status else "stale"
    } else if (derived_status %in% c("failed", "error")) {
      derived_status <- "failed"
    } else if (identical(derived_status, "running")) {
      derived_status <- "running"
    } else if (identical(derived_status, "skipped")) {
      derived_status <- "skipped"
    } else {
      derived_status <- if (isTRUE(deps_ok)) "not_started" else "blocked"
    }

    statuses[[step_id]] <- derived_status
    errors[[step_id]] <- if (!nzchar(error)) NULL else error
  }

  list(statuses = statuses, errors = errors)
}

.studyAgentSlashReconcileProjectState <- function(base_dir,
                                                  project_state = NULL,
                                                  runtime_state = NULL,
                                                  write = FALSE) {
  project_state <- project_state %||% .studyAgentSlashReadProjectState(base_dir)
  runtime_state <- runtime_state %||% if (file.exists(.studyAgentSlashRuntimeStatePath(base_dir))) .studyAgentSlashReadRuntimeState(base_dir) else .studyAgentSlashNewRuntimeState(project_state)
  resolved <- .studyAgentSlashResolveDerivedWorkflowStatuses(base_dir, project_state = project_state)
  statuses <- resolved$statuses %||% list()
  errors <- resolved$errors %||% list()

  for (i in seq_along(project_state$execution_plan %||% list())) {
    step <- project_state$execution_plan[[i]]
    step_id <- as.character(step$step_id %||% "")
    step$status <- as.character(statuses[[step_id]] %||% step$status %||% "not_started")
    step$error <- errors[[step_id]] %||% NULL
    if (identical(step$status, "not_started") || identical(step$status, "blocked")) step$error <- NULL
    project_state$execution_plan[[i]] <- step
  }

  project_state <- .studyAgentSlashAdvanceResumePointer(project_state)
  runtime_state$current_step <- project_state$resume$current_step_id %||% NULL
  runtime_state <- .studyAgentSlashUpdateArtifactDetection(runtime_state, project_state, base_dir)

  if (isTRUE(write)) {
    .studyAgentSlashWriteProjectState(project_state, base_dir)
    .studyAgentSlashWriteRuntimeState(runtime_state, base_dir)
  }
  list(project_state = project_state, runtime_state = runtime_state, statuses = statuses)
}

.studyAgentSlashWorkflowDownstreamStepIds <- function(project_state, step_id) {
  step_id <- as.character(step_id %||% "")
  if (!nzchar(step_id)) return(character(0))
  remaining <- step_id
  discovered <- character(0)
  repeat {
    next_steps <- character(0)
    for (step in project_state$execution_plan %||% list()) {
      current_id <- as.character(step$step_id %||% "")
      deps <- as.character(unlist(step$depends_on %||% character(0), use.names = FALSE))
      if (current_id %in% c(step_id, discovered)) next
      if (length(intersect(deps, c(step_id, discovered))) > 0) {
        next_steps <- c(next_steps, current_id)
      }
    }
    next_steps <- unique(next_steps)
    if (length(next_steps) == 0) break
    discovered <- unique(c(discovered, next_steps))
  }
  discovered
}

.studyAgentSlashResetWorkflowStepState <- function(base_dir,
                                                   step_id,
                                                   cascade = TRUE,
                                                   backup = TRUE,
                                                   delete_outputs = TRUE) {
  step_id <- as.character(step_id %||% "")
  if (!nzchar(step_id)) stop("Provide a non-empty step_id.")
  reconciled <- .studyAgentSlashReconcileProjectState(base_dir, write = FALSE)
  project_state <- reconciled$project_state
  runtime_state <- reconciled$runtime_state
  step <- .studyAgentSlashFindPlanStep(project_state, step_id)
  if (is.null(step)) stop(sprintf("Unknown workflow step: %s", step_id))

  affected_steps <- step_id
  if (isTRUE(cascade)) {
    affected_steps <- unique(c(affected_steps, .studyAgentSlashWorkflowDownstreamStepIds(project_state, step_id)))
  }

  owned_artifacts <- unique(unlist(lapply(affected_steps, function(id) {
    .studyAgentSlashStepOwnedArtifacts(project_state, base_dir, id)
  }), use.names = FALSE))

  backup_info <- NULL
  if (isTRUE(backup)) {
    backup_info <- .studyAgentSlashBackupWorkflowState(
      base_dir,
      label = sprintf("reset-%s", step_id),
      include_paths = if (isTRUE(delete_outputs)) owned_artifacts else character(0)
    )
  }

  for (id in affected_steps) {
    .studyAgentSlashDeleteStepState(base_dir, id)
    if (is.null(runtime_state$step_status) || !is.list(runtime_state$step_status)) {
      runtime_state$step_status <- list()
    }
    runtime_state$step_status[[as.character(id)]] <- NULL
    project_state <- .studyAgentSlashSetProjectStepStatus(project_state, id, "not_started", error = NULL)
  }

  if (isTRUE(delete_outputs)) {
    for (path in owned_artifacts) {
      absolute_path <- .studyAgentSlashResolveProjectPath(path, base_dir)
      if (file.exists(absolute_path) || dir.exists(absolute_path)) {
        unlink(absolute_path, recursive = TRUE, force = TRUE)
      }
    }
  }

  project_state <- .studyAgentSlashRefreshProjectArtifactsAfterStep(project_state, base_dir)
  project_state <- .studyAgentSlashAdvanceResumePointer(project_state)
  runtime_state$current_step <- project_state$resume$current_step_id %||% NULL
  runtime_state$last_error <- NULL
  runtime_state <- .studyAgentSlashUpdateArtifactDetection(runtime_state, project_state, base_dir)
  .studyAgentSlashWriteProjectState(project_state, base_dir)
  .studyAgentSlashWriteRuntimeState(runtime_state, base_dir)
  invisible(c(
    list(
      step_id = step_id,
      affected_steps = as.list(affected_steps),
      deleted_artifacts = as.list(owned_artifacts)
    ),
    backup_info
  ))
}
