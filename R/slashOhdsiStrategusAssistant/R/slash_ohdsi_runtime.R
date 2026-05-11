.studyAgentSlashCreateAcpClient <- function(url = "http://127.0.0.1:8765", token = NULL, check = TRUE) {
  slashOhdsiAcpClient::acp_client(url = url, token = token, check = check)
}

.studyAgentSlashAcpIsConnected <- function(client) {
  isTRUE(slashOhdsiAcpClient::acp_is_connected(client))
}

.studyAgentSlashCallAcpFlow <- function(client, flow_name, body = list()) {
  slashOhdsiAcpClient::acp_call_flow(client = client, flow_name = flow_name, body = body)
}

.studyAgentSlashNewWorkflowStageContext <- function(...) {
  new_workflow_stage_context(...)
}

.studyAgentSlashCompactWorkflowDialogueContext <- function(value) {
  compact_workflow_dialogue_context(value)
}

.studyAgentSlashNewWorkflowDialogueSession <- function(...) {
  new_workflow_dialogue_session(...)
}

.studyAgentSlashNormalizeIncidenceDialogueStep <- function(step) {
  normalize_incidence_dialogue_step(step)
}

.studyAgentSlashIncidenceDialogueStepLabel <- function(step, role = "") {
  incidence_dialogue_step_label(step = step, role = role)
}

.studyAgentSlashBuildIncidenceWorkflowStageContext <- function(study_intent, dialogue_state, interactive = TRUE) {
  build_incidence_workflow_stage_context(
    study_intent = study_intent,
    dialogue_state = dialogue_state,
    interactive = interactive
  )
}

.studyAgentSlashNormalizeCohortMethodsDialogueStep <- function(step) {
  normalize_cohort_methods_dialogue_step(step)
}

.studyAgentSlashCohortMethodsDialogueStepLabel <- function(step, role = "") {
  cohort_methods_dialogue_step_label(step = step, role = role)
}

.studyAgentSlashBuildCohortMethodsWorkflowStageContext <- function(study_intent, dialogue_state, interactive = TRUE) {
  build_cohort_methods_workflow_stage_context(
    study_intent = study_intent,
    dialogue_state = dialogue_state,
    interactive = interactive
  )
}

.studyAgentSlashWorkflowContextDialogue <- function(client, stage_context, message) {
  slashOhdsiAcpClient::acp_workflow_context_dialogue(
    client = client,
    stage_context = stage_context,
    message = message
  )
}
