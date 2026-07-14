.studyAgentSlashCreateAcpClient <- function(url = "http://127.0.0.1:8765", token = NULL, check = TRUE) {
  slashOhdsiAcpClient::acp_client(url = url, token = token, check = check)
}

.studyAgentSlashAcpIsConnected <- function(client) {
  isTRUE(slashOhdsiAcpClient::acp_is_connected(client))
}

.studyAgentSlashCallAcpFlow <- function(client, flow_name, body = list()) {
  slashOhdsiAcpClient::acp_call_flow(client = client, flow_name = flow_name, body = body)
}

.studyAgentSlashAcpKeeperConceptSetsGenerate <- function(client,
                                                         phenotype,
                                                         domain_keys = NULL,
                                                         vocab_search_provider = NULL,
                                                         phoebe_provider = NULL,
                                                         candidate_limit = 5,
                                                         min_record_count = NULL,
                                                         include_diagnostics = TRUE) {
  slashOhdsiAcpClient::acp_keeper_concept_sets_generate(
    client = client,
    phenotype = phenotype,
    domain_keys = domain_keys,
    vocab_search_provider = vocab_search_provider,
    phoebe_provider = phoebe_provider,
    candidate_limit = candidate_limit,
    min_record_count = min_record_count,
    include_diagnostics = include_diagnostics
  )
}

.studyAgentSlashAcpKeeperProfilesGenerate <- function(client,
                                                      cohort_database_schema,
                                                      cohort_table,
                                                      cohort_definition_id,
                                                      cdm_database_schema,
                                                      keeper_concept_sets = NULL,
                                                      keeper_concept_sets_path = NULL,
                                                      sample_size = 20,
                                                      person_ids = NULL,
                                                      phenotype_name = NULL,
                                                      use_descendants = TRUE,
                                                      remove_pii = TRUE) {
  slashOhdsiAcpClient::acp_keeper_profiles_generate(
    client = client,
    cohort_database_schema = cohort_database_schema,
    cohort_table = cohort_table,
    cohort_definition_id = cohort_definition_id,
    cdm_database_schema = cdm_database_schema,
    keeper_concept_sets = keeper_concept_sets,
    keeper_concept_sets_path = keeper_concept_sets_path,
    sample_size = sample_size,
    person_ids = person_ids,
    phenotype_name = phenotype_name,
    use_descendants = use_descendants,
    remove_pii = remove_pii
  )
}

.studyAgentSlashAcpPhenotypeValidationReview <- function(client,
                                                            disease_name,
                                                            keeper_row = NULL,
                                                            keeper_row_path = NULL,
                                                            row_index = NULL) {
  slashOhdsiAcpClient::acp_phenotype_validation_review(
    client = client,
    disease_name = disease_name,
    keeper_row = keeper_row,
    keeper_row_path = keeper_row_path,
    row_index = row_index
  )
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

.studyAgentSlashWorkflowBuildHelpLines <- function(workflow_type, step, role = "", context = list()) {
  workflow_build_help_lines(
    workflow_type = workflow_type,
    step = step,
    role = role,
    context = context
  )
}

.studyAgentSlashWorkflowContextDialogue <- function(client, stage_context, message) {
  slashOhdsiAcpClient::acp_workflow_context_dialogue(
    client = client,
    stage_context = stage_context,
    message = message
  )
}
