#' Run ACP-based Keeper concept-set workflow for selected cohorts
#' @param base_dir workflow base directory
#' @param execution_settings_path path to strategus-execution-settings.json
#' @param cohort_id_map_path path to outputs/cohort_id_map.json
#' @param cohort_roles_path optional path to outputs/cohort_roles.json
#' @param intent_path optional path to intent split JSON used to infer phenotype labels
#' @param acp_url ACP base URL
#' @param acp_timeout_seconds ACP HTTP timeout in seconds; defaults to ACP_TIMEOUT or 300
#' @param review_roles cohort roles to process, defaults to outcome-first
#' @param role_phenotypes optional named overrides by role or cohort id
#' @param stage_callback optional workflow stage callback
#' @param stage_gate optional interactive stage gate callback returning actions or setting updates
#' @param domain_keys Keeper concept-set domains to request
#' @param candidate_limit ACP concept candidate limit
#' @param min_record_count optional minimum record count filter
#' @param include_diagnostics whether to request ACP diagnostics
#' @param auto_approve_generated when TRUE, seed approved concept sets from generated output when no approved file exists
#' @param overwrite_approved_concept_sets when TRUE, replace approved concept sets with the current generated concept sets
#' @param reuse_generated_concept_sets when TRUE, reuse existing generated concept-set artifacts
#' @return invisible list summarizing artifact paths and per-cohort status
#' @export
runKeeperConceptSetWorkflow <- function(base_dir,
                                        execution_settings_path = file.path(base_dir, "strategus-execution-settings.json"),
                                        cohort_id_map_path = file.path(base_dir, "outputs", "cohort_id_map.json"),
                                        cohort_roles_path = file.path(base_dir, "outputs", "cohort_roles.json"),
                                        intent_path = NULL,
                                        acp_url = Sys.getenv("ACP_URL", "http://127.0.0.1:8765"),
                                        acp_timeout_seconds = as.numeric(Sys.getenv("ACP_TIMEOUT", "300")),
                                        review_roles = c("outcome"),
                                        role_phenotypes = NULL,
                                        stage_callback = NULL,
                                        stage_gate = NULL,
                                        domain_keys = c(
                                          "doi",
                                          "drugs",
                                          "complications"
                                        ),
                                        candidate_limit = 10,
                                        min_record_count = NULL,
                                        include_diagnostics = TRUE,
                                        auto_approve_generated = TRUE,
                                        overwrite_approved_concept_sets = FALSE,
                                        reuse_generated_concept_sets = TRUE) {
  context <- .studyAgentSlashPrepareKeeperWorkflowContext(
    base_dir = base_dir,
    execution_settings_path = execution_settings_path,
    cohort_id_map_path = cohort_id_map_path,
    cohort_roles_path = cohort_roles_path,
    intent_path = intent_path,
    acp_url = acp_url,
    acp_timeout_seconds = acp_timeout_seconds,
    review_roles = review_roles,
    stage_callback = stage_callback,
    stage_gate = stage_gate
  )

  current_candidate_limit <- .studyAgentSlashValidateKeeperPositiveInteger(candidate_limit, "candidate_limit")
  current_min_record_count <- .studyAgentSlashValidateKeeperOptionalInteger(min_record_count, "min_record_count")
  summary_rows <- vector("list", nrow(context$selected_map))
  workflow_errors <- list()

  for (i in seq_len(nrow(context$selected_map))) {
    row <- .studyAgentSlashKeeperConceptSetStep(
      context = context,
      selected_row = context$selected_map[i, , drop = FALSE],
      role_phenotypes = role_phenotypes,
      domain_keys = domain_keys,
      candidate_limit = current_candidate_limit,
      min_record_count = current_min_record_count,
      include_diagnostics = include_diagnostics,
      auto_approve_generated = auto_approve_generated,
      overwrite_approved_concept_sets = overwrite_approved_concept_sets,
      reuse_generated_concept_sets = reuse_generated_concept_sets,
      workflow_errors = workflow_errors
    )
    summary_rows[[i]] <- row$summary
    workflow_errors <- row$workflow_errors
  }

  keeper_state <- list(
    status = if (length(workflow_errors)) "error" else "ok",
    message = if (length(workflow_errors)) {
      sprintf("Keeper concept-set workflow encountered %s ACP error(s).", length(workflow_errors))
    } else {
      "Keeper concept-set workflow completed without ACP errors."
    },
    error_count = length(workflow_errors),
    errors = workflow_errors,
    base_dir = context$base_dir,
    execution_settings_path = context$execution_settings_path,
    cohort_id_map_path = context$cohort_id_map_path,
    cohort_roles_path = context$cohort_roles_path,
    intent_path = context$intent_path,
    acp_url = context$acp_url,
    acp_timeout_seconds = as.numeric(context$acp_timeout_seconds),
    keeper_dir = context$keeper_dir,
    review_roles = as.list(context$review_roles),
    domain_keys = as.list(as.character(domain_keys)),
    candidate_limit = as.integer(current_candidate_limit),
    min_record_count = if (is.null(current_min_record_count)) NULL else as.integer(current_min_record_count),
    overwrite_approved_concept_sets = isTRUE(overwrite_approved_concept_sets),
    reuse_generated_concept_sets = isTRUE(reuse_generated_concept_sets),
    auto_approve_generated = isTRUE(auto_approve_generated),
    cohorts = summary_rows
  )
  keeper_state_path <- file.path(context$output_dir, "keeper_concept_set_state.json")
  .studyAgentSlashWriteJson(keeper_state, keeper_state_path)
  .studyAgentSlashUpdateStudyAgentState(
    state_path = file.path(context$output_dir, "study_agent_state.json"),
    state_key = "keeper_concept_set",
    state_value = keeper_state,
    state_path_value = keeper_state_path,
    artifact_paths = list(
      keeper_dir = context$keeper_dir,
      concept_sets_generated = context$generated_dir,
      concept_sets_approved = context$approved_dir
    )
  )

  invisible(c(keeper_state, list(keeper_concept_set_state_path = keeper_state_path)))
}

