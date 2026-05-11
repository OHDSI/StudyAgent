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
#' @export
acp_workflow_context_dialogue <- function(client, stage_context, message) {
  if (!is.list(stage_context)) stop("stage_context must be a list.")
  if (is.null(message) || !nzchar(trimws(as.character(message)))) {
    stop("Provide a non-empty message.")
  }
  body <- list(
    workflow_stage_context = stage_context,
    message = trimws(as.character(message))
  )
  acp_call_flow(client, "workflow_context_dialogue", body)
}

#' Call keeper concept set generation flow
#' @param client ACP client object
#' @param phenotype phenotype label
#' @param domain_keys character vector of domain keys
#' @param candidate_limit candidate limit
#' @param include_diagnostics whether to request diagnostics
#' @return parsed ACP response
#' @export
acp_keeper_concept_sets_generate <- function(client,
                                             phenotype,
                                             domain_keys,
                                             candidate_limit = 5,
                                             include_diagnostics = TRUE) {
  if (is.null(phenotype) || !nzchar(trimws(as.character(phenotype)))) {
    stop("Provide a non-empty phenotype.")
  }
  domain_keys <- as.character(domain_keys %||% character(0))
  if (!length(domain_keys)) stop("Provide at least one domain key.")
  body <- list(
    phenotype = trimws(as.character(phenotype)),
    domain_keys = as.list(domain_keys),
    candidate_limit = candidate_limit,
    include_diagnostics = isTRUE(include_diagnostics)
  )
  acp_call_flow(client, "keeper_concept_sets_generate", body)
}
