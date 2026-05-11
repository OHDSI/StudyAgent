#' Call phenotype recommendation flow
#' @param client ACP client object
#' @param study_intent non-empty study intent string
#' @param top_k number of candidates to retrieve
#' @param max_results maximum recommendations to return
#' @param candidate_limit optional candidate limit forwarded to ACP
#' @return parsed ACP response
#' @export
acp_suggest_phenotypes <- function(client,
                                   study_intent,
                                   top_k = 20,
                                   max_results = 10,
                                   candidate_limit = NULL) {
  if (is.null(study_intent) || !nzchar(trimws(as.character(study_intent)))) {
    stop("Provide a non-empty study_intent.")
  }
  body <- list(
    study_intent = trimws(as.character(study_intent)),
    top_k = top_k,
    max_results = max_results
  )
  if (!is.null(candidate_limit)) body$candidate_limit <- candidate_limit
  acp_call_flow(client, "phenotype_recommendation", body)
}

#' Call phenotype recommendation advice flow
#' @param client ACP client object
#' @param study_intent non-empty study intent string
#' @return parsed ACP response
#' @export
acp_phenotype_recommendation_advice <- function(client, study_intent) {
  if (is.null(study_intent) || !nzchar(trimws(as.character(study_intent)))) {
    stop("Provide a non-empty study_intent.")
  }
  acp_call_flow(client, "phenotype_recommendation_advice", list(study_intent = trimws(as.character(study_intent))))
}

#' Call phenotype improvements flow
#' @param client ACP client object
#' @param protocol_path path to protocol markdown or text
#' @param cohort_paths cohort JSON paths
#' @return parsed ACP response
#' @export
acp_review_phenotypes <- function(client, protocol_path, cohort_paths) {
  cohort_paths <- as.character(cohort_paths %||% character(0))
  if (!length(cohort_paths)) stop("Provide at least one cohort path.")
  body <- list(
    protocol_path = normalizePath(protocol_path, winslash = "/", mustWork = FALSE),
    cohort_paths = as.list(unname(vapply(cohort_paths, normalizePath, character(1), winslash = "/", mustWork = FALSE)))
  )
  acp_call_flow(client, "phenotype_improvements", body)
}

#' Call cohort methods intent split flow
#' @param client ACP client object
#' @param study_intent non-empty study intent string
#' @return parsed ACP response
#' @export
acp_cohort_methods_intent_split <- function(client, study_intent) {
  if (is.null(study_intent) || !nzchar(trimws(as.character(study_intent)))) {
    stop("Provide a non-empty study_intent.")
  }
  acp_call_flow(client, "cohort_methods_intent_split", list(study_intent = trimws(as.character(study_intent))))
}

#' Call cohort methods specification recommendation flow
#' @param client ACP client object
#' @param study_intent protocol context string
#' @param analytic_settings_description free-text analytic settings description
#' @return parsed ACP response
#' @export
acp_suggest_cohort_method_specs <- function(client,
                                            study_intent,
                                            analytic_settings_description) {
  if (is.null(study_intent) || !nzchar(trimws(as.character(study_intent)))) {
    stop("Provide a non-empty study_intent.")
  }
  if (is.null(analytic_settings_description) || !nzchar(trimws(as.character(analytic_settings_description)))) {
    stop("Provide a non-empty analytic_settings_description.")
  }
  body <- list(
    study_intent = trimws(as.character(study_intent)),
    study_description = trimws(as.character(analytic_settings_description)),
    analytic_settings_description = trimws(as.character(analytic_settings_description))
  )
  acp_call_flow(client, "cohort_methods_specifications_recommendation", body)
}

#' Call workflow context dialogue flow
#' @param client ACP client object
#' @param stage_context workflow-stage context object
#' @param message latest user message
#' @return parsed ACP response
.flatten_workflow_context_dialogue_payload <- function(stage_context, message) {
  if (!is.list(stage_context)) stop("stage_context must be a list.")
  if (is.null(message) || !nzchar(trimws(as.character(message)))) {
    stop("Provide a non-empty message.")
  }

  dialogue <- stage_context$dialogue %||% list()
  current_context <- stage_context$legacy_context %||% list()
  if (!is.list(current_context)) current_context <- list()

  current_context$contract_version <- current_context$contract_version %||% stage_context$contract_version %||% NULL
  current_context$step_label <- current_context$step_label %||% stage_context$step_label %||% NULL
  current_context$entities <- current_context$entities %||% stage_context$entities %||% list()
  current_context$available_artifacts <- current_context$available_artifacts %||% stage_context$available_artifacts %||% list()
  current_context$prior_questions <- current_context$prior_questions %||% dialogue$prior_questions %||% list()
  current_context$prior_answers <- current_context$prior_answers %||% dialogue$prior_answers %||% list()
  current_context$constraints <- current_context$constraints %||% stage_context$constraints %||% list()

  current_role <- current_context$active_role %||% (stage_context$entities %||% list())$active_role %||% ""

  list(
    user_prompt = trimws(as.character(message)),
    study_intent = trimws(as.character(stage_context$user_goal %||% "")),
    workflow_type = trimws(as.character(stage_context$workflow_type %||% "")),
    current_step = trimws(as.character(stage_context$current_step %||% "")),
    current_role = trimws(as.character(current_role)),
    current_context = .normalize_acp_body(current_context)
  )
}