#' Run ACP-based Keeper case-review workflow for selected cohorts
#' @param base_dir workflow base directory
#' @param execution_settings_path path to strategus-execution-settings.json
#' @param cohort_id_map_path path to outputs/cohort_id_map.json
#' @param cohort_roles_path optional path to outputs/cohort_roles.json
#' @param intent_path optional path to intent split JSON used to infer phenotype labels
#' @param acp_url ACP base URL
#' @param acp_timeout_seconds ACP HTTP timeout in seconds; defaults to ACP_TIMEOUT or 300
#' @param review_roles cohort roles to process, defaults to outcome-first
#' @param role_phenotypes optional named overrides by role or cohort id
#' @param stage_callback optional workflow stage callback
#' @param stage_gate optional interactive stage gate callback returning actions or setting updates
#' @param sample_size requested profile sample size per cohort
#' @param review_row_limit maximum number of generated rows to review per cohort
#' @param use_descendants whether profile generation should include descendants
#' @param remove_pii whether to enforce PII removal for generated rows
#' @param reuse_rows when TRUE, reuse existing generated Keeper row artifacts
#' @param resume_reviews when TRUE, continue from saved review artifacts instead of restarting
#' @param review_row_selection optional review row indices or range string such as "1-3,5"; overrides the default first-N selection
#' @return invisible list summarizing artifact paths and per-cohort status
#' @export
runKeeperCaseReviewWorkflow <- function(base_dir,
                                        execution_settings_path = file.path(base_dir, "strategus-execution-settings.json"),
                                        cohort_id_map_path = file.path(base_dir, "outputs", "cohort_id_map.json"),
                                        cohort_roles_path = file.path(base_dir, "outputs", "cohort_roles.json"),
                                        intent_path = NULL,
                                        acp_url = Sys.getenv("ACP_URL", "http://127.0.0.1:8765"),
                                        acp_timeout_seconds = as.numeric(Sys.getenv("ACP_TIMEOUT", "300")),
                                        review_roles = c("outcome"),
                                        role_phenotypes = NULL,
                                        stage_callback = NULL,
                                        stage_gate = NULL,
                                        sample_size = 5,
                                        review_row_limit = 5,
                                        use_descendants = TRUE,
                                        remove_pii = TRUE,
                                        reuse_rows = FALSE,
                                        resume_reviews = TRUE,
                                        review_row_selection = NULL) {
  context <- .studyAgentSlashPrepareKeeperWorkflowContext(
    base_dir = base_dir,
    execution_settings_path = execution_settings_path,
    cohort_id_map_path = cohort_id_map_path,
    cohort_roles_path = cohort_roles_path,
    intent_path = intent_path,
    acp_url = acp_url,
    acp_timeout_seconds = acp_timeout_seconds,
    review_roles = review_roles,
    stage_callback = stage_callback,
    stage_gate = stage_gate
  )

  current_sample_size <- .studyAgentSlashValidateKeeperPositiveInteger(sample_size, "sample_size")
  current_review_row_limit <- .studyAgentSlashValidateKeeperPositiveInteger(review_row_limit, "review_row_limit")
  summary_rows <- vector("list", nrow(context$selected_map))
  workflow_errors <- list()

  for (i in seq_len(nrow(context$selected_map))) {
    row <- .studyAgentSlashKeeperCaseReviewStep(
      context = context,
      selected_row = context$selected_map[i, , drop = FALSE],
      role_phenotypes = role_phenotypes,
      sample_size = current_sample_size,
      review_row_limit = current_review_row_limit,
      use_descendants = use_descendants,
      remove_pii = remove_pii,
      reuse_rows = reuse_rows,
      resume_reviews = resume_reviews,
      review_row_selection = review_row_selection,
      workflow_errors = workflow_errors
    )
    summary_rows[[i]] <- row$summary
    workflow_errors <- row$workflow_errors
  }

  keeper_state <- list(
    status = if (length(workflow_errors)) "error" else "ok",
    message = if (length(workflow_errors)) {
      sprintf("Keeper case-review workflow encountered %s workflow error(s).", length(workflow_errors))
    } else {
      "Keeper case-review workflow completed successfully."
    },
    error_count = length(workflow_errors),
    errors = workflow_errors,
    base_dir = context$base_dir,
    execution_settings_path = context$execution_settings_path,
    cohort_id_map_path = context$cohort_id_map_path,
    cohort_roles_path = context$cohort_roles_path,
    intent_path = context$intent_path,
    acp_url = context$acp_url,
    acp_timeout_seconds = as.numeric(context$acp_timeout_seconds),
    keeper_dir = context$keeper_dir,
    review_roles = as.list(context$review_roles),
    sample_size = as.integer(current_sample_size),
    review_row_limit = as.integer(current_review_row_limit),
    review_row_selection = if (is.null(review_row_selection)) NULL else as.character(review_row_selection),
    reuse_rows = isTRUE(reuse_rows),
    resume_reviews = isTRUE(resume_reviews),
    remove_pii = isTRUE(remove_pii),
    use_descendants = isTRUE(use_descendants),
    cohorts = summary_rows
  )
  keeper_state_path <- file.path(context$output_dir, "keeper_case_review_state.json")
  .studyAgentSlashWriteJson(keeper_state, keeper_state_path)
  .studyAgentSlashUpdateStudyAgentState(
    state_path = file.path(context$output_dir, "study_agent_state.json"),
    state_key = "keeper_case_review",
    state_value = keeper_state,
    state_path_value = keeper_state_path,
    artifact_paths = list(
      keeper_dir = context$keeper_dir,
      rows = context$rows_dir,
      reviews = context$reviews_dir
    )
  )

  invisible(c(keeper_state, list(keeper_case_review_state_path = keeper_state_path)))
}

`%||%` <- function(x, y) if (is.null(x)) y else x

.studyAgentSlashEnsureDir <- function(path) {
  if (!dir.exists(path)) dir.create(path, recursive = TRUE, showWarnings = FALSE)
}

.studyAgentSlashReadJson <- function(path, simplify = FALSE) {
  jsonlite::fromJSON(path, simplifyVector = simplify)
}

.studyAgentSlashWriteJson <- function(x, path) {
  jsonlite::write_json(x, path, pretty = TRUE, auto_unbox = TRUE, null = "null")
}

.studyAgentSlashAsNamedRecord <- function(x) {
  if (!is.list(x)) return(list(value = x))
  x
}

.studyAgentSlashRecordsToDataFrame <- function(records) {
  records <- Filter(Negate(is.null), lapply(records, .studyAgentSlashAsNamedRecord))
  if (!length(records)) return(data.frame())
  keys <- unique(unlist(lapply(records, names), use.names = FALSE))
  rows <- lapply(records, function(rec) {
    values <- lapply(keys, function(key) {
      value <- rec[[key]]
      if (is.null(value)) return(NA_character_)
      if (length(value) == 0) return(NA_character_)
      if (is.list(value)) return(jsonlite::toJSON(value, auto_unbox = TRUE, null = "null"))
      if (length(value) > 1) return(jsonlite::toJSON(value, auto_unbox = TRUE, null = "null"))
      as.character(value)
    })
    stats::setNames(as.list(values), keys)
  })
  as.data.frame(do.call(rbind, lapply(rows, function(x) as.data.frame(x, stringsAsFactors = FALSE))), stringsAsFactors = FALSE)
}

.studyAgentSlashReadMapping <- function(path) {
  payload <- .studyAgentSlashReadJson(path, simplify = TRUE)
  mapping <- payload$mapping %||% payload
  if (is.null(mapping) || NROW(mapping) == 0) {
    stop("No cohort mapping found in: ", path)
  }
  as.data.frame(mapping, stringsAsFactors = FALSE)
}

