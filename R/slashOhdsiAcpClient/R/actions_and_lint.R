#' Call ACP execute-llm action for concept-set edits
#' @param client ACP client object
#' @param concept_set_ref path to concept set JSON
#' @param actions list of ACP action objects
#' @param write when TRUE, write changes through ACP
#' @param overwrite whether ACP should overwrite the source file
#' @param backup whether ACP should create a backup before overwrite
#' @return parsed ACP response
#' @export
acp_execute_llm_actions_concept_set <- function(client,
                                                concept_set_ref,
                                                actions,
                                                write = FALSE,
                                                overwrite = FALSE,
                                                backup = TRUE) {
  body <- list(
    artifactRef = concept_set_ref,
    actions = actions %||% list(),
    write = isTRUE(write),
    overwrite = isTRUE(overwrite),
    backup = isTRUE(backup)
  )
  acp_call_action(client, "execute_llm", body)
}

#' Call ACP concept-set edit action
#' @param client ACP client object
#' @param artifact_ref path or URL to concept set JSON
#' @param ops deterministic concept-set operations
#' @param write whether ACP should write the result
#' @param backup whether ACP should create a backup
#' @param output_path optional output path
#' @return parsed ACP response
#' @export
acp_concept_set_edit <- function(client,
                                 artifact_ref,
                                 ops,
                                 write = FALSE,
                                 backup = TRUE,
                                 output_path = NULL) {
  body <- list(
    artifactRef = artifact_ref,
    ops = ops %||% list(),
    write = isTRUE(write),
    backup = isTRUE(backup)
  )
  if (!is.null(output_path)) body$outputPath <- output_path
  acp_call_action(client, "concept_set_edit", body)
}

#' Call ACP concept-set lint flow
#' @param client ACP client object
#' @param concept_set_path local path to concept set JSON; the client loads and sends inline concept_set
#' @param study_intent study intent text
#' @return parsed ACP response
#' @export
acp_lint_concept_sets <- function(client, concept_set_path, study_intent = "") {
  body <- list(
    concept_set = .acp_read_json_file(concept_set_path, label = "concept_set_path"),
    study_intent = as.character(study_intent %||% "")
  )
  acp_call_flow(client, "concept_sets_review", body)
}

#' Call ACP general cohort critique flow
#' @param client ACP client object
#' @param cohort_path local path to cohort JSON; the client loads and sends inline cohort
#' @return parsed ACP response
#' @export
acp_lint_cohort_general_design <- function(client, cohort_path) {
  acp_call_flow(client, "cohort_critique_general_design", list(cohort = .acp_load_cohort_from_path(cohort_path, label = "cohort_path")))
}
