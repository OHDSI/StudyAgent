normalize_incidence_dialogue_step <- function(step) {
  step <- as.character(step %||% "")
  mapped <- switch(
    step,
    study_intent = "study_intent_capture",
    target_recommendation = "target_selection",
    target_recommendation_window2 = "target_selection",
    target_recommendation_resume = "target_selection",
    target_advice_call = "target_selection",
    target_improvements = "phenotype_review",
    outcome_recommendation = "outcome_selection",
    outcome_recommendation_window2 = "outcome_selection",
    outcome_recommendation_resume = "outcome_selection",
    outcome_advice_call = "outcome_selection",
    outcome_improvements = "phenotype_review",
    keeper_concept_set_generation_before = "keeper_concept_set_generation",
    keeper_concept_set_generation_after = "keeper_concept_set_generation",
    keeper_case_review_before = "keeper_case_review",
    keeper_case_review_after = "keeper_case_review",
    step
  )
  as.character(mapped %||% "")
}

incidence_dialogue_step_label <- function(step, role = "") {
  step <- normalize_incidence_dialogue_step(step)
  role <- as.character(role %||% "")
  role_label <- if (nzchar(role)) paste0(toupper(substring(role, 1, 1)), substring(role, 2), " ") else ""
  switch(
    step,
    study_intent_capture = "Study intent capture",
    intent_split = if (nzchar(role_label)) paste0("Intent split: ", trimws(role_label)) else "Intent split",
    target_selection = "Target selection",
    outcome_selection = "Outcome selection",
    phenotype_review = if (nzchar(role_label)) paste0(role_label, "phenotype review") else "Phenotype review",
    keeper_concept_set_generation = if (nzchar(role_label)) paste0(role_label, "Keeper concept-set generation") else "Keeper concept-set generation",
    keeper_case_review = if (nzchar(role_label)) paste0(role_label, "Keeper case review") else "Keeper case review",
    incidence_design_setup = "Incidence design setup",
    time_at_risk_configuration = "Time-at-risk configuration",
    workflow_summary = "Workflow summary",
    gsub("_", " ", step, fixed = TRUE)
  )
}

build_incidence_workflow_stage_context <- function(study_intent,
                                                   dialogue_state,
                                                   interactive = TRUE) {
  current_step <- normalize_incidence_dialogue_step(dialogue_state$current_step %||% "")
  current_role <- as.character(dialogue_state$current_role %||% "")
  current_context <- compact_workflow_dialogue_context(dialogue_state$current_context %||% list())

  context <- new_workflow_stage_context(
    workflow_type = "strategus_incidence",
    current_step = current_step,
    step_label = incidence_dialogue_step_label(current_step, current_role),
    user_goal = as.character(study_intent %||% ""),
    entities = compact_workflow_dialogue_context(list(
      active_role = current_role,
      role_statement = current_context$role_statement %||% current_context$statement,
      target = current_context$target_statement %||% NULL,
      outcomes = current_context$outcome_statement %||% current_context$outcome_statements %||% list()
    )),
    available_artifacts = compact_workflow_dialogue_context(list(
      selected_target_ids = as.list(current_context$selected_target_ids %||% list()),
      selected_outcome_ids = as.list(current_context$selected_outcome_ids %||% list()),
      analysis_settings_path = current_context$analysis_settings_path %||% NULL,
      concept_set_paths = current_context$concept_set_paths %||% list()
    )),
    last_user_message = NULL,
    constraints = list(
      interactive = isTRUE(interactive),
      allow_recommendations = TRUE,
      allow_generation = FALSE
    )
  )
  context$legacy_context <- current_context
  context
}

normalize_cohort_methods_dialogue_step <- function(step) {
  step <- as.character(step %||% "")
  mapped <- switch(
    step,
    study_intent = "study_intent_capture",
    target_recommendation = "target_selection",
    comparator_recommendation = "comparator_selection",
    outcome_recommendation = "outcome_selection",
    target_improvements = "phenotype_review",
    comparator_improvements = "phenotype_review",
    outcome_improvements = "phenotype_review",
    analytic_settings_step_by_step = "analytic_settings_collection",
    keeper_concept_set_generation_before = "keeper_concept_set_generation",
    keeper_concept_set_generation_after = "keeper_concept_set_generation",
    keeper_case_review_before = "keeper_case_review",
    keeper_case_review_after = "keeper_case_review",
    step
  )
  as.character(mapped %||% "")
}

cohort_methods_dialogue_step_label <- function(step, role = "") {
  step <- normalize_cohort_methods_dialogue_step(step)
  role <- as.character(role %||% "")
  role_label <- if (nzchar(role)) {
    paste0(toupper(substring(role, 1, 1)), substring(role, 2), " ")
  } else {
    ""
  }
  switch(
    step,
    study_intent_capture = "Study intent capture",
    intent_split = if (nzchar(role_label)) paste0("Intent split: ", trimws(role_label)) else "Intent split",
    target_selection = "Target selection",
    comparator_selection = "Comparator selection",
    outcome_selection = "Outcome selection",
    phenotype_review = if (nzchar(role_label)) paste0(role_label, "phenotype review") else "Phenotype review",
    keeper_concept_set_generation = if (nzchar(role_label)) paste0(role_label, "Keeper concept-set generation") else "Keeper concept-set generation",
    keeper_case_review = if (nzchar(role_label)) paste0(role_label, "Keeper case review") else "Keeper case review",
    analytic_settings_collection = "Analytic settings collection",
    cohort_method_spec_recommendation = "Cohort method specification recommendation",
    cohort_method_spec_confirmation = "Cohort method specification confirmation",
    workflow_summary = "Workflow summary",
    gsub("_", " ", step, fixed = TRUE)
  )
}

build_cohort_methods_workflow_stage_context <- function(study_intent,
                                                        dialogue_state,
                                                        interactive = TRUE) {
  current_step <- normalize_cohort_methods_dialogue_step(dialogue_state$current_step %||% "")
  current_role <- as.character(dialogue_state$current_role %||% "")
  current_context <- compact_workflow_dialogue_context(dialogue_state$current_context %||% list())

  context <- new_workflow_stage_context(
    workflow_type = "strategus_cohort_methods",
    current_step = current_step,
    step_label = cohort_methods_dialogue_step_label(current_step, current_role),
    user_goal = as.character(study_intent %||% ""),
    entities = compact_workflow_dialogue_context(list(
      active_role = current_role,
      role_statement = current_context$role_statement %||% current_context$statement,
      target = current_context$target_statement %||% NULL,
      comparator = current_context$comparator_statement %||% NULL,
      outcomes = current_context$outcome_statements %||% list()
    )),
    available_artifacts = compact_workflow_dialogue_context(list(
      selected_target_ids = as.list(current_context$selected_target_ids %||% list()),
      selected_comparator_ids = as.list(current_context$selected_comparator_ids %||% list()),
      selected_outcome_ids = as.list(current_context$selected_outcome_ids %||% list()),
      analysis_settings_path = current_context$analysis_settings_path %||% NULL,
      concept_set_paths = current_context$concept_set_paths %||% list()
    )),
    last_user_message = NULL,
    constraints = list(
      interactive = isTRUE(interactive),
      allow_recommendations = TRUE,
      allow_generation = FALSE
    )
  )
  context$legacy_context <- current_context
  context
}