.studyAgentSlashIntentCore <- function(path) {
  if (is.null(path) || !nzchar(path) || !file.exists(path)) return(list())
  payload <- .studyAgentSlashReadJson(path, simplify = FALSE)
  payload$intent_split %||% payload
}

.studyAgentSlashInferPhenotypeName <- function(role, cohort_id, cohort_name, intent_payload, overrides = NULL) {
  override <- NULL
  if (is.list(overrides) && !is.null(overrides[[as.character(cohort_id)]])) {
    override <- overrides[[as.character(cohort_id)]]
  } else if (is.list(overrides) && !is.null(overrides[[role]])) {
    override <- overrides[[role]]
  } else if (!is.null(overrides) && !is.list(overrides)) {
    named_overrides <- overrides
    if (!is.null(names(named_overrides))) {
      override <- named_overrides[[as.character(cohort_id)]] %||% named_overrides[[role]]
    }
  }
  if (!is.null(override) && nzchar(trimws(as.character(override)))) {
    return(trimws(as.character(override)))
  }
  field <- switch(
    as.character(role),
    target = "target_statement",
    comparator = "comparator_statement",
    outcome = "outcome_statement",
    NULL
  )
  if (!is.null(field) && !is.null(intent_payload[[field]]) && nzchar(trimws(as.character(intent_payload[[field]])))) {
    return(trimws(as.character(intent_payload[[field]])))
  }
  if (!is.null(cohort_name) && nzchar(trimws(as.character(cohort_name)))) {
    return(trimws(as.character(cohort_name)))
  }
  sprintf("Cohort %s", cohort_id)
}

.studyAgentSlashExtractConceptSets <- function(payload) {
  payload$concept_sets %||% payload$result$concept_sets %||% payload$full_result$concept_sets %||% list()
}

.studyAgentSlashExtractRows <- function(payload) {
  payload$rows %||% payload$result$rows %||% payload$full_result$rows %||% list()
}

.studyAgentSlashExtractReviewValue <- function(payload, field) {
  payload[[field]] %||% payload$result[[field]] %||% payload$full_result[[field]] %||% NULL
}

.studyAgentSlashExtractReviews <- function(payload) {
  payload$reviews %||% payload$result$reviews %||% payload$full_result$reviews %||% list()
}

.studyAgentSlashParseRowSelection <- function(selection, total_rows, default_limit) {
  total_rows <- suppressWarnings(as.integer(total_rows %||% 0L))
  default_limit <- suppressWarnings(as.integer(default_limit %||% 0L))
  if (is.na(total_rows) || total_rows <= 0L) return(integer(0))

  default_indices <- if (!is.na(default_limit) && default_limit > 0L) {
    seq_len(min(total_rows, default_limit))
  } else {
    integer(0)
  }

  if (is.null(selection) || length(selection) == 0L) return(default_indices)

  if (is.character(selection) && length(selection) == 1L) {
    selection_text <- trimws(selection)
    if (!nzchar(selection_text)) return(default_indices)
    if (tolower(selection_text) %in% c("all", "*")) return(seq_len(total_rows))
    parts <- trimws(strsplit(selection_text, ",", fixed = TRUE)[[1]])
    parsed <- integer(0)
    for (part in parts[nzchar(parts)]) {
      if (grepl("^[0-9]+-[0-9]+$", part)) {
        bounds <- as.integer(strsplit(part, "-", fixed = TRUE)[[1]])
        if (length(bounds) == 2L && !anyNA(bounds)) {
          parsed <- c(parsed, seq.int(min(bounds), max(bounds)))
        }
      } else {
        parsed <- c(parsed, suppressWarnings(as.integer(part)))
      }
    }
    indices <- parsed
  } else {
    indices <- suppressWarnings(as.integer(unlist(selection, use.names = FALSE)))
  }

  indices <- unique(indices[!is.na(indices)])
  indices[indices >= 1L & indices <= total_rows]
}

.studyAgentSlashSafeCall <- function(expr) {
  tryCatch(expr, error = function(e) {
    list(status = "error", error = conditionMessage(e))
  })
}

.studyAgentSlashPayloadErrorMessage <- function(payload) {
  if (!is.list(payload)) return(NULL)
  status <- payload$status %||% payload$result$status %||% payload$full_result$status %||% NULL
  error_text <- payload$error %||% payload$result$error %||% payload$full_result$error %||% NULL
  if (!is.null(error_text) && nzchar(trimws(as.character(error_text)))) {
    return(trimws(as.character(error_text)))
  }
  if (!is.null(status) && identical(tolower(as.character(status)), "error")) {
    return("ACP call returned status=error")
  }
  NULL
}

.studyAgentSlashClearWorkflowErrors <- function(errors,
                                                step = NULL,
                                                role = NULL,
                                                cohort_id = NULL,
                                                row_index = NULL,
                                                domain_key = NULL) {
  if (!length(errors)) return(errors)
  Filter(function(item) {
    if (!is.null(step) && identical(as.character(item$step %||% ""), as.character(step))) {
      if (!is.null(role) && !identical(as.character(item$role %||% ""), as.character(role %||% ""))) return(TRUE)
      if (!is.null(cohort_id) && !identical(item$cohort_definition_id %||% NULL, cohort_id)) return(TRUE)
      if (!is.null(row_index) && !identical(item$row_index %||% NULL, row_index)) return(TRUE)
      if (!is.null(domain_key) && !identical(as.character(item$domain_key %||% ""), as.character(domain_key %||% ""))) return(TRUE)
      return(FALSE)
    }
    TRUE
  }, errors)
}

.studyAgentSlashAppendWorkflowError <- function(errors,
                                                step,
                                                role,
                                                cohort_id,
                                                cohort_name,
                                                phenotype_name,
                                                message,
                                                path = NULL,
                                                row_index = NULL,
                                                domain_key = NULL) {
  if (is.null(message) || !nzchar(trimws(as.character(message)))) return(errors)
  errors[[length(errors) + 1L]] <- Filter(
    Negate(is.null),
    list(
      step = as.character(step),
      role = as.character(role %||% ""),
      cohort_definition_id = cohort_id,
      cohort_name = as.character(cohort_name %||% ""),
      phenotype_name = as.character(phenotype_name %||% ""),
      domain_key = as.character(domain_key %||% ""),
      row_index = row_index,
      message = trimws(as.character(message)),
      artifact_path = path
    )
  )
  errors
}

.studyAgentSlashEmitKeeperStage <- function(stage_callback, step, role = "", context = list()) {
  if (!is.function(stage_callback)) return(invisible(NULL))
  stage_callback(
    step = as.character(step %||% ""),
    role = as.character(role %||% ""),
    context = compact_workflow_dialogue_context(context %||% list())
  )
  invisible(NULL)
}

