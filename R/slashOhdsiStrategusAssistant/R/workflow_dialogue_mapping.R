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

.studyAgentSlashCollapseDialogueText <- function(value) {
  if (is.null(value) || length(value) == 0) return("")
  if (is.list(value)) {
    parts <- unlist(lapply(value, .studyAgentSlashCollapseDialogueText), use.names = FALSE)
    parts <- trimws(as.character(parts %||% character(0)))
    parts <- parts[nzchar(parts)]
    return(paste(parts, collapse = "; "))
  }
  text <- trimws(as.character(value))
  text <- text[nzchar(text)]
  paste(text, collapse = "; ")
}

.studyAgentSlashResolveDialogueUserGoal <- function(study_intent,
                                                    workflow_type,
                                                    current_step,
                                                    current_role = "",
                                                    current_context = list()) {
  current_context <- compact_workflow_dialogue_context(current_context %||% list())
  current_step <- as.character(current_step %||% "")
  current_role <- as.character(current_role %||% "")

  study_goal <- trimws(as.character(study_intent %||% ""))
  if (nzchar(study_goal)) return(study_goal)

  role_statement <- .studyAgentSlashCollapseDialogueText(
    current_context$role_statement %||% current_context$statement %||% NULL
  )
  if (!nzchar(role_statement) && identical(current_role, "target")) {
    role_statement <- .studyAgentSlashCollapseDialogueText(current_context$target_statement %||% NULL)
  }
  if (!nzchar(role_statement) && identical(current_role, "comparator")) {
    role_statement <- .studyAgentSlashCollapseDialogueText(current_context$comparator_statement %||% NULL)
  }
  if (!nzchar(role_statement) && identical(current_role, "outcome")) {
    role_statement <- .studyAgentSlashCollapseDialogueText(
      current_context$outcome_statement %||% current_context$outcome_statements %||% NULL
    )
  }
  if (nzchar(role_statement)) {
    role_label <- if (nzchar(current_role)) current_role else "active"
    return(sprintf("Define the %s cohort using this statement: %s", role_label, role_statement))
  }

  step_goal <- if (identical(workflow_type, "strategus_incidence")) {
    switch(
      current_step,
      study_intent_capture = "Define the study intent or proceed with direct cohort acquisition for the incidence study.",
      intent_split = "Enter concise cohort statements for the current incidence-study role.",
      target_selection = "Define or select the target cohort for the incidence study.",
      outcome_selection = "Define or select the outcome cohort for the incidence study.",
      phenotype_review = "Review phenotype improvements for the current incidence-study cohort.",
      incidence_design_setup = "Configure incidence-study execution inputs and generated artifacts.",
      time_at_risk_configuration = "Configure time-at-risk definitions and strata settings for the incidence study.",
      workflow_summary = "Review the saved incidence-study build summary before execution mode.",
      "Continue the incidence-study workflow using the current prompt."
    )
  } else {
    switch(
      current_step,
      study_intent_capture = "Define the study intent or proceed with direct cohort acquisition for the cohort-method study.",
      intent_split = "Enter concise cohort statements for the current cohort-method role.",
      target_selection = "Define or select the target cohort for the cohort-method study.",
      comparator_selection = "Define or select the comparator cohort for the cohort-method study.",
      outcome_selection = "Define or select the outcome cohort for the cohort-method study.",
      phenotype_review = "Review phenotype improvements for the current cohort-method cohort.",
      analytic_settings_collection = "Configure analytic settings for the cohort-method study.",
      cohort_method_spec_recommendation = "Review the cohort-method specification inputs before confirmation.",
      cohort_method_spec_confirmation = "Confirm the cohort-method specification inputs before writing artifacts.",
      workflow_summary = "Review the saved cohort-method build summary before execution mode.",
      "Continue the cohort-method workflow using the current prompt."
    )
  }

  as.character(step_goal %||% "Continue the current workflow using the active prompt.")
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
    user_goal = .studyAgentSlashResolveDialogueUserGoal(
      study_intent = study_intent,
      workflow_type = "strategus_incidence",
      current_step = current_step,
      current_role = current_role,
      current_context = current_context
    ),
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
    user_goal = .studyAgentSlashResolveDialogueUserGoal(
      study_intent = study_intent,
      workflow_type = "strategus_cohort_methods",
      current_step = current_step,
      current_role = current_role,
      current_context = current_context
    ),
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

workflow_build_help_lines <- function(workflow_type, step, role = "", context = list()) {
  `%||%` <- function(x, y) if (is.null(x)) y else x
  workflow_type <- as.character(workflow_type %||% "")
  role <- as.character(role %||% "")
  context <- compact_workflow_dialogue_context(context %||% list())

  command_lines <- c(
    "Commands for this step:",
    "  - h or help: show commands for the current step",
    "  - /ohdsi <question>: ask for workflow-aware OHDSI guidance",
    "  - /back: return to the previous supported step boundary",
    "  - Enter: accept the default value or continue when allowed"
  )

  if (identical(workflow_type, "strategus_incidence")) {
    step <- normalize_incidence_dialogue_step(step)
    step_lines <- switch(
      step,
      study_intent_capture = c(
        "Provide a study intent to let ACP propose target and outcome statements.",
        "Press Enter on a blank study intent to switch to direct cohort-statement entry."
      ),
      intent_split = c(
        "Enter concise cohort statements for the current role.",
        "Use direct acquisition when you want to bypass ACP intent splitting and drive role selection yourself."
      ),
      target_selection = c(
        "Choose how to acquire the target cohort: agentic search, database cohort, local JSON file, or directory.",
        "Selection sources are recorded in project state and imported artifacts are cached locally."
      ),
      outcome_selection = c(
        "Choose how to acquire the outcome cohort: agentic search, database cohort, local JSON file, or directory.",
        "Selection sources are recorded in project state and imported artifacts are cached locally."
      ),
      phenotype_review = c(
        "Review phenotype improvement suggestions for the active role before continuing.",
        "You can keep the existing cohort, apply improvements, or skip improvements when they are not useful."
      ),
      incidence_design_setup = c(
        "Configure the incidence build inputs, including cohort ID mapping and execution-root paths.",
        "These settings shape the generated Strategus scripts and downstream artifact discovery."
      ),
      time_at_risk_configuration = c(
        "Review time-at-risk windows, analysis TAR IDs, and optional strata settings.",
        "Use the cohort statements and selected cohort IDs as context when deciding the TAR definitions."
      ),
      workflow_summary = c(
        "Review the saved build summary before entering execution mode.",
        "This is the last build-stage checkpoint before generated steps are run."
      ),
      c("Use the current prompt and surrounding context to decide the next input.")
    )
  } else {
    step <- normalize_cohort_methods_dialogue_step(step)
    step_lines <- switch(
      step,
      study_intent_capture = c(
        "Provide a study intent to let ACP propose target, comparator, and outcome statements.",
        "Press Enter on a blank study intent to switch to direct cohort-statement entry."
      ),
      intent_split = c(
        "Enter concise cohort statements for the current role.",
        "If outcome statements are suggested, keep the defaults or edit them into the final analysis wording you want preserved."
      ),
      target_selection = c(
        "Choose how to acquire the target cohort: agentic search, database cohort, local JSON file, or directory.",
        "Imported cohort definitions are cached and the selection source is persisted in project state."
      ),
      comparator_selection = c(
        "Choose how to acquire the comparator cohort: agentic search, database cohort, local JSON file, or directory.",
        "Imported cohort definitions are cached and the selection source is persisted in project state."
      ),
      outcome_selection = c(
        "Choose how to acquire the outcome cohort: agentic search, database cohort, local JSON file, or directory.",
        "Imported cohort definitions are cached and the selection source is persisted in project state."
      ),
      phenotype_review = c(
        "Review phenotype improvement suggestions for the active role before continuing.",
        "You can keep the existing cohort, apply improvements, or skip improvements when they are not useful."
      ),
      analytic_settings_collection = c(
        "Review the analytic settings profile and any customized sections before generating the cohort-method specification.",
        "This step controls the generated analysis JSON and the resulting Strategus module arguments."
      ),
      cohort_method_spec_recommendation = c(
        "Review the recommended cohort-method specification details and confirm the persisted settings.",
        "Use /ohdsi if you want contextual guidance on washout, risk windows, matching, or outcome modeling."
      ),
      cohort_method_spec_confirmation = c(
        "Confirm the final specification inputs before writing the generated cohort-method artifacts.",
        "Edits here should persist to the saved manual inputs and analysis settings files."
      ),
      workflow_summary = c(
        "Review the saved build summary before entering execution mode.",
        "This is the last build-stage checkpoint before generated steps are run."
      ),
      c("Use the current prompt and surrounding context to decide the next input.")
    )
  }

  db_lines <- character(0)
  if (identical(step, "target_selection") || identical(step, "comparator_selection") || identical(step, "outcome_selection")) {
    db_lines <- c(
      "Database import:",
      "  - db uses strategus-cohort-source-db-details.json, not the execution DB config.",
      "  - Populate the cohort-source DB template before retrying a db import."
    )
  }

  role_line <- if (nzchar(role)) sprintf("Current role: %s", role) else NULL
  intent_line <- if (nzchar(trimws(as.character(context$study_intent %||% "")))) {
    sprintf("Current study intent: %s", as.character(context$study_intent))
  } else if (!is.null(context$generated_from_role_statements) && isTRUE(context$generated_from_role_statements)) {
    "Current study intent: a derived default will be proposed from the entered cohort statements."
  } else {
    NULL
  }

  c(role_line, intent_line, step_lines, db_lines, command_lines)
}