#' @export
acp_workflow_context_dialogue <- function(client, stage_context, message) {
  body <- .flatten_workflow_context_dialogue_payload(stage_context = stage_context, message = message)
  acp_call_flow(client, "workflow_context_dialogue", body)
}

#' Call keeper concept set generation flow
#' @param client ACP client object
#' @param phenotype phenotype label
#' @param domain_keys optional character vector of domain keys
#' @param vocab_search_provider optional vocabulary search provider override
#' @param phoebe_provider optional related-concepts provider override
#' @param candidate_limit candidate limit
#' @param min_record_count optional minimum record count filter
#' @param include_diagnostics whether to request diagnostics
#' @return parsed ACP response
#' @export
acp_keeper_concept_sets_generate <- function(client,
                                             phenotype,
                                             domain_keys = NULL,
                                             vocab_search_provider = NULL,
                                             phoebe_provider = NULL,
                                             candidate_limit = 5,
                                             min_record_count = NULL,
                                             include_diagnostics = TRUE) {
  if (is.null(phenotype) || !nzchar(trimws(as.character(phenotype)))) {
    stop("Provide a non-empty phenotype.")
  }
  domain_keys <- as.character(domain_keys %||% character(0))
  body <- list(
    phenotype = trimws(as.character(phenotype)),
    candidate_limit = candidate_limit,
    include_diagnostics = isTRUE(include_diagnostics)
  )
  if (length(domain_keys)) body$domain_keys <- as.list(domain_keys)
  if (!is.null(vocab_search_provider) && nzchar(trimws(as.character(vocab_search_provider)))) {
    body$vocab_search_provider <- trimws(as.character(vocab_search_provider))
  }
  if (!is.null(phoebe_provider) && nzchar(trimws(as.character(phoebe_provider)))) {
    body$phoebe_provider <- trimws(as.character(phoebe_provider))
  }
  if (!is.null(min_record_count)) body$min_record_count <- as.numeric(min_record_count)
  acp_call_flow(client, "keeper_concept_sets_generate", body)
}

#' Call keeper profile generation flow
#' @param client ACP client object
#' @param cohort_database_schema cohort results schema
#' @param cohort_table cohort table name
#' @param cohort_definition_id cohort definition ID to sample from
#' @param cdm_database_schema CDM schema
#' @param keeper_concept_sets list of normalized Keeper concept-set rows
#' @param sample_size requested sample size
#' @param person_ids optional character vector of person IDs to restrict to
#' @param phenotype_name optional phenotype label for output metadata
#' @param use_descendants whether to expand descendant concepts
#' @param remove_pii whether to strip PII from generated rows
#' @return parsed ACP response
#' @export
acp_keeper_profiles_generate <- function(client,
                                         cohort_database_schema,
                                         cohort_table,
                                         cohort_definition_id,
                                         cdm_database_schema,
                                         keeper_concept_sets,
                                         sample_size = 20,
                                         person_ids = NULL,
                                         phenotype_name = NULL,
                                         use_descendants = TRUE,
                                         remove_pii = TRUE) {
  if (is.null(cohort_database_schema) || !nzchar(trimws(as.character(cohort_database_schema)))) {
    stop("Provide a non-empty cohort_database_schema.")
  }
  if (is.null(cohort_table) || !nzchar(trimws(as.character(cohort_table)))) {
    stop("Provide a non-empty cohort_table.")
  }
  if (is.null(cdm_database_schema) || !nzchar(trimws(as.character(cdm_database_schema)))) {
    stop("Provide a non-empty cdm_database_schema.")
  }
  cohort_definition_id <- suppressWarnings(as.integer(cohort_definition_id))
  if (is.na(cohort_definition_id)) stop("Provide a numeric cohort_definition_id.")
  if (!is.list(keeper_concept_sets) || !length(keeper_concept_sets)) {
    stop("Provide a non-empty keeper_concept_sets list.")
  }
  person_ids <- as.character(person_ids %||% character(0))

  body <- list(
    cohort_database_schema = trimws(as.character(cohort_database_schema)),
    cohort_table = trimws(as.character(cohort_table)),
    cohort_definition_id = cohort_definition_id,
    cdm_database_schema = trimws(as.character(cdm_database_schema)),
    sample_size = as.integer(sample_size),
    person_ids = as.list(person_ids),
    keeper_concept_sets = keeper_concept_sets,
    use_descendants = isTRUE(use_descendants),
    remove_pii = isTRUE(remove_pii)
  )
  if (!is.null(phenotype_name) && nzchar(trimws(as.character(phenotype_name)))) {
    body$phenotype_name <- trimws(as.character(phenotype_name))
  }
  acp_call_flow(client, "keeper_profiles_generate", body)
}

#' Call phenotype validation review flow
#' @param client ACP client object
#' @param disease_name disease or phenotype name
#' @param keeper_row sanitized Keeper-style review row
#' @return parsed ACP response
#' @export
acp_phenotype_validation_review <- function(client, disease_name, keeper_row) {
  if (is.null(disease_name) || !nzchar(trimws(as.character(disease_name)))) {
    stop("Provide a non-empty disease_name.")
  }
  if (!is.list(keeper_row) || !length(keeper_row)) {
    stop("Provide keeper_row as a non-empty list.")
  }
  acp_call_flow(
    client,
    "phenotype_validation_review",
    list(
      disease_name = trimws(as.character(disease_name)),
      keeper_row = keeper_row
    )
  )
}