.studyAgentSlashNormalizeStageGateResult <- function(result) {
  if (is.null(result)) return(list(action = "continue", updates = list()))
  if (!is.list(result)) result <- list(action = as.character(result))
  action <- tolower(trimws(as.character(result$action %||% "continue")))
  if (!nzchar(action)) action <- "continue"
  updates <- result$updates %||% list()
  if (!is.list(updates)) updates <- as.list(updates)
  list(action = action, updates = updates)
}

.studyAgentSlashInvokeKeeperStageGate <- function(stage_gate, step, role = "", context = list()) {
  if (!is.function(stage_gate)) return(list(action = "continue", updates = list()))
  result <- tryCatch(
    stage_gate(
      step = as.character(step %||% ""),
      role = as.character(role %||% ""),
      context = compact_workflow_dialogue_context(context %||% list())
    ),
    error = function(e) list(action = "continue", error = conditionMessage(e))
  )
  .studyAgentSlashNormalizeStageGateResult(result)
}

.studyAgentSlashValidateKeeperPositiveInteger <- function(value, label, min_value = 1L) {
  parsed <- suppressWarnings(as.integer(value))
  if (length(parsed) == 0 || is.na(parsed) || parsed < min_value) {
    stop(sprintf("%s must be an integer >= %s.", label, min_value))
  }
  as.integer(parsed)
}

.studyAgentSlashValidateKeeperOptionalInteger <- function(value, label, min_value = 1L) {
  if (is.null(value) || length(value) == 0) return(NULL)
  if (is.character(value) && length(value) == 1L && !nzchar(trimws(value))) return(NULL)
  parsed <- suppressWarnings(as.integer(value))
  if (length(parsed) == 0 || is.na(parsed) || parsed < min_value) {
    stop(sprintf("%s must be NULL or an integer >= %s.", label, min_value))
  }
  as.integer(parsed)
}

.studyAgentSlashApplyDomainGateUpdates <- function(current_candidate_limit, current_min_record_count, updates) {
  if (!is.list(updates) || length(updates) == 0) {
    return(list(candidate_limit = current_candidate_limit, min_record_count = current_min_record_count))
  }
  next_candidate_limit <- current_candidate_limit
  next_min_record_count <- current_min_record_count
  if (!is.null(updates$candidate_limit)) {
    next_candidate_limit <- .studyAgentSlashValidateKeeperPositiveInteger(updates$candidate_limit, "candidate_limit")
  }
  if ("min_record_count" %in% names(updates)) {
    next_min_record_count <- .studyAgentSlashValidateKeeperOptionalInteger(updates$min_record_count, "min_record_count")
  }
  list(candidate_limit = next_candidate_limit, min_record_count = next_min_record_count)
}

.studyAgentSlashApplyReviewGateUpdates <- function(current_review_row_limit,
                                                   current_review_row_selection,
                                                   current_resume_reviews,
                                                   updates) {
  if (!is.list(updates) || length(updates) == 0) {
    return(list(
      review_row_limit = current_review_row_limit,
      review_row_selection = current_review_row_selection,
      resume_reviews = current_resume_reviews
    ))
  }
  next_review_row_limit <- current_review_row_limit
  next_review_row_selection <- current_review_row_selection
  next_resume_reviews <- current_resume_reviews
  if (!is.null(updates$review_row_limit)) {
    next_review_row_limit <- .studyAgentSlashValidateKeeperPositiveInteger(updates$review_row_limit, "review_row_limit")
  }
  if ("review_row_selection" %in% names(updates)) {
    value <- updates$review_row_selection
    if (is.null(value) || (is.character(value) && length(value) == 1L && !nzchar(trimws(value))) || (length(value) == 0)) {
      next_review_row_selection <- NULL
    } else {
      next_review_row_selection <- as.character(value)
    }
  }
  if ("resume_reviews" %in% names(updates) && !is.null(updates$resume_reviews)) {
    next_resume_reviews <- isTRUE(updates$resume_reviews)
  }
  list(
    review_row_limit = next_review_row_limit,
    review_row_selection = next_review_row_selection,
    resume_reviews = next_resume_reviews
  )
}

.studyAgentSlashSetDomainRun <- function(domain_runs, domain_key, run) {
  domain_key <- as.character(domain_key %||% "")
  existing <- which(vapply(domain_runs, function(item) {
    identical(as.character(item$domain_key %||% ""), domain_key)
  }, logical(1)))
  if (length(existing) > 0) {
    domain_runs[[existing[[1]]]] <- run
  } else {
    domain_runs[[length(domain_runs) + 1L]] <- run
  }
  domain_runs
}

.studyAgentSlashCollectDomainConceptSets <- function(domain_runs) {
  concept_sets <- list()
  for (run in domain_runs) {
    run_sets <- run$concept_sets %||% list()
    if (length(run_sets) > 0) concept_sets <- c(concept_sets, run_sets)
  }
  concept_sets
}

.studyAgentSlashWriteGeneratedDomainPayload <- function(path,
                                                        role,
                                                        cohort_id,
                                                        phenotype_name,
                                                        domain_runs,
                                                        candidate_limit,
                                                        min_record_count) {
  concept_sets <- .studyAgentSlashCollectDomainConceptSets(domain_runs)
  has_error <- any(vapply(domain_runs, function(run) {
    identical(as.character(run$status %||% ""), "error")
  }, logical(1)))
  payload <- list(
    status = if (isTRUE(has_error)) "error" else "ok",
    role = role,
    cohort_definition_id = cohort_id,
    phenotype_name = phenotype_name,
    candidate_limit = as.integer(candidate_limit),
    min_record_count = if (is.null(min_record_count)) NULL else as.integer(min_record_count),
    domain_keys = as.list(vapply(domain_runs, function(run) as.character(run$domain_key %||% ""), character(1))),
    domain_runs = domain_runs,
    concept_sets = concept_sets
  )
  .studyAgentSlashWriteJson(payload, path)
  payload
}

.studyAgentSlashUpdateStudyAgentState <- function(state_path,
                                                  state_key,
                                                  state_value,
                                                  state_path_value,
                                                  artifact_paths = list()) {
  state <- if (file.exists(state_path)) .studyAgentSlashReadJson(state_path, simplify = FALSE) else list()
  state[[paste0(state_key, "_state_path")]] <- state_path_value
  state[[paste0(state_key, "_artifacts")]] <- artifact_paths
  state[[paste0(state_key, "_summary")]] <- state_value$cohorts %||% list()
  .studyAgentSlashWriteJson(state, state_path)
}

