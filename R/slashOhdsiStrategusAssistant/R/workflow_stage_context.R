`%||%` <- function(a, b) if (is.null(a)) b else a

workflow_stage_step_choices <- function() {
  c(
    "study_intent_capture",
    "intent_split",
    "target_selection",
    "comparator_selection",
    "outcome_selection",
    "phenotype_review",
    "keeper_concept_set_generation",
    "keeper_case_review",
    "analytic_settings_collection",
    "cohort_method_spec_recommendation",
    "cohort_method_spec_confirmation",
    "incidence_design_setup",
    "time_at_risk_configuration",
    "diagnostics_review",
    "strategus_spec_execution",
    "workflow_execution",
    "workflow_summary"
  )
}

#' Construct a workflow stage context object
#' @param workflow_type workflow identifier such as `strategus_cohort_methods`
#' @param current_step controlled step identifier
#' @param user_goal study intent or current user goal
#' @param step_label optional human-readable step label
#' @param entities optional entity state list
#' @param available_artifacts optional artifact references list
#' @param prior_questions optional list of prior question summaries
#' @param prior_answers optional list of prior answer summaries
#' @param last_user_message optional latest user message
#' @param constraints optional constraint flags
#' @param contract_version contract version integer
#' @return validated workflow stage context list
#' @export
new_workflow_stage_context <- function(workflow_type,
                                       current_step,
                                       user_goal,
                                       step_label = NULL,
                                       entities = NULL,
                                       available_artifacts = NULL,
                                       prior_questions = NULL,
                                       prior_answers = NULL,
                                       last_user_message = NULL,
                                       constraints = NULL,
                                       contract_version = 1L) {
  context <- list(
    contract_version = as.integer(contract_version),
    workflow_type = as.character(workflow_type),
    current_step = as.character(current_step),
    step_label = step_label %||% gsub("_", " ", as.character(current_step), fixed = TRUE),
    user_goal = as.character(user_goal),
    entities = entities %||% list(target = NULL, comparator = NULL, outcomes = list()),
    available_artifacts = available_artifacts %||% list(
      protocol_path = NULL,
      selected_target_ids = list(),
      selected_comparator_ids = list(),
      selected_outcome_ids = list(),
      analysis_settings_path = NULL,
      concept_set_paths = list()
    ),
    dialogue = list(
      prior_questions = prior_questions %||% list(),
      prior_answers = prior_answers %||% list(),
      last_user_message = last_user_message
    ),
    constraints = constraints %||% list(
      interactive = TRUE,
      allow_recommendations = TRUE,
      allow_generation = FALSE
    )
  )
  validate_workflow_stage_context(context)
  context
}

#' Validate a workflow stage context object
#' @param context workflow stage context list
#' @return invisible(TRUE) when valid
#' @export
validate_workflow_stage_context <- function(context) {
  if (!is.list(context)) stop("workflow stage context must be a list.")
  required_fields <- c("contract_version", "workflow_type", "current_step", "user_goal")
  missing_fields <- required_fields[!required_fields %in% names(context)]
  if (length(missing_fields)) {
    stop(sprintf("workflow stage context is missing required field(s): %s", paste(missing_fields, collapse = ", ")))
  }
  if (!nzchar(trimws(context$workflow_type %||% ""))) {
    stop("workflow_type must be non-empty.")
  }
  if (!nzchar(trimws(context$current_step %||% ""))) {
    stop("current_step must be non-empty.")
  }
  if (!(context$current_step %in% workflow_stage_step_choices())) {
    stop(sprintf("Unsupported current_step '%s'.", context$current_step))
  }
  if (!nzchar(trimws(context$user_goal %||% ""))) {
    stop("user_goal must be non-empty.")
  }
  invisible(TRUE)
}
