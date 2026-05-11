.studyAgentSlashBridgeState <- local({
  env <- new.env(parent = emptyenv())
  env$acp_env <- NULL
  env$strategus_env <- NULL
  env
})

.studyAgentRepoRoot <- function() {
  candidates <- unique(c(
    Sys.getenv("STUDY_AGENT_BASE_DIR", unset = ""),
    getwd(),
    file.path(getwd(), "OHDSI-Study-Agent"),
    normalizePath(file.path(getwd(), "..", ".."), winslash = "/", mustWork = FALSE)
  ))
  candidates <- candidates[nzchar(candidates)]
  for (candidate in candidates) {
    if (dir.exists(file.path(candidate, "R", "slashOhdsiAcpClient")) &&
        dir.exists(file.path(candidate, "R", "slashOhdsiStrategusAssistant"))) {
      return(normalizePath(candidate, winslash = "/", mustWork = FALSE))
    }
  }
  stop("Could not locate repo root for slash-ohdsi bridge helpers.")
}

.studyAgentSourcePackageDir <- function(package_dir) {
  env <- new.env(parent = baseenv())
  r_dir <- file.path(package_dir, "R")
  files <- list.files(r_dir, pattern = "\\.[Rr]$", full.names = TRUE)
  for (path in sort(files)) {
    sys.source(path, envir = env)
  }
  env
}

.studyAgentSlashAcpEnv <- function() {
  if (!is.null(.studyAgentSlashBridgeState$acp_env)) {
    return(.studyAgentSlashBridgeState$acp_env)
  }
  repo_root <- .studyAgentRepoRoot()
  env <- .studyAgentSourcePackageDir(file.path(repo_root, "R", "slashOhdsiAcpClient"))
  .studyAgentSlashBridgeState$acp_env <- env
  env
}

.studyAgentSlashStrategusEnv <- function() {
  if (!is.null(.studyAgentSlashBridgeState$strategus_env)) {
    return(.studyAgentSlashBridgeState$strategus_env)
  }
  repo_root <- .studyAgentRepoRoot()
  env <- .studyAgentSourcePackageDir(file.path(repo_root, "R", "slashOhdsiStrategusAssistant"))
  .studyAgentSlashBridgeState$strategus_env <- env
  env
}

.studyAgentSlashCreateAcpClient <- function(url = "http://127.0.0.1:8765", token = NULL, check = TRUE) {
  env <- .studyAgentSlashAcpEnv()
  env$acp_client(url = url, token = token, check = check)
}

.studyAgentSlashAcpIsConnected <- function(client) {
  env <- .studyAgentSlashAcpEnv()
  isTRUE(env$acp_is_connected(client))
}

.studyAgentSlashCallAcpFlow <- function(client, flow_name, body = list()) {
  env <- .studyAgentSlashAcpEnv()
  env$acp_call_flow(client = client, flow_name = flow_name, body = body)
}

.studyAgentSlashNewWorkflowStageContext <- function(...) {
  env <- .studyAgentSlashStrategusEnv()
  env$new_workflow_stage_context(...)
}

.studyAgentSlashCompactWorkflowDialogueContext <- function(value) {
  env <- .studyAgentSlashStrategusEnv()
  env$compact_workflow_dialogue_context(value)
}

.studyAgentSlashNewWorkflowDialogueSession <- function(...) {
  env <- .studyAgentSlashStrategusEnv()
  env$new_workflow_dialogue_session(...)
}

.studyAgentSlashNormalizeIncidenceDialogueStep <- function(step) {
  env <- .studyAgentSlashStrategusEnv()
  env$normalize_incidence_dialogue_step(step)
}

.studyAgentSlashIncidenceDialogueStepLabel <- function(step, role = "") {
  env <- .studyAgentSlashStrategusEnv()
  env$incidence_dialogue_step_label(step = step, role = role)
}

.studyAgentSlashBuildIncidenceWorkflowStageContext <- function(study_intent, dialogue_state, interactive = TRUE) {
  env <- .studyAgentSlashStrategusEnv()
  env$build_incidence_workflow_stage_context(
    study_intent = study_intent,
    dialogue_state = dialogue_state,
    interactive = interactive
  )
}

.studyAgentSlashNormalizeCohortMethodsDialogueStep <- function(step) {
  env <- .studyAgentSlashStrategusEnv()
  env$normalize_cohort_methods_dialogue_step(step)
}

.studyAgentSlashCohortMethodsDialogueStepLabel <- function(step, role = "") {
  env <- .studyAgentSlashStrategusEnv()
  env$cohort_methods_dialogue_step_label(step = step, role = role)
}

.studyAgentSlashBuildCohortMethodsWorkflowStageContext <- function(study_intent, dialogue_state, interactive = TRUE) {
  env <- .studyAgentSlashStrategusEnv()
  env$build_cohort_methods_workflow_stage_context(
    study_intent = study_intent,
    dialogue_state = dialogue_state,
    interactive = interactive
  )
}

.studyAgentSlashWorkflowContextDialogue <- function(client, stage_context, message) {
  env <- .studyAgentSlashAcpEnv()
  env$acp_workflow_context_dialogue(
    client = client,
    stage_context = stage_context,
    message = message
  )
}