.studyAgentSlashPrepareKeeperWorkflowContext <- function(base_dir,
                                                         execution_settings_path,
                                                         cohort_id_map_path,
                                                         cohort_roles_path,
                                                         intent_path,
                                                         acp_url,
                                                         acp_timeout_seconds,
                                                         review_roles,
                                                         stage_callback,
                                                         stage_gate) {
  previous_acp_timeout <- Sys.getenv("ACP_TIMEOUT", unset = NA_character_)
  if (is.na(acp_timeout_seconds) || acp_timeout_seconds <= 0) acp_timeout_seconds <- 300
  Sys.setenv(ACP_TIMEOUT = as.character(acp_timeout_seconds))
  on.exit({
    if (is.na(previous_acp_timeout)) Sys.unsetenv("ACP_TIMEOUT")
    else Sys.setenv(ACP_TIMEOUT = previous_acp_timeout)
  }, add = TRUE)

  if (is.null(base_dir) || !nzchar(trimws(as.character(base_dir)))) {
    stop("Provide a non-empty base_dir.")
  }
  if (!file.exists(execution_settings_path)) {
    stop("Execution settings file not found: ", execution_settings_path)
  }
  if (!file.exists(cohort_id_map_path)) {
    stop("Cohort id map not found: ", cohort_id_map_path)
  }

  base_dir <- normalizePath(base_dir, winslash = "/", mustWork = FALSE)
  execution_settings_path <- normalizePath(execution_settings_path, winslash = "/", mustWork = FALSE)
  cohort_id_map_path <- normalizePath(cohort_id_map_path, winslash = "/", mustWork = FALSE)
  if (!is.null(intent_path) && nzchar(intent_path)) {
    intent_path <- normalizePath(intent_path, winslash = "/", mustWork = FALSE)
  }
  if (!is.null(cohort_roles_path) && file.exists(cohort_roles_path)) {
    cohort_roles_path <- normalizePath(cohort_roles_path, winslash = "/", mustWork = FALSE)
  }

  output_dir <- file.path(base_dir, "outputs")
  keeper_dir <- file.path(base_dir, "keeper-case-review")
  generated_dir <- file.path(keeper_dir, "concept-sets-generated")
  approved_dir <- file.path(keeper_dir, "concept-sets-approved")
  rows_dir <- file.path(keeper_dir, "rows")
  reviews_dir <- file.path(keeper_dir, "reviews")
  for (path in c(output_dir, keeper_dir, generated_dir, approved_dir, rows_dir, reviews_dir)) {
    .studyAgentSlashEnsureDir(path)
  }

  exec <- readStrategusExecutionSettings(execution_settings_path)
  id_map <- .studyAgentSlashReadMapping(cohort_id_map_path)
  intent_payload <- .studyAgentSlashIntentCore(intent_path)
  available_roles <- unique(as.character(id_map$role %||% character(0)))
  review_roles <- as.character(review_roles %||% character(0))
  if (!length(review_roles)) {
    review_roles <- if ("outcome" %in% available_roles) "outcome" else available_roles
  }
  selected_map <- id_map[as.character(id_map$role) %in% review_roles, , drop = FALSE]
  if (nrow(selected_map) == 0) {
    stop("No cohorts matched review_roles in cohort_id_map.json")
  }

  client <- .studyAgentSlashCreateAcpClient(url = acp_url, check = TRUE)
  list(
    base_dir = base_dir,
    output_dir = output_dir,
    execution_settings_path = execution_settings_path,
    cohort_id_map_path = cohort_id_map_path,
    cohort_roles_path = if (!is.null(cohort_roles_path) && file.exists(cohort_roles_path)) cohort_roles_path else NULL,
    intent_path = if (!is.null(intent_path) && file.exists(intent_path)) intent_path else NULL,
    acp_url = acp_url,
    acp_timeout_seconds = as.numeric(acp_timeout_seconds),
    keeper_dir = keeper_dir,
    generated_dir = generated_dir,
    approved_dir = approved_dir,
    rows_dir = rows_dir,
    reviews_dir = reviews_dir,
    exec = exec,
    intent_payload = intent_payload,
    selected_map = selected_map,
    review_roles = review_roles,
    stage_callback = stage_callback,
    stage_gate = stage_gate,
    client = client
  )
}

