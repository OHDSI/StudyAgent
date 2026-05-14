#' Run ACP-based Keeper review workflow for selected cohorts
#' @param base_dir workflow base directory
#' @param execution_settings_path path to strategus-execution-settings.json
#' @param cohort_id_map_path path to outputs/cohort_id_map.json
#' @param cohort_roles_path optional path to outputs/cohort_roles.json
#' @param intent_path optional path to intent split JSON used to infer phenotype labels
#' @param acp_url ACP base URL
#' @param acp_timeout_seconds ACP HTTP timeout in seconds; defaults to ACP_TIMEOUT or 300
#' @param review_roles cohort roles to process, defaults to outcome-first
#' @param role_phenotypes optional named overrides by role or cohort id
#' @param domain_keys Keeper concept-set domains to request
#' @param candidate_limit ACP concept candidate limit
#' @param min_record_count optional minimum record count filter
#' @param sample_size requested profile sample size per cohort
#' @param review_row_limit maximum number of generated rows to review per cohort
#' @param include_diagnostics whether to request ACP diagnostics
#' @param use_descendants whether profile generation should include descendants
#' @param remove_pii whether to enforce PII removal for generated rows
#' @param auto_approve_generated when TRUE, seed approved concept sets from generated output when no approved file exists
#' @param overwrite_approved_concept_sets when TRUE, replace approved concept sets with the current generated concept sets
#' @param reuse_generated_concept_sets when TRUE, reuse existing generated concept-set artifacts
#' @param reuse_rows when TRUE, reuse existing generated Keeper row artifacts
#' @param resume_reviews when TRUE, continue from saved review artifacts instead of restarting
#' @param review_row_selection optional review row indices or range string such as "1-3,5"; overrides the default first-N selection
#' @return invisible list summarizing artifact paths and per-cohort status
#' @export
runKeeperReviewWorkflow <- function(base_dir,
                                    execution_settings_path = file.path(base_dir, "strategus-execution-settings.json"),
                                    cohort_id_map_path = file.path(base_dir, "outputs", "cohort_id_map.json"),
                                    cohort_roles_path = file.path(base_dir, "outputs", "cohort_roles.json"),
                                    intent_path = NULL,
                                    acp_url = Sys.getenv("ACP_URL", "http://127.0.0.1:8765"),
                                    acp_timeout_seconds = as.numeric(Sys.getenv("ACP_TIMEOUT", "300")),
                                    review_roles = c("outcome"),
                                    role_phenotypes = NULL,
                                    stage_callback = NULL,
                                    domain_keys = c(
                                      "doi",
                                      #"alternativeDiagnosis",
                                      #"symptoms",
                                      "drugs",
                                      #"diagnosticProcedures",
                                      #"measurements",
                                      #"treatmentProcedures",
                                      "complications"
                                    ),
                                    candidate_limit = 10,
                                    min_record_count = NULL,
                                    sample_size = 5,
                                    review_row_limit = 5,
                                    include_diagnostics = TRUE,
                                    use_descendants = TRUE,
                                    remove_pii = TRUE,
                                    auto_approve_generated = TRUE,
                                    overwrite_approved_concept_sets = FALSE,
                                    reuse_generated_concept_sets = TRUE,
                                    reuse_rows = TRUE,
                                    resume_reviews = TRUE,
                                    review_row_selection = NULL) {
  `%||%` <- function(x, y) if (is.null(x)) y else x

  ensure_dir <- function(path) {
    if (!dir.exists(path)) dir.create(path, recursive = TRUE, showWarnings = FALSE)
  }

  read_json <- function(path, simplify = FALSE) {
    jsonlite::fromJSON(path, simplifyVector = simplify)
  }

  write_json <- function(x, path) {
    jsonlite::write_json(x, path, pretty = TRUE, auto_unbox = TRUE, null = "null")
  }

  as_named_record <- function(x) {
    if (!is.list(x)) return(list(value = x))
    x
  }

  records_to_data_frame <- function(records) {
    records <- Filter(Negate(is.null), lapply(records, as_named_record))
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

  read_mapping <- function(path) {
    payload <- read_json(path, simplify = TRUE)
    mapping <- payload$mapping %||% payload
    if (is.null(mapping) || NROW(mapping) == 0) {
      stop("No cohort mapping found in: ", path)
    }
    as.data.frame(mapping, stringsAsFactors = FALSE)
  }

  intent_core <- function(path) {
    if (is.null(path) || !nzchar(path) || !file.exists(path)) return(list())
    payload <- read_json(path, simplify = FALSE)
    payload$intent_split %||% payload
  }

  infer_phenotype_name <- function(role, cohort_id, cohort_name, intent_payload, overrides = NULL) {
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

  extract_concept_sets <- function(payload) {
    payload$concept_sets %||% payload$result$concept_sets %||% payload$full_result$concept_sets %||% list()
  }

  extract_rows <- function(payload) {
    payload$rows %||% payload$result$rows %||% payload$full_result$rows %||% list()
  }

  extract_review_value <- function(payload, field) {
    payload[[field]] %||% payload$result[[field]] %||% payload$full_result[[field]] %||% NULL
  }

  extract_reviews <- function(payload) {
    payload$reviews %||% payload$result$reviews %||% payload$full_result$reviews %||% list()
  }

  parse_row_selection <- function(selection, total_rows, default_limit) {
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
            lo <- min(bounds)
            hi <- max(bounds)
            parsed <- c(parsed, seq.int(lo, hi))
          }
        } else {
          parsed <- c(parsed, suppressWarnings(as.integer(part)))
        }
      }
      indices <- parsed
    } else {
      indices <- suppressWarnings(as.integer(unlist(selection, use.names = FALSE)))
    }

    indices <- indices[!is.na(indices)]
    indices <- indices[indices >= 1L & indices <= total_rows]
    indices <- unique(indices)
    if (!length(indices)) return(integer(0))
    indices
  }

  safe_call <- function(expr) {
    tryCatch(expr, error = function(e) {
      list(status = "error", error = conditionMessage(e))
    })
  }

  payload_error_message <- function(payload) {
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

  append_workflow_error <- function(errors,
                                    step,
                                    role,
                                    cohort_id,
                                    cohort_name,
                                    phenotype_name,
                                    message,
                                    path = NULL,
                                    row_index = NULL) {
    if (is.null(message) || !nzchar(trimws(as.character(message)))) return(errors)
    errors[[length(errors) + 1L]] <- Filter(
      Negate(is.null),
      list(
        step = as.character(step),
        role = as.character(role %||% ""),
        cohort_definition_id = cohort_id,
        cohort_name = as.character(cohort_name %||% ""),
        phenotype_name = as.character(phenotype_name %||% ""),
        row_index = row_index,
        message = trimws(as.character(message)),
        artifact_path = path
      )
    )
    errors
  }

  emit_stage <- function(step, role = "", context = list()) {
    if (!is.function(stage_callback)) return(invisible(NULL))
    stage_callback(
      step = as.character(step %||% ""),
      role = as.character(role %||% ""),
      context = compact_workflow_dialogue_context(context %||% list())
    )
    invisible(NULL)
  }

  previous_acp_timeout <- Sys.getenv("ACP_TIMEOUT", unset = NA_character_)
  if (is.na(acp_timeout_seconds) || acp_timeout_seconds <= 0) acp_timeout_seconds <- 300
  Sys.setenv(ACP_TIMEOUT = as.character(acp_timeout_seconds))
  on.exit({
    if (is.na(previous_acp_timeout)) Sys.unsetenv("ACP_TIMEOUT")
    else Sys.setenv(ACP_TIMEOUT = previous_acp_timeout)
  }, add = TRUE)

  update_study_agent_state <- function(state_path, keeper_state_path, keeper_dir, summary) {
    state <- if (file.exists(state_path)) read_json(state_path, simplify = FALSE) else list()
    state$keeper_review_state_path <- keeper_state_path
    state$keeper_review_artifacts <- list(
      keeper_dir = keeper_dir,
      concept_sets_generated = file.path(keeper_dir, "concept-sets-generated"),
      concept_sets_approved = file.path(keeper_dir, "concept-sets-approved"),
      rows = file.path(keeper_dir, "rows"),
      reviews = file.path(keeper_dir, "reviews")
    )
    state$keeper_review_summary <- summary
    write_json(state, state_path)
  }

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
  for (path in c(output_dir, keeper_dir, generated_dir, approved_dir, rows_dir, reviews_dir)) ensure_dir(path)

  exec <- readStrategusExecutionSettings(execution_settings_path)
  id_map <- read_mapping(cohort_id_map_path)
  intent_payload <- intent_core(intent_path)
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
  summary_rows <- vector("list", nrow(selected_map))
  workflow_errors <- list()

  for (i in seq_len(nrow(selected_map))) {
    role <- as.character(selected_map$role[[i]] %||% "")
    cohort_id <- suppressWarnings(as.integer(selected_map$cohort_id[[i]]))
    cohort_name <- as.character(selected_map$cohort_name[[i]] %||% sprintf("Cohort %s", cohort_id))
    phenotype_name <- infer_phenotype_name(role, cohort_id, cohort_name, intent_payload, role_phenotypes)
    prefix <- sprintf("%s_%s", role, cohort_id)

    generated_path <- file.path(generated_dir, sprintf("%s_concept_sets.json", prefix))
    approved_path <- file.path(approved_dir, sprintf("%s_concept_sets.json", prefix))
    rows_path <- file.path(rows_dir, sprintf("%s_rows.json", prefix))
    rows_csv_path <- file.path(rows_dir, sprintf("%s_rows.csv", prefix))
    review_path <- file.path(reviews_dir, sprintf("%s_reviews.json", prefix))
    review_csv_path <- file.path(reviews_dir, sprintf("%s_reviews.csv", prefix))

    emit_stage(
      "keeper_concept_set_generation",
      role = role,
      context = list(
        phenotype_name = phenotype_name,
        cohort_id = cohort_id,
        cohort_name = cohort_name,
        review_roles = as.list(review_roles),
        domain_keys = as.list(domain_keys),
        review_status = "generating_concept_sets",
        generated_concept_sets_path = generated_path,
        approved_concept_sets_path = approved_path
      )
    )

    generated_source <- "generated"
    if (isTRUE(reuse_generated_concept_sets) && file.exists(generated_path)) {
      generated_payload <- read_json(generated_path, simplify = FALSE)
      generated_source <- "reused"
    } else {
      generated_payload <- safe_call(
        .studyAgentSlashAcpKeeperConceptSetsGenerate(
          client = client,
          phenotype = phenotype_name,
          domain_keys = domain_keys,
          candidate_limit = candidate_limit,
          min_record_count = min_record_count,
          include_diagnostics = include_diagnostics
        )
      )
      write_json(generated_payload, generated_path)
    }
    generated_error <- payload_error_message(generated_payload)
    workflow_errors <- append_workflow_error(
      workflow_errors,
      step = "keeper_concept_set_generation",
      role = role,
      cohort_id = cohort_id,
      cohort_name = cohort_name,
      phenotype_name = phenotype_name,
      message = generated_error,
      path = generated_path
    )
    generated_concept_sets <- extract_concept_sets(generated_payload)

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
      write_json(approved_payload, approved_path)
    } else if (file.exists(approved_path)) {
      approved_payload <- read_json(approved_path, simplify = FALSE)
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
      write_json(approved_payload, approved_path)
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
    approved_concept_sets <- extract_concept_sets(approved_payload)

    rows_source <- "generated"
    rows_payload <- if (length(approved_concept_sets)) {
      if (isTRUE(reuse_rows) && file.exists(rows_path)) {
        rows_source <- "reused"
        read_json(rows_path, simplify = FALSE)
      } else {
        payload <- safe_call(
          .studyAgentSlashAcpKeeperProfilesGenerate(
            client = client,
            cohort_database_schema = exec$workDatabaseSchema,
            cohort_table = exec$cohortTable,
            cohort_definition_id = cohort_id,
            cdm_database_schema = exec$cdmDatabaseSchema,
            keeper_concept_sets = approved_concept_sets,
            sample_size = sample_size,
            phenotype_name = phenotype_name,
            use_descendants = use_descendants,
            remove_pii = remove_pii
          )
        )
        write_json(payload, rows_path)
        payload
      }
    } else {
      rows_source <- "missing_approved_concept_sets"
      list(status = "error", error = "no approved concept sets", rows = list())
    }
    rows_error <- payload_error_message(rows_payload)
    workflow_errors <- append_workflow_error(
      workflow_errors,
      step = "keeper_profile_generation",
      role = role,
      cohort_id = cohort_id,
      cohort_name = cohort_name,
      phenotype_name = phenotype_name,
      message = rows_error,
      path = rows_path
    )
    row_records <- extract_rows(rows_payload)
    row_df <- records_to_data_frame(row_records)
    if (nrow(row_df) > 0) utils::write.csv(row_df, rows_csv_path, row.names = FALSE)

    review_source <- "generated"
    review_records <- list()
    if (isTRUE(resume_reviews) && file.exists(review_path)) {
      existing_review_payload <- read_json(review_path, simplify = FALSE)
      review_records <- extract_reviews(existing_review_payload)
      if (length(review_records) > 0) review_source <- "resumed"
    }
    selected_row_indices <- parse_row_selection(review_row_selection, length(row_records), review_row_limit)
    if (length(selected_row_indices) > 0) {
      reviewed_indices <- unique(vapply(review_records, function(rec) {
        suppressWarnings(as.integer(rec$row_index %||% NA_integer_))
      }, integer(1)))
      reviewed_indices <- reviewed_indices[!is.na(reviewed_indices)]
      pending_row_indices <- selected_row_indices[!selected_row_indices %in% reviewed_indices]
      emit_stage(
        "keeper_case_review",
        role = role,
        context = list(
          phenotype_name = phenotype_name,
          cohort_id = cohort_id,
          cohort_name = cohort_name,
          review_roles = as.list(review_roles),
          generated_concept_sets_path = generated_path,
          approved_concept_sets_path = approved_path,
          rows_path = rows_path,
          reviews_path = review_path,
          row_count = length(row_records),
          reviewed_row_count = length(review_records),
          review_row_limit = as.integer(review_row_limit),
          selected_row_indices = as.list(selected_row_indices),
          pending_row_indices = as.list(pending_row_indices),
          review_status = if (length(pending_row_indices)) "reviewing_rows" else "all_selected_rows_already_reviewed"
        )
      )
      for (row_index in pending_row_indices) {
        emit_stage(
          "keeper_case_review",
          role = role,
          context = list(
            phenotype_name = phenotype_name,
            cohort_id = cohort_id,
            cohort_name = cohort_name,
            review_roles = as.list(review_roles),
            generated_concept_sets_path = generated_path,
            approved_concept_sets_path = approved_path,
            rows_path = rows_path,
            reviews_path = review_path,
            row_count = length(row_records),
            current_row_index = row_index,
            reviewed_row_count = length(review_records),
            review_row_limit = as.integer(review_row_limit),
            selected_row_indices = as.list(selected_row_indices),
            pending_row_indices = as.list(pending_row_indices),
            review_status = "reviewing_rows"
          )
        )
        keeper_row <- row_records[[row_index]]
        review_payload <- safe_call(
          .studyAgentSlashAcpPhenotypeValidationReview(
            client = client,
            disease_name = phenotype_name,
            keeper_row = keeper_row
          )
        )
        review_error <- payload_error_message(review_payload)
        workflow_errors <- append_workflow_error(
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
        review_records[[length(review_records) + 1]] <- c(
          list(
            row_index = row_index,
            role = role,
            cohort_definition_id = cohort_id,
            phenotype_name = phenotype_name,
            label = extract_review_value(review_payload, "label"),
            rationale = extract_review_value(review_payload, "rationale"),
            mode = extract_review_value(review_payload, "mode"),
            error = review_payload$error %||% NULL
          ),
          keeper_row
        )
      }
    } else if (length(row_records) > 0) {
      emit_stage(
        "keeper_case_review",
        role = role,
        context = list(
          phenotype_name = phenotype_name,
          cohort_id = cohort_id,
          cohort_name = cohort_name,
          review_roles = as.list(review_roles),
          generated_concept_sets_path = generated_path,
          approved_concept_sets_path = approved_path,
          rows_path = rows_path,
          reviews_path = review_path,
          row_count = length(row_records),
          reviewed_row_count = length(review_records),
          review_row_limit = as.integer(review_row_limit),
          selected_row_indices = list(),
          pending_row_indices = list(),
          review_status = "no_rows_selected_for_review"
        )
      )
    }

    review_payload_out <- list(
      role = role,
      cohort_definition_id = cohort_id,
      phenotype_name = phenotype_name,
      reviewed_row_count = length(review_records),
      review_row_limit = as.integer(review_row_limit),
      reviews = review_records
    )
    write_json(review_payload_out, review_path)
    review_df <- records_to_data_frame(review_records)
    if (nrow(review_df) > 0) utils::write.csv(review_df, review_csv_path, row.names = FALSE)

    summary_rows[[i]] <- list(
      role = role,
      cohort_definition_id = cohort_id,
      cohort_name = cohort_name,
      phenotype_name = phenotype_name,
      generated_concept_sets_path = generated_path,
      approved_concept_sets_path = approved_path,
      rows_path = rows_path,
      reviews_path = review_path,
      generated_concept_set_count = length(generated_concept_sets),
      approved_concept_set_count = length(approved_concept_sets),
      row_count = length(row_records),
      reviewed_row_count = length(review_records),
      selected_row_indices = as.list(selected_row_indices),
      generated_concept_sets_source = generated_source,
      approved_concept_sets_source = approved_source,
      rows_source = rows_source,
      reviews_source = review_source,
      concept_generation_status = generated_payload$status %||% "ok",
      row_generation_status = rows_payload$status %||% "ok",
      review_error_count = sum(vapply(review_records, function(rec) {
        err <- rec$error %||% NULL
        !is.null(err) && nzchar(trimws(as.character(err)))
      }, logical(1)))
    )
  }

  workflow_status <- if (length(workflow_errors)) "error" else "ok"
  workflow_message <- if (length(workflow_errors)) {
    sprintf("Keeper review encountered %s ACP error(s).", length(workflow_errors))
  } else {
    "Keeper review completed without ACP errors."
  }

  keeper_state <- list(
    status = workflow_status,
    message = workflow_message,
    error_count = length(workflow_errors),
    errors = workflow_errors,
    base_dir = base_dir,
    execution_settings_path = execution_settings_path,
    cohort_id_map_path = cohort_id_map_path,
    acp_url = acp_url,
    acp_timeout_seconds = as.numeric(acp_timeout_seconds),
    cohort_roles_path = if (!is.null(cohort_roles_path) && file.exists(cohort_roles_path)) cohort_roles_path else NULL,
    intent_path = if (!is.null(intent_path) && file.exists(intent_path)) intent_path else NULL,
    keeper_dir = keeper_dir,
    review_roles = as.list(review_roles),
    domain_keys = as.list(domain_keys),
    sample_size = as.integer(sample_size),
    review_row_limit = as.integer(review_row_limit),
    review_row_selection = if (is.null(review_row_selection)) NULL else as.character(review_row_selection),
    overwrite_approved_concept_sets = isTRUE(overwrite_approved_concept_sets),
    reuse_generated_concept_sets = isTRUE(reuse_generated_concept_sets),
    reuse_rows = isTRUE(reuse_rows),
    resume_reviews = isTRUE(resume_reviews),
    cohorts = summary_rows
  )
  keeper_state_path <- file.path(output_dir, "keeper_review_state.json")
  write_json(keeper_state, keeper_state_path)
  update_study_agent_state(file.path(output_dir, "study_agent_state.json"), keeper_state_path, keeper_dir, summary_rows)

  invisible(c(keeper_state, list(keeper_review_state_path = keeper_state_path)))
}