.studyAgentSlashKeeperConceptSetStep <- function(context,
                                                 selected_row,
                                                 role_phenotypes,
                                                 domain_keys,
                                                 candidate_limit,
                                                 min_record_count,
                                                 include_diagnostics,
                                                 auto_approve_generated,
                                                 overwrite_approved_concept_sets,
                                                 reuse_generated_concept_sets,
                                                 workflow_errors) {
  role <- as.character(selected_row$role[[1]] %||% "")
  cohort_id <- suppressWarnings(as.integer(selected_row$cohort_id[[1]]))
  cohort_name <- as.character(selected_row$cohort_name[[1]] %||% sprintf("Cohort %s", cohort_id))
  phenotype_name <- .studyAgentSlashInferPhenotypeName(role, cohort_id, cohort_name, context$intent_payload, role_phenotypes)
  prefix <- sprintf("%s_%s", role, cohort_id)
  generated_path <- file.path(context$generated_dir, sprintf("%s_concept_sets.json", prefix))
  approved_path <- file.path(context$approved_dir, sprintf("%s_concept_sets.json", prefix))

  current_candidate_limit <- candidate_limit
  current_min_record_count <- min_record_count
  generated_source <- "generated"

  if (isTRUE(reuse_generated_concept_sets) && file.exists(generated_path)) {
    generated_payload <- .studyAgentSlashReadJson(generated_path, simplify = FALSE)
    generated_source <- "reused"
  } else {
    domain_runs <- list()
    for (domain_key in as.character(domain_keys)) {
      before_domain_context <- list(
        phenotype_name = phenotype_name,
        cohort_id = cohort_id,
        cohort_name = cohort_name,
        review_roles = as.list(context$review_roles),
        domain_key = domain_key,
        domain_keys = as.list(domain_keys),
        candidate_limit = as.integer(current_candidate_limit),
        min_record_count = if (is.null(current_min_record_count)) NULL else as.integer(current_min_record_count),
        generated_concept_sets_path = generated_path,
        approved_concept_sets_path = approved_path,
        review_status = "before_domain_generation"
      )
      .studyAgentSlashEmitKeeperStage(context$stage_callback, "keeper_concept_set_generation_before", role = role, context = before_domain_context)
      before_domain_gate <- .studyAgentSlashInvokeKeeperStageGate(context$stage_gate, "keeper_concept_set_generation_before", role = role, context = before_domain_context)
      domain_settings <- .studyAgentSlashApplyDomainGateUpdates(current_candidate_limit, current_min_record_count, before_domain_gate$updates)
      current_candidate_limit <- domain_settings$candidate_limit
      current_min_record_count <- domain_settings$min_record_count

      if (identical(before_domain_gate$action, "skip_domain")) {
        skipped_run <- list(
          domain_key = domain_key,
          status = "skipped",
          source = "skipped_by_user",
          candidate_limit = as.integer(current_candidate_limit),
          min_record_count = if (is.null(current_min_record_count)) NULL else as.integer(current_min_record_count),
          concept_set_count = 0L,
          concept_sets = list()
        )
        domain_runs <- .studyAgentSlashSetDomainRun(domain_runs, domain_key, skipped_run)
        generated_payload <- .studyAgentSlashWriteGeneratedDomainPayload(
          path = generated_path,
          role = role,
          cohort_id = cohort_id,
          phenotype_name = phenotype_name,
          domain_runs = domain_runs,
          candidate_limit = current_candidate_limit,
          min_record_count = current_min_record_count
        )
        .studyAgentSlashEmitKeeperStage(context$stage_callback, "keeper_concept_set_generation_after", role = role, context = c(before_domain_context, list(
          generated_concept_set_count = 0L,
          total_generated_concept_set_count = length(.studyAgentSlashExtractConceptSets(generated_payload)),
          generated_source = "skipped_by_user",
          review_status = "domain_skipped"
        )))
        .studyAgentSlashInvokeKeeperStageGate(context$stage_gate, "keeper_concept_set_generation_after", role = role, context = before_domain_context)
        next
      }

      repeat {
        domain_payload <- .studyAgentSlashSafeCall(
          .studyAgentSlashAcpKeeperConceptSetsGenerate(
            client = context$client,
            phenotype = phenotype_name,
            domain_keys = domain_key,
            candidate_limit = current_candidate_limit,
            min_record_count = current_min_record_count,
            include_diagnostics = include_diagnostics
          )
        )
        domain_error <- .studyAgentSlashPayloadErrorMessage(domain_payload)
        workflow_errors <- .studyAgentSlashClearWorkflowErrors(
          workflow_errors,
          step = "keeper_concept_set_generation",
          role = role,
          cohort_id = cohort_id,
          domain_key = domain_key
        )
        workflow_errors <- .studyAgentSlashAppendWorkflowError(
          workflow_errors,
          step = "keeper_concept_set_generation",
          role = role,
          cohort_id = cohort_id,
          cohort_name = cohort_name,
          phenotype_name = phenotype_name,
          message = domain_error,
          path = generated_path,
          domain_key = domain_key
        )
        domain_concept_sets <- .studyAgentSlashExtractConceptSets(domain_payload)
        domain_run <- list(
          domain_key = domain_key,
          status = as.character(domain_payload$status %||% if (is.null(domain_error)) "ok" else "error"),
          source = "generated",
          candidate_limit = as.integer(current_candidate_limit),
          min_record_count = if (is.null(current_min_record_count)) NULL else as.integer(current_min_record_count),
          concept_set_count = length(domain_concept_sets),
          error = domain_error,
          concept_sets = domain_concept_sets
        )
        domain_runs <- .studyAgentSlashSetDomainRun(domain_runs, domain_key, domain_run)
        generated_payload <- .studyAgentSlashWriteGeneratedDomainPayload(
          path = generated_path,
          role = role,
          cohort_id = cohort_id,
          phenotype_name = phenotype_name,
          domain_runs = domain_runs,
          candidate_limit = current_candidate_limit,
          min_record_count = current_min_record_count
        )
        after_domain_context <- list(
          phenotype_name = phenotype_name,
          cohort_id = cohort_id,
          cohort_name = cohort_name,
          review_roles = as.list(context$review_roles),
          domain_key = domain_key,
          domain_keys = as.list(domain_keys),
          candidate_limit = as.integer(current_candidate_limit),
          min_record_count = if (is.null(current_min_record_count)) NULL else as.integer(current_min_record_count),
          generated_concept_set_count = length(domain_concept_sets),
          total_generated_concept_set_count = length(.studyAgentSlashExtractConceptSets(generated_payload)),
          generated_concept_sets_path = generated_path,
          approved_concept_sets_path = approved_path,
          generated_source = "generated",
          review_status = if (is.null(domain_error)) "domain_generated" else "domain_error"
        )
        .studyAgentSlashEmitKeeperStage(context$stage_callback, "keeper_concept_set_generation_after", role = role, context = after_domain_context)
        after_domain_gate <- .studyAgentSlashInvokeKeeperStageGate(context$stage_gate, "keeper_concept_set_generation_after", role = role, context = after_domain_context)
        domain_settings <- .studyAgentSlashApplyDomainGateUpdates(current_candidate_limit, current_min_record_count, after_domain_gate$updates)
        current_candidate_limit <- domain_settings$candidate_limit
        current_min_record_count <- domain_settings$min_record_count
        if (identical(after_domain_gate$action, "rerun_domain")) next
        break
      }
    }
  }

  generated_error <- .studyAgentSlashPayloadErrorMessage(generated_payload)
  workflow_errors <- .studyAgentSlashAppendWorkflowError(
    workflow_errors,
    step = "keeper_concept_set_generation",
    role = role,
    cohort_id = cohort_id,
    cohort_name = cohort_name,
    phenotype_name = phenotype_name,
    message = generated_error,
    path = generated_path
  )
  generated_concept_sets <- .studyAgentSlashExtractConceptSets(generated_payload)

  approved_source <- "reused"
  if (isTRUE(overwrite_approved_concept_sets)) {
    approved_source <- "overwritten_from_generated"
    approved_payload <- list(
      status = "seeded_from_generated",
      role = role,
      cohort_definition_id = cohort_id,
      phenotype_name = phenotype_name,
      concept_sets = generated_concept_sets,
      source_generated_artifact = generated_path,
      replaced_existing_approved = isTRUE(file.exists(approved_path))
    )
    .studyAgentSlashWriteJson(approved_payload, approved_path)
  } else if (file.exists(approved_path)) {
    approved_payload <- .studyAgentSlashReadJson(approved_path, simplify = FALSE)
  } else if (isTRUE(auto_approve_generated)) {
    approved_source <- "seeded_from_generated"
    approved_payload <- list(
      status = "seeded_from_generated",
      role = role,
      cohort_definition_id = cohort_id,
      phenotype_name = phenotype_name,
      concept_sets = generated_concept_sets,
      source_generated_artifact = generated_path
    )
    .studyAgentSlashWriteJson(approved_payload, approved_path)
  } else {
    approved_source <- "missing"
    approved_payload <- list(
      status = "missing_approved_concept_sets",
      role = role,
      cohort_definition_id = cohort_id,
      phenotype_name = phenotype_name,
      concept_sets = list()
    )
  }

  list(
    summary = list(
      role = role,
      cohort_definition_id = cohort_id,
      cohort_name = cohort_name,
      phenotype_name = phenotype_name,
      generated_concept_sets_path = generated_path,
      approved_concept_sets_path = approved_path,
      domain_runs = generated_payload$domain_runs %||% list(),
      generated_concept_set_count = length(generated_concept_sets),
      approved_concept_set_count = length(.studyAgentSlashExtractConceptSets(approved_payload)),
      generated_concept_sets_source = generated_source,
      approved_concept_sets_source = approved_source,
      concept_generation_status = generated_payload$status %||% "ok"
    ),
    workflow_errors = workflow_errors
  )
}

.studyAgentSlashKeeperCaseReviewStep <- function(context,
                                                 selected_row,
                                                 role_phenotypes,
                                                 sample_size,
                                                 review_row_limit,
                                                 use_descendants,
                                                 remove_pii,
                                                 reuse_rows,
                                                 resume_reviews,
                                                 review_row_selection,
                                                 workflow_errors) {
  role <- as.character(selected_row$role[[1]] %||% "")
  cohort_id <- suppressWarnings(as.integer(selected_row$cohort_id[[1]]))
  cohort_name <- as.character(selected_row$cohort_name[[1]] %||% sprintf("Cohort %s", cohort_id))
  phenotype_name <- .studyAgentSlashInferPhenotypeName(role, cohort_id, cohort_name, context$intent_payload, role_phenotypes)
  prefix <- sprintf("%s_%s", role, cohort_id)
  generated_path <- file.path(context$generated_dir, sprintf("%s_concept_sets.json", prefix))
  approved_path <- file.path(context$approved_dir, sprintf("%s_concept_sets.json", prefix))
  rows_path <- file.path(context$rows_dir, sprintf("%s_rows.json", prefix))
  rows_csv_path <- file.path(context$rows_dir, sprintf("%s_rows.csv", prefix))
  review_path <- file.path(context$reviews_dir, sprintf("%s_reviews.json", prefix))
  review_csv_path <- file.path(context$reviews_dir, sprintf("%s_reviews.csv", prefix))

  if (!file.exists(approved_path)) {
    stop(sprintf("Approved concept sets not found for role '%s' cohort %s: %s", role, cohort_id, approved_path))
  }
  approved_payload <- .studyAgentSlashReadJson(approved_path, simplify = FALSE)
  approved_concept_sets <- .studyAgentSlashExtractConceptSets(approved_payload)

  rows_source <- "generated"
  rows_payload <- if (length(approved_concept_sets)) {
    if (isTRUE(reuse_rows) && file.exists(rows_path)) {
      rows_source <- "reused"
      .studyAgentSlashReadJson(rows_path, simplify = FALSE)
    } else {
      payload <- .studyAgentSlashSafeCall(
        .studyAgentSlashAcpKeeperProfilesGenerate(
          client = context$client,
          cohort_database_schema = context$exec$workDatabaseSchema,
          cohort_table = context$exec$cohortTable,
          cohort_definition_id = cohort_id,
          cdm_database_schema = context$exec$cdmDatabaseSchema,
          keeper_concept_sets = approved_concept_sets,
          sample_size = sample_size,
          phenotype_name = phenotype_name,
          use_descendants = use_descendants,
          remove_pii = remove_pii
        )
      )
      .studyAgentSlashWriteJson(payload, rows_path)
      payload
    }
  } else {
    rows_source <- "missing_approved_concept_sets"
    list(status = "error", error = "no approved concept sets", rows = list())
  }
  rows_error <- .studyAgentSlashPayloadErrorMessage(rows_payload)
  workflow_errors <- .studyAgentSlashAppendWorkflowError(
    workflow_errors,
    step = "keeper_profile_generation",
    role = role,
    cohort_id = cohort_id,
    cohort_name = cohort_name,
    phenotype_name = phenotype_name,
    message = rows_error,
    path = rows_path
  )
  row_records <- .studyAgentSlashExtractRows(rows_payload)
  sample_size_returned <- suppressWarnings(as.integer(rows_payload$sample_size_returned %||% rows_payload$result$sample_size_returned %||% rows_payload$full_result$sample_size_returned %||% length(row_records)))
  if (is.na(sample_size_returned)) sample_size_returned <- length(row_records)
  profile_record_count <- suppressWarnings(as.integer(rows_payload$diagnostics$record_count %||% rows_payload$result$diagnostics$record_count %||% rows_payload$full_result$diagnostics$record_count %||% 0L))
  if (is.na(profile_record_count)) profile_record_count <- 0L
  if (identical(rows_payload$status %||% "ok", "ok") && sample_size_returned <= 0L) {
    workflow_errors <- .studyAgentSlashAppendWorkflowError(
      workflow_errors,
      step = "keeper_profile_generation",
      role = role,
      cohort_id = cohort_id,
      cohort_name = cohort_name,
      phenotype_name = phenotype_name,
      message = "Keeper profile generation returned zero sampled cohort rows. Confirm the MCP DB connection string points to the same database the R workflow used when generating cohorts, then verify the configured cohort table contains rows for this cohort_definition_id.",
      path = rows_path
    )
  } else if (identical(rows_payload$status %||% "ok", "ok") && length(row_records) <= 0L) {
    workflow_errors <- .studyAgentSlashAppendWorkflowError(
      workflow_errors,
      step = "keeper_profile_generation",
      role = role,
      cohort_id = cohort_id,
      cohort_name = cohort_name,
      phenotype_name = phenotype_name,
      message = sprintf("Keeper profile generation sampled %s cohort row(s) but produced zero review rows. Extracted profile record count: %s.", sample_size_returned, profile_record_count),
      path = rows_path
    )
  }
  row_df <- .studyAgentSlashRecordsToDataFrame(row_records)
  if (nrow(row_df) > 0) utils::write.csv(row_df, rows_csv_path, row.names = FALSE)

  current_review_row_limit <- review_row_limit
  current_review_row_selection <- review_row_selection
  current_resume_reviews <- isTRUE(resume_reviews)
  before_review_context <- list(
    phenotype_name = phenotype_name,
    cohort_id = cohort_id,
    cohort_name = cohort_name,
    review_roles = as.list(context$review_roles),
    generated_concept_sets_path = generated_path,
    approved_concept_sets_path = approved_path,
    rows_path = rows_path,
    rows_csv_path = if (file.exists(rows_csv_path)) rows_csv_path else NULL,
    reviews_path = review_path,
    row_count = length(row_records),
    review_row_limit = as.integer(current_review_row_limit),
    review_row_selection = if (is.null(current_review_row_selection)) NULL else as.character(current_review_row_selection),
    resume_reviews = isTRUE(current_resume_reviews),
    review_status = "before_case_review"
  )
  .studyAgentSlashEmitKeeperStage(context$stage_callback, "keeper_case_review_before", role = role, context = before_review_context)
  review_gate <- .studyAgentSlashInvokeKeeperStageGate(context$stage_gate, "keeper_case_review_before", role = role, context = before_review_context)
  review_settings <- .studyAgentSlashApplyReviewGateUpdates(
    current_review_row_limit,
    current_review_row_selection,
    current_resume_reviews,
    review_gate$updates
  )
  current_review_row_limit <- review_settings$review_row_limit
  current_review_row_selection <- review_settings$review_row_selection
  current_resume_reviews <- review_settings$resume_reviews

  review_source <- "generated"
  review_records <- list()
  if (isTRUE(current_resume_reviews) && file.exists(review_path)) {
    existing_review_payload <- .studyAgentSlashReadJson(review_path, simplify = FALSE)
    review_records <- .studyAgentSlashExtractReviews(existing_review_payload)
    if (length(review_records) > 0) review_source <- "resumed"
  }
  selected_row_indices <- .studyAgentSlashParseRowSelection(current_review_row_selection, length(row_records), current_review_row_limit)
  if (length(selected_row_indices) > 0) {
    reviewed_indices <- unique(vapply(review_records, function(rec) {
      suppressWarnings(as.integer(rec$row_index %||% NA_integer_))
    }, integer(1)))
    reviewed_indices <- reviewed_indices[!is.na(reviewed_indices)]
    pending_row_indices <- selected_row_indices[!selected_row_indices %in% reviewed_indices]
    .studyAgentSlashEmitKeeperStage(context$stage_callback, "keeper_case_review", role = role, context = list(
      phenotype_name = phenotype_name,
      cohort_id = cohort_id,
      cohort_name = cohort_name,
      review_roles = as.list(context$review_roles),
      generated_concept_sets_path = generated_path,
      approved_concept_sets_path = approved_path,
      rows_path = rows_path,
      reviews_path = review_path,
      row_count = length(row_records),
      reviewed_row_count = length(review_records),
      review_row_limit = as.integer(current_review_row_limit),
      selected_row_indices = as.list(selected_row_indices),
      pending_row_indices = as.list(pending_row_indices),
      review_status = if (length(pending_row_indices)) "reviewing_rows" else "all_selected_rows_already_reviewed"
    ))
    for (row_index in pending_row_indices) {
      .studyAgentSlashEmitKeeperStage(context$stage_callback, "keeper_case_review", role = role, context = list(
        phenotype_name = phenotype_name,
        cohort_id = cohort_id,
        cohort_name = cohort_name,
        review_roles = as.list(context$review_roles),
        generated_concept_sets_path = generated_path,
        approved_concept_sets_path = approved_path,
        rows_path = rows_path,
        reviews_path = review_path,
        row_count = length(row_records),
        current_row_index = row_index,
        reviewed_row_count = length(review_records),
        review_row_limit = as.integer(current_review_row_limit),
        selected_row_indices = as.list(selected_row_indices),
        pending_row_indices = as.list(pending_row_indices),
        review_status = "reviewing_rows"
      ))
      keeper_row <- row_records[[row_index]]
      review_payload <- .studyAgentSlashSafeCall(
        .studyAgentSlashAcpPhenotypeValidationReview(
          client = context$client,
          disease_name = phenotype_name,
          keeper_row_path = rows_path,
          row_index = row_index
        )
      )
      review_error <- .studyAgentSlashPayloadErrorMessage(review_payload)
      workflow_errors <- .studyAgentSlashAppendWorkflowError(
        workflow_errors,
        step = "keeper_case_review",
        role = role,
        cohort_id = cohort_id,
        cohort_name = cohort_name,
        phenotype_name = phenotype_name,
        message = review_error,
        path = review_path,
        row_index = row_index
      )
      review_records[[length(review_records) + 1L]] <- c(
        list(
          row_index = row_index,
          role = role,
          cohort_definition_id = cohort_id,
          phenotype_name = phenotype_name,
          label = .studyAgentSlashExtractReviewValue(review_payload, "label"),
          rationale = .studyAgentSlashExtractReviewValue(review_payload, "rationale"),
          mode = .studyAgentSlashExtractReviewValue(review_payload, "mode"),
          error = review_payload$error %||% NULL
        ),
        keeper_row
      )
    }
  } else if (length(row_records) > 0) {
    .studyAgentSlashEmitKeeperStage(context$stage_callback, "keeper_case_review", role = role, context = list(
      phenotype_name = phenotype_name,
      cohort_id = cohort_id,
      cohort_name = cohort_name,
      review_roles = as.list(context$review_roles),
      generated_concept_sets_path = generated_path,
      approved_concept_sets_path = approved_path,
      rows_path = rows_path,
      reviews_path = review_path,
      row_count = length(row_records),
      reviewed_row_count = length(review_records),
      review_row_limit = as.integer(current_review_row_limit),
      selected_row_indices = list(),
      pending_row_indices = list(),
      review_status = "no_rows_selected_for_review"
    ))
  }

  review_payload_out <- list(
    role = role,
    cohort_definition_id = cohort_id,
    phenotype_name = phenotype_name,
    reviewed_row_count = length(review_records),
    review_row_limit = as.integer(current_review_row_limit),
    review_row_selection = if (is.null(current_review_row_selection)) NULL else as.character(current_review_row_selection),
    reviews = review_records
  )
  .studyAgentSlashWriteJson(review_payload_out, review_path)
  review_df <- .studyAgentSlashRecordsToDataFrame(review_records)
  if (nrow(review_df) > 0) utils::write.csv(review_df, review_csv_path, row.names = FALSE)

  after_review_context <- list(
    phenotype_name = phenotype_name,
    cohort_id = cohort_id,
    cohort_name = cohort_name,
    review_roles = as.list(context$review_roles),
    generated_concept_sets_path = generated_path,
    approved_concept_sets_path = approved_path,
    rows_path = rows_path,
    rows_csv_path = if (file.exists(rows_csv_path)) rows_csv_path else NULL,
    reviews_path = review_path,
    reviews_csv_path = if (file.exists(review_csv_path)) review_csv_path else NULL,
    row_count = length(row_records),
    reviewed_row_count = length(review_records),
    review_row_limit = as.integer(current_review_row_limit),
    selected_row_indices = as.list(selected_row_indices),
    review_status = "after_case_review"
  )
  .studyAgentSlashEmitKeeperStage(context$stage_callback, "keeper_case_review_after", role = role, context = after_review_context)
  .studyAgentSlashInvokeKeeperStageGate(context$stage_gate, "keeper_case_review_after", role = role, context = after_review_context)

  list(
    summary = list(
      role = role,
      cohort_definition_id = cohort_id,
      cohort_name = cohort_name,
      phenotype_name = phenotype_name,
      generated_concept_sets_path = generated_path,
      approved_concept_sets_path = approved_path,
      rows_path = rows_path,
      reviews_path = review_path,
      approved_concept_set_count = length(approved_concept_sets),
      row_count = length(row_records),
      reviewed_row_count = length(review_records),
      review_row_limit = as.integer(current_review_row_limit),
      review_row_selection = if (is.null(current_review_row_selection)) NULL else as.character(current_review_row_selection),
      resume_reviews = isTRUE(current_resume_reviews),
      selected_row_indices = as.list(selected_row_indices),
      rows_source = rows_source,
      reviews_source = review_source,
      row_generation_status = rows_payload$status %||% "ok",
      sample_size_returned = sample_size_returned,
      profile_record_count = profile_record_count,
      review_error_count = sum(vapply(review_records, function(rec) {
        err <- rec$error %||% NULL
        !is.null(err) && nzchar(trimws(as.character(err)))
      }, logical(1)))
    ),
    workflow_errors = workflow_errors
  )
}
