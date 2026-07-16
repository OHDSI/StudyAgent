.studyAgentSlashReadCsvSafe <- function(path) {
  if (is.null(path) || !nzchar(trimws(as.character(path))) || !file.exists(path)) {
    return(NULL)
  }
  data <- tryCatch(
    utils::read.csv(path, stringsAsFactors = FALSE, check.names = FALSE),
    error = function(e) NULL
  )
  if (is.null(data)) return(NULL)
  names(data) <- sub("^\ufeff", "", names(data), useBytes = TRUE)
  data
}

.studyAgentSlashReadJsonSafe <- function(path, simplifyVector = FALSE) {
  if (is.null(path) || !nzchar(trimws(as.character(path))) || !file.exists(path)) {
    return(NULL)
  }
  tryCatch(
    jsonlite::fromJSON(path, simplifyVector = simplifyVector),
    error = function(e) NULL
  )
}

.studyAgentSlashReadRdsSafe <- function(path) {
  if (is.null(path) || !nzchar(trimws(as.character(path))) || !file.exists(path)) {
    return(NULL)
  }
  tryCatch(readRDS(path), error = function(e) NULL)
}

.studyAgentSlashCompactPreviewTable <- function(data, max_rows = 12L, max_cols = 8L) {
  if (is.null(data)) return(NULL)
  if (!is.data.frame(data)) data <- as.data.frame(data, stringsAsFactors = FALSE)
  if (ncol(data) > max_cols) data <- data[, seq_len(max_cols), drop = FALSE]
  utils::head(data, n = max_rows)
}


.studyAgentSlashSupportsDataViewer <- function() {
  isTRUE(interactive()) &&
    exists("View", where = asNamespace("utils"), mode = "function", inherits = FALSE)
}

.studyAgentSlashOpenTableViewer <- function(data, title = "Study Agent") {
  if (!isTRUE(.studyAgentSlashSupportsDataViewer()) || is.null(data)) return(FALSE)
  if (!is.data.frame(data)) data <- as.data.frame(data, stringsAsFactors = FALSE)
  if (exists(".studyAgentSlashPrepareViewerTable", mode = "function")) {
    data <- .studyAgentSlashPrepareViewerTable(data)
  }
  utils::View(data, title = as.character(title %||% "Study Agent"))
  TRUE
}

.studyAgentSlashNormalizeExecutionTableDisplay <- function(display = c("console", "viewer", "auto")) {
  match.arg(as.character(display %||% "console"), c("console", "viewer", "auto"))
}

.studyAgentSlashResolveExecutionTableDisplay <- function(display = NULL, viewer = FALSE) {
  supports_viewer <- isTRUE(.studyAgentSlashSupportsDataViewer())
  if (is.null(display)) {
    return(list(
      show_console = TRUE,
      open_viewer = isTRUE(viewer) && supports_viewer,
      supports_viewer = supports_viewer
    ))
  }
  normalized <- .studyAgentSlashNormalizeExecutionTableDisplay(display)
  if (identical(normalized, "console")) {
    return(list(show_console = TRUE, open_viewer = FALSE, supports_viewer = supports_viewer))
  }
  if (supports_viewer) {
    return(list(show_console = FALSE, open_viewer = TRUE, supports_viewer = TRUE))
  }
  list(show_console = TRUE, open_viewer = FALSE, supports_viewer = FALSE)
}

.studyAgentSlashExplorationTableSection <- function(data,
                                                    title,
                                                    preview_data = NULL) {
  list(
    kind = "table",
    data = preview_data %||% data,
    view_data = data,
    view_title = as.character(title %||% "Study Agent")
  )
}

.studyAgentSlashDiscoverKeeperReviewCsvPaths <- function(base_dir) {
  reviews_dir <- file.path(base_dir, "keeper-case-review", "reviews")
  if (!dir.exists(reviews_dir)) return(character(0))
  sort(list.files(reviews_dir, pattern = "_reviews\\.csv$", full.names = TRUE))
}

.studyAgentSlashSummarizeKeeperReviewMetrics <- function(data) {
  if (is.null(data) || !is.data.frame(data) || nrow(data) <= 0) {
    return(NULL)
  }
  labels <- tolower(trimws(as.character(data$label %||% character(nrow(data)))))
  yes_count <- sum(labels == "yes", na.rm = TRUE)
  no_count <- sum(labels == "no", na.rm = TRUE)
  unknown_count <- sum(labels == "unknown" | !nzchar(labels), na.rm = TRUE)
  reviewed_rows <- nrow(data)
  evaluable_rows <- yes_count + no_count
  precision_ppv <- if (evaluable_rows > 0) yes_count / evaluable_rows else NA_real_
  data.frame(
    reviewed_rows = reviewed_rows,
    yes_count = yes_count,
    no_count = no_count,
    unknown_count = unknown_count,
    evaluable_rows = evaluable_rows,
    precision_ppv = precision_ppv,
    recall_estimate = NA_real_,
    recall_note = "Not estimable from a reviewed sample drawn only from cohort-positive rows.",
    stringsAsFactors = FALSE
  )
}


.studyAgentSlashDiscoverDiagnosticsRoots <- function(base_dir, project_state = NULL) {
  project_state <- project_state %||% tryCatch(.studyAgentSlashReadProjectState(base_dir), error = function(e) list())
  study_context <- project_state$study_context %||% list()
  exec_roots <- .studyAgentSlashConfiguredExecutionRoots(base_dir, project_state = project_state, prefer_confirmed = TRUE)
  candidates <- c(
    as.character(study_context$cm_diagnostics_dir %||% ""),
    as.character(study_context$cm_results_dir %||% ""),
    file.path(base_dir, "cm-diagnostics"),
    file.path(base_dir, "cm-results"),
    as.character(exec_roots$results_root %||% ""),
    as.character(exec_roots$work_root %||% ""),
    as.character(exec_roots$configured_results_root %||% ""),
    as.character(exec_roots$configured_work_root %||% "")
  )
  candidates <- unique(Filter(nzchar, trimws(as.character(candidates))))
  resolved <- unique(vapply(candidates, function(item) {
    .studyAgentSlashResolveArtifactPath(item, base_dir)
  }, character(1)))
  existing <- Filter(dir.exists, resolved)
  expanded <- unique(unlist(lapply(existing, function(root) {
    module_root <- file.path(root, "CohortDiagnosticsModule")
    if (dir.exists(module_root)) {
      return(module_root)
    }
    root
  }), use.names = FALSE))
  Filter(dir.exists, expanded)
}

.studyAgentSlashClassifyDiagnosticsArtifact <- function(path) {
  name <- tolower(basename(as.character(path %||% "")))
  if (grepl("^cd_orphan_concept\\.csv$", name)) return("orphan_concepts")
  if (grepl("^cd_visit_context\\.csv$", name)) return("visit_context")
  if (grepl("^cd_included_source_concept\\.csv$", name)) return("source_concepts")
  if (grepl("^cd_index_event_breakdown\\.csv$", name)) return("index_event_breakdown")
  if (grepl("^cd_incidence_rate\\.csv$", name)) return("incidence_rate")
  if (grepl("^cd_temporal_", name)) return("temporal_characterization")
  if (grepl("^cd_cohort_inclusion\\.csv$", name) || grepl("^cd_cohort_inc_", name) || grepl("^cd_cohort_summary_stats\\.csv$", name)) return("inclusion_statistics")
  if (grepl("^cd_cohort\\.csv$", name)) return("cohort_reference")
  if (grepl("^cd_concept\\.csv$", name)) return("concept_reference")
  if (grepl("^cd_concept_sets\\.csv$", name)) return("concept_set_reference")
  if (grepl("^cd_relationship\\.csv$", name)) return("relationship_reference")
  if (grepl("^cd_concept_relationship\\.csv$", name)) return("concept_relationship_reference")
  if (grepl("^cd_", name) && grepl("source", name) && grepl("concept", name)) return("source_concepts")
  if (grepl("^cd_", name) && grepl("orphan", name)) return("orphan_concepts")
  if (grepl("^cd_", name) && grepl("visit", name) && grepl("context", name)) return("visit_context")
  "other"
}

.studyAgentSlashReadDiagnosticsTable <- function(base_dir, file_name, project_state = NULL) {
  inventory <- .studyAgentSlashDiagnosticsInventoryTable(base_dir, project_state = project_state)
  if (nrow(inventory) <= 0) return(NULL)
  matches <- inventory[tolower(basename(inventory$absolute_path)) == tolower(file_name), , drop = FALSE]
  if (nrow(matches) <= 0) return(NULL)
  .studyAgentSlashReadCsvSafe(matches$absolute_path[[1]])
}

.studyAgentSlashDiagnosticsLookupContext <- function(base_dir, project_state = NULL) {
  concept_data <- .studyAgentSlashReadDiagnosticsTable(base_dir, "cd_concept.csv", project_state = project_state)
  cohort_data <- .studyAgentSlashReadDiagnosticsTable(base_dir, "cd_cohort.csv", project_state = project_state)
  concept_lookup <- if (!is.null(concept_data) && all(c("concept_id", "concept_name") %in% names(concept_data))) {
    unique(concept_data[, intersect(c("concept_id", "concept_name", "domain_id", "vocabulary_id", "concept_class_id"), names(concept_data)), drop = FALSE])
  } else {
    NULL
  }
  cohort_lookup <- if (!is.null(cohort_data) && all(c("cohort_id", "cohort_name") %in% names(cohort_data))) {
    unique(cohort_data[, intersect(c("cohort_id", "cohort_name"), names(cohort_data)), drop = FALSE])
  } else {
    NULL
  }
  list(
    concept_lookup = concept_lookup,
    cohort_lookup = cohort_lookup
  )
}

.studyAgentSlashEnrichDiagnosticsWithLookups <- function(data, base_dir, project_state = NULL) {
  if (is.null(data) || !is.data.frame(data) || nrow(data) <= 0) return(data)
  lookups <- .studyAgentSlashDiagnosticsLookupContext(base_dir, project_state = project_state)
  cohort_lookup <- lookups$cohort_lookup
  concept_lookup <- lookups$concept_lookup
  if (!is.null(cohort_lookup) && "cohort_id" %in% names(data)) {
    data <- merge(data, cohort_lookup, by = "cohort_id", all.x = TRUE, sort = FALSE)
  }
  if (!is.null(concept_lookup) && "concept_id" %in% names(data)) {
    standard_lookup <- concept_lookup
    names(standard_lookup)[names(standard_lookup) == "concept_name"] <- "concept_name"
    data <- merge(data, standard_lookup, by = "concept_id", all.x = TRUE, sort = FALSE)
  }
  if (!is.null(concept_lookup) && "source_concept_id" %in% names(data)) {
    source_lookup <- concept_lookup
    names(source_lookup)[names(source_lookup) == "concept_id"] <- "source_concept_id"
    names(source_lookup)[names(source_lookup) == "concept_name"] <- "source_concept_name"
    keep_names <- intersect(c("source_concept_id", "source_concept_name", "domain_id", "vocabulary_id", "concept_class_id"), names(source_lookup))
    source_lookup <- unique(source_lookup[, keep_names, drop = FALSE])
    data <- merge(data, source_lookup, by = "source_concept_id", all.x = TRUE, sort = FALSE)
  }
  if (!is.null(concept_lookup) && "visit_concept_id" %in% names(data)) {
    visit_lookup <- concept_lookup
    names(visit_lookup)[names(visit_lookup) == "concept_id"] <- "visit_concept_id"
    names(visit_lookup)[names(visit_lookup) == "concept_name"] <- "visit_concept_name"
    keep_names <- intersect(c("visit_concept_id", "visit_concept_name"), names(visit_lookup))
    visit_lookup <- unique(visit_lookup[, keep_names, drop = FALSE])
    data <- merge(data, visit_lookup, by = "visit_concept_id", all.x = TRUE, sort = FALSE)
  }
  data
}

.studyAgentSlashSummarizeDiagnosticsOrphanConcepts <- function(base_dir, project_state = NULL) {
  inventory <- .studyAgentSlashDiagnosticsFilesByClass(base_dir, classes = c("orphan_concepts"), project_state = project_state)
  if (nrow(inventory) <= 0) return(NULL)
  tables <- lapply(as.character(inventory$absolute_path), .studyAgentSlashReadCsvSafe)
  tables <- Filter(function(x) !is.null(x) && is.data.frame(x) && nrow(x) > 0, tables)
  if (length(tables) <= 0) return(NULL)
  data <- do.call(rbind, tables)
  data <- .studyAgentSlashEnrichDiagnosticsWithLookups(data, base_dir = base_dir, project_state = project_state)
  if ("concept_subjects" %in% names(data)) data$concept_subjects <- suppressWarnings(as.numeric(data$concept_subjects))
  if ("concept_count" %in% names(data)) data$concept_count <- suppressWarnings(as.numeric(data$concept_count))
  order_cols <- intersect(c("cohort_id", "cohort_name", "concept_set_id", "concept_id", "concept_name", "domain_id", "vocabulary_id", "concept_subjects", "concept_count"), names(data))
  if ("concept_subjects" %in% names(data)) {
    data <- data[order(-data$concept_subjects, -data$concept_count), , drop = FALSE]
  }
  data[, order_cols, drop = FALSE]
}

.studyAgentSlashSummarizeDiagnosticsSourceConcepts <- function(base_dir, project_state = NULL) {
  inventory <- .studyAgentSlashDiagnosticsFilesByClass(base_dir, classes = c("source_concepts"), project_state = project_state)
  if (nrow(inventory) <= 0) return(NULL)
  tables <- lapply(as.character(inventory$absolute_path), .studyAgentSlashReadCsvSafe)
  tables <- Filter(function(x) !is.null(x) && is.data.frame(x) && nrow(x) > 0, tables)
  if (length(tables) <= 0) return(NULL)
  data <- do.call(rbind, tables)
  data <- .studyAgentSlashEnrichDiagnosticsWithLookups(data, base_dir = base_dir, project_state = project_state)
  if ("concept_subjects" %in% names(data)) data$concept_subjects <- suppressWarnings(as.numeric(data$concept_subjects))
  if ("concept_count" %in% names(data)) data$concept_count <- suppressWarnings(as.numeric(data$concept_count))
  order_cols <- intersect(c("cohort_id", "cohort_name", "concept_set_id", "source_concept_id", "source_concept_name", "concept_id", "concept_name", "domain_id", "vocabulary_id", "concept_subjects", "concept_count"), names(data))
  if ("concept_subjects" %in% names(data)) {
    data <- data[order(-data$concept_subjects, -data$concept_count), , drop = FALSE]
  }
  data[, order_cols, drop = FALSE]
}

.studyAgentSlashSummarizeDiagnosticsVisitContext <- function(base_dir, project_state = NULL) {
  inventory <- .studyAgentSlashDiagnosticsFilesByClass(base_dir, classes = c("visit_context"), project_state = project_state)
  if (nrow(inventory) <= 0) return(NULL)
  tables <- lapply(as.character(inventory$absolute_path), .studyAgentSlashReadCsvSafe)
  tables <- Filter(function(x) !is.null(x) && is.data.frame(x) && nrow(x) > 0, tables)
  if (length(tables) <= 0) return(NULL)
  data <- do.call(rbind, tables)
  data <- .studyAgentSlashEnrichDiagnosticsWithLookups(data, base_dir = base_dir, project_state = project_state)
  if ("subjects" %in% names(data)) data$subjects <- suppressWarnings(as.numeric(data$subjects))
  if (all(c("cohort_id", "subjects") %in% names(data))) {
    totals <- stats::aggregate(list(total_subjects = data$subjects), by = list(cohort_id = data$cohort_id), FUN = sum, na.rm = TRUE)
    data <- merge(data, totals, by = "cohort_id", all.x = TRUE, sort = FALSE)
    data$subject_pct <- ifelse(is.finite(data$total_subjects) & data$total_subjects > 0, data$subjects / data$total_subjects, NA_real_)
  }
  order_cols <- intersect(c("cohort_id", "cohort_name", "visit_context", "visit_concept_id", "visit_concept_name", "subjects", "subject_pct"), names(data))
  if ("subjects" %in% names(data)) {
    data <- data[order(-data$subjects, data$cohort_id), , drop = FALSE]
  }
  data[, order_cols, drop = FALSE]
}

.studyAgentSlashDiagnosticsInventoryTable <- function(base_dir, project_state = NULL) {
  roots <- .studyAgentSlashDiscoverDiagnosticsRoots(base_dir, project_state = project_state)
  if (length(roots) == 0) {
    return(data.frame(
      root = character(0),
      relative_path = character(0),
      artifact_class = character(0),
      size_bytes = numeric(0),
      modified_at = character(0),
      stringsAsFactors = FALSE
    ))
  }
  rows <- list()
  for (root in roots) {
    paths <- list.files(root, recursive = TRUE, full.names = TRUE, all.files = FALSE, no.. = TRUE)
    if (length(paths) == 0) next
    info <- file.info(paths)
    root_prefix <- paste0(normalizePath(root, winslash = "/", mustWork = FALSE), "/")
    normalized_paths <- normalizePath(paths, winslash = "/", mustWork = FALSE)
    rel <- ifelse(startsWith(normalized_paths, root_prefix), substr(normalized_paths, nchar(root_prefix) + 1L, nchar(normalized_paths)), normalized_paths)
    rows[[length(rows) + 1L]] <- data.frame(
      root = .studyAgentSlashRelativizeProjectPath(root, base_dir),
      relative_path = rel,
      artifact_class = vapply(paths, .studyAgentSlashClassifyDiagnosticsArtifact, character(1)),
      size_bytes = as.numeric(info$size),
      modified_at = as.character(info$mtime),
      absolute_path = normalizePath(paths, winslash = "/", mustWork = FALSE),
      stringsAsFactors = FALSE
    )
  }
  if (length(rows) == 0) {
    return(data.frame(
      root = character(0),
      relative_path = character(0),
      artifact_class = character(0),
      size_bytes = numeric(0),
      modified_at = character(0),
      absolute_path = character(0),
      stringsAsFactors = FALSE
    ))
  }
  do.call(rbind, rows)
}

.studyAgentSlashDiagnosticsFilesByClass <- function(base_dir, classes, project_state = NULL) {
  inventory <- .studyAgentSlashDiagnosticsInventoryTable(base_dir, project_state = project_state)
  if (nrow(inventory) == 0) return(inventory)
  inventory[inventory$artifact_class %in% as.character(classes %||% character(0)), , drop = FALSE]
}

.studyAgentSlashDiagnosticsPreviewSections <- function(inventory, title_prefix = "Diagnostics artifact") {
  if (is.null(inventory) || !is.data.frame(inventory) || nrow(inventory) == 0) return(list())
  sections <- list(
    .studyAgentSlashExplorationTableSection(
      data = inventory[, intersect(c("root", "relative_path", "artifact_class", "size_bytes", "modified_at"), names(inventory)), drop = FALSE],
      title = paste(title_prefix, "inventory"),
      preview_data = .studyAgentSlashCompactPreviewTable(inventory[, intersect(c("root", "relative_path", "artifact_class", "size_bytes", "modified_at"), names(inventory)), drop = FALSE], max_rows = 20L, max_cols = 5L)
    )
  )
  preview_paths <- utils::head(as.character(inventory$absolute_path %||% character(0)), n = 3L)
  for (preview_path in preview_paths) {
    data <- .studyAgentSlashReadCsvSafe(preview_path)
    if (is.null(data)) next
    sections[[length(sections) + 1L]] <- list(kind = "text", text = sprintf("%s: %s", title_prefix, preview_path))
    sections[[length(sections) + 1L]] <- .studyAgentSlashExplorationTableSection(
      data = data,
      title = basename(preview_path),
      preview_data = .studyAgentSlashCompactPreviewTable(data, max_rows = 8L, max_cols = 8L)
    )
  }
  sections
}

.studyAgentSlashCompactDiagnosticsDialogueSummary <- function(base_dir, project_state = NULL, max_items = 6L) {
  inventory <- .studyAgentSlashDiagnosticsInventoryTable(base_dir, project_state = project_state)
  if (nrow(inventory) == 0) return(list())
  counts <- stats::aggregate(list(file_count = inventory$relative_path), by = list(artifact_class = inventory$artifact_class), FUN = length)
  counts <- counts[order(-counts$file_count, counts$artifact_class), , drop = FALSE]
  top_counts <- utils::head(counts, n = max_items)
  top_files <- utils::head(inventory[, intersect(c("artifact_class", "root", "relative_path"), names(inventory)), drop = FALSE], n = max_items)
  compact_workflow_dialogue_context(list(
    diagnostics_roots = as.list(unique(as.character(inventory$root %||% character(0)))),
    diagnostics_file_count = nrow(inventory),
    diagnostics_artifact_counts = lapply(seq_len(nrow(top_counts)), function(i) compact_workflow_dialogue_context(list(
      artifact_class = top_counts$artifact_class[[i]],
      file_count = as.integer(top_counts$file_count[[i]])
    ))),
    diagnostics_top_files = lapply(seq_len(nrow(top_files)), function(i) compact_workflow_dialogue_context(list(
      artifact_class = top_files$artifact_class[[i]],
      root = top_files$root[[i]],
      relative_path = top_files$relative_path[[i]]
    )))
  ))
}


.studyAgentSlashDiscoverStrategusExecutionRoots <- function(base_dir, project_state = NULL) {
  roots <- .studyAgentSlashConfiguredExecutionRoots(base_dir, project_state = project_state, prefer_confirmed = TRUE)
  list(
    results_root = roots$results_root %||% roots$configured_results_root %||% NULL,
    work_root = roots$work_root %||% roots$configured_work_root %||% NULL
  )
}

.studyAgentSlashDiscoverCmSpecRoots <- function(base_dir, project_state = NULL) {
  roots <- c(file.path(base_dir, "analysis-settings"))
  exec_roots <- .studyAgentSlashDiscoverStrategusExecutionRoots(base_dir, project_state = project_state)
  roots <- c(roots, as.character(exec_roots$results_root %||% ""), as.character(exec_roots$work_root %||% ""))
  roots <- unique(Filter(nzchar, trimws(as.character(roots))))
  resolved <- unique(vapply(roots, function(root) .studyAgentSlashResolveArtifactPath(root, base_dir), character(1)))
  Filter(dir.exists, resolved)
}

.studyAgentSlashDiscoverIncidenceResultsDir <- function(base_dir, project_state = NULL) {
  exec_roots <- .studyAgentSlashDiscoverStrategusExecutionRoots(base_dir, project_state = project_state)
  results_root <- as.character(exec_roots$results_root %||% "")
  if (!nzchar(results_root)) return(NULL)
  candidate <- file.path(results_root, "CohortIncidenceModule")
  if (!dir.exists(candidate)) return(NULL)
  candidate
}

.studyAgentSlashReadIncidenceTable <- function(base_dir, file_name, project_state = NULL) {
  root <- .studyAgentSlashDiscoverIncidenceResultsDir(base_dir, project_state = project_state)
  if (is.null(root) || !nzchar(root)) return(NULL)
  path <- file.path(root, as.character(file_name %||% ""))
  .studyAgentSlashReadCsvSafe(path)
}

.studyAgentSlashFormatIncidenceTarLabel <- function(start_with, start_offset, end_with, end_offset) {
  sprintf("%s %+d to %s %+d days", start_with %||% "start", as.integer(start_offset %||% 0L), end_with %||% "end", as.integer(end_offset %||% 0L))
}

.studyAgentSlashSummarizeIncidenceResults <- function(base_dir, project_state = NULL) {
  summary <- .studyAgentSlashReadIncidenceTable(base_dir, "ci_incidence_summary.csv", project_state = project_state)
  if (is.null(summary) || !is.data.frame(summary) || nrow(summary) <= 0) return(NULL)
  target_def <- .studyAgentSlashReadIncidenceTable(base_dir, "ci_target_def.csv", project_state = project_state)
  outcome_def <- .studyAgentSlashReadIncidenceTable(base_dir, "ci_outcome_def.csv", project_state = project_state)
  tar_def <- .studyAgentSlashReadIncidenceTable(base_dir, "ci_tar_def.csv", project_state = project_state)

  names(summary) <- toupper(names(summary))
  if (!is.null(target_def) && is.data.frame(target_def) && nrow(target_def) > 0) {
    names(target_def) <- toupper(names(target_def))
    summary <- merge(summary, unique(target_def[, intersect(c("TARGET_COHORT_DEFINITION_ID", "TARGET_NAME"), names(target_def)), drop = FALSE]), by = "TARGET_COHORT_DEFINITION_ID", all.x = TRUE, sort = FALSE)
  }
  if (!is.null(outcome_def) && is.data.frame(outcome_def) && nrow(outcome_def) > 0) {
    names(outcome_def) <- toupper(names(outcome_def))
    summary <- merge(summary, unique(outcome_def[, intersect(c("OUTCOME_ID", "OUTCOME_NAME", "OUTCOME_COHORT_DEFINITION_ID"), names(outcome_def)), drop = FALSE]), by = "OUTCOME_ID", all.x = TRUE, sort = FALSE)
  }
  if (!is.null(tar_def) && is.data.frame(tar_def) && nrow(tar_def) > 0) {
    names(tar_def) <- toupper(names(tar_def))
    summary <- merge(summary, unique(tar_def[, intersect(c("TAR_ID", "TAR_START_WITH", "TAR_START_OFFSET", "TAR_END_WITH", "TAR_END_OFFSET"), names(tar_def)), drop = FALSE]), by = "TAR_ID", all.x = TRUE, sort = FALSE)
    if (all(c("TAR_START_WITH", "TAR_START_OFFSET", "TAR_END_WITH", "TAR_END_OFFSET") %in% names(summary))) {
      summary$TAR_LABEL <- vapply(seq_len(nrow(summary)), function(i) {
        .studyAgentSlashFormatIncidenceTarLabel(
          summary$TAR_START_WITH[[i]],
          summary$TAR_START_OFFSET[[i]],
          summary$TAR_END_WITH[[i]],
          summary$TAR_END_OFFSET[[i]]
        )
      }, character(1))
    }
  }

  numeric_cols <- intersect(c("TARGET_COHORT_DEFINITION_ID", "TAR_ID", "OUTCOME_ID", "START_YEAR", "PERSONS_AT_RISK", "PERSON_DAYS", "OUTCOMES", "INCIDENCE_PROPORTION_P100P", "INCIDENCE_RATE_P100PY"), names(summary))
  for (col in numeric_cols) {
    summary[[col]] <- suppressWarnings(as.numeric(summary[[col]]))
  }
  keep <- intersect(c(
    "TARGET_COHORT_DEFINITION_ID",
    "TARGET_NAME",
    "OUTCOME_ID",
    "OUTCOME_NAME",
    "TAR_ID",
    "TAR_LABEL",
    "GENDER_NAME",
    "START_YEAR",
    "PERSONS_AT_RISK",
    "PERSON_DAYS",
    "OUTCOMES",
    "INCIDENCE_PROPORTION_P100P",
    "INCIDENCE_RATE_P100PY"
  ), names(summary))
  summary <- summary[, keep, drop = FALSE]
  order_year <- if ("START_YEAR" %in% names(summary)) ifelse(is.na(summary$START_YEAR), Inf, summary$START_YEAR) else rep(Inf, nrow(summary))
  order_tar <- if ("TAR_ID" %in% names(summary)) summary$TAR_ID else seq_len(nrow(summary))
  order_gender <- if ("GENDER_NAME" %in% names(summary)) as.character(summary$GENDER_NAME %||% "") else rep("", nrow(summary))
  summary[order(order_tar, order_year, order_gender), , drop = FALSE]
}

.studyAgentSlashIncidenceAnalysisSettingsTables <- function(base_dir, project_state = NULL) {
  tar_settings <- .studyAgentSlashReadJsonSafe(file.path(base_dir, "analysis-settings", "time_at_risk_settings.json"), simplifyVector = FALSE) %||% list()
  roles <- .studyAgentSlashReadJsonSafe(file.path(base_dir, "outputs", "cohort_roles.json"), simplifyVector = TRUE) %||% list()
  selected <- .studyAgentSlashReadCsvSafe(file.path(base_dir, "selected-cohorts", "Cohorts.csv"))
  exec_roots <- .studyAgentSlashDiscoverStrategusExecutionRoots(base_dir, project_state = project_state)
  analysis_spec_path <- file.path(base_dir, "analysis-settings", "analysisSpecification.json")

  describe_ids <- function(ids) {
    ids <- suppressWarnings(as.integer(unlist(ids %||% integer(0), use.names = FALSE)))
    ids <- ids[!is.na(ids)]
    if (length(ids) == 0) return("")
    if (!is.null(selected) && all(c("cohort_id", "cohort_name") %in% names(selected))) {
      labels <- vapply(ids, function(id) {
        match_row <- selected[selected$cohort_id == id, , drop = FALSE]
        name <- if (nrow(match_row) > 0) as.character(match_row$cohort_name[[1]] %||% id) else as.character(id)
        sprintf("%s (%s)", id, name)
      }, character(1))
      return(paste(labels, collapse = "; "))
    }
    paste(ids, collapse = ", ")
  }

  strata <- tar_settings$strata_settings %||% list()
  overview <- data.frame(
    property = c(
      "targets",
      "outcomes",
      "analysis_tar_ids",
      "strata_by_year",
      "strata_by_gender",
      "strata_by_age",
      "age_breaks",
      "analysis_specification_path",
      "results_root",
      "work_root"
    ),
    value = c(
      describe_ids(roles$targets),
      describe_ids(roles$outcomes),
      paste(unlist(tar_settings$analysis_tar_ids %||% integer(0), use.names = FALSE), collapse = ", "),
      as.character(isTRUE(strata$byYear %||% FALSE)),
      as.character(isTRUE(strata$byGender %||% FALSE)),
      as.character(isTRUE(strata$byAge %||% FALSE)),
      paste(unlist(strata$ageBreaks %||% integer(0), use.names = FALSE), collapse = ", "),
      analysis_spec_path,
      as.character(exec_roots$results_root %||% ""),
      as.character(exec_roots$work_root %||% "")
    ),
    stringsAsFactors = FALSE
  )

  tar_defs <- tar_settings$time_at_risk_defs %||% list()
  tar_table <- if (length(tar_defs) > 0) {
    do.call(rbind, lapply(tar_defs, function(def) {
      data.frame(
        tar_id = as.integer(def$id %||% NA_integer_),
        tar_name = as.character(def$name %||% ""),
        start_with = as.character(def$startWith %||% "start"),
        start_offset = as.integer(def$startOffset %||% 0L),
        end_with = as.character(def$endWith %||% "end"),
        end_offset = as.integer(def$endOffset %||% 0L),
        tar_label = .studyAgentSlashFormatIncidenceTarLabel(def$startWith, def$startOffset, def$endWith, def$endOffset),
        stringsAsFactors = FALSE
      )
    }))
  } else {
    data.frame()
  }

  list(overview = overview, tar_table = tar_table)
}

.studyAgentSlashClassifyCmSpecArtifact <- function(path) {
  path <- normalizePath(as.character(path %||% ""), winslash = "/", mustWork = FALSE)
  name <- tolower(basename(path))
  if (dir.exists(path) && grepl("characterizationmodule", name, fixed = TRUE)) return("characterization_module_dir")
  if (dir.exists(path) && grepl("cohortincidencemodule", name, fixed = TRUE)) return("cohort_incidence_module_dir")
  if (dir.exists(path) && grepl("cohortmethodmodule", name, fixed = TRUE)) return("cohort_method_module_dir")
  if (dir.exists(path) && identical(name, "analysis-settings")) return("analysis_settings_dir")
  if (grepl("/characterizationmodule/", path, fixed = TRUE)) return("characterization_output")
  if (grepl("/cohortincidencemodule/", path, fixed = TRUE)) return("cohort_incidence_output")
  if (grepl("/cohortmethodmodule/", path, fixed = TRUE)) return("cohort_method_output")
  if (identical(name, "analysisspecification.json")) return("analysis_specification_json")
  if (identical(name, "strategus_execute_result.rds")) return("strategus_execute_result_rds")
  if (identical(name, "cm_analysis_state.json")) return("cm_analysis_state_json")
  if (identical(name, "cmanalysis.json")) return("analysis_settings_json")
  if (grepl("\\.rds$", name)) return("rds")
  if (grepl("\\.json$", name)) return("json")
  if (grepl("\\.csv$", name)) return("csv")
  "other"
}

.studyAgentSlashCmSpecInventoryTable <- function(base_dir, project_state = NULL) {
  roots <- .studyAgentSlashDiscoverCmSpecRoots(base_dir, project_state = project_state)
  if (length(roots) == 0) {
    return(data.frame(
      root_path = character(0),
      relative_path = character(0),
      artifact_class = character(0),
      size_bytes = numeric(0),
      modified_at = character(0),
      absolute_path = character(0),
      stringsAsFactors = FALSE
    ))
  }
  rows <- list()
  for (root in roots) {
    root_norm <- normalizePath(root, winslash = "/", mustWork = FALSE)
    root_paths <- c(root_norm, list.files(root_norm, recursive = TRUE, full.names = TRUE, all.files = FALSE, no.. = TRUE))
    root_paths <- unique(root_paths)
    if (length(root_paths) == 0) next
    info <- file.info(root_paths)
    prefix <- paste0(root_norm, "/")
    rel <- ifelse(normalizePath(root_paths, winslash = "/", mustWork = FALSE) == root_norm, ".", ifelse(startsWith(normalizePath(root_paths, winslash = "/", mustWork = FALSE), prefix), substr(normalizePath(root_paths, winslash = "/", mustWork = FALSE), nchar(prefix) + 1L, nchar(normalizePath(root_paths, winslash = "/", mustWork = FALSE))), normalizePath(root_paths, winslash = "/", mustWork = FALSE)))
    rows[[length(rows) + 1L]] <- data.frame(
      root_path = root_norm,
      relative_path = rel,
      artifact_class = vapply(root_paths, .studyAgentSlashClassifyCmSpecArtifact, character(1)),
      size_bytes = as.numeric(info$size),
      modified_at = as.character(info$mtime),
      absolute_path = normalizePath(root_paths, winslash = "/", mustWork = FALSE),
      stringsAsFactors = FALSE
    )
  }
  if (length(rows) == 0) {
    return(data.frame(
      root_path = character(0),
      relative_path = character(0),
      artifact_class = character(0),
      size_bytes = numeric(0),
      modified_at = character(0),
      absolute_path = character(0),
      stringsAsFactors = FALSE
    ))
  }
  do.call(rbind, rows)
}

.studyAgentSlashCmSpecAnalysisState <- function(base_dir) {
  .studyAgentSlashReadJsonSafe(file.path(base_dir, "outputs", "cm_analysis_state.json"), simplifyVector = FALSE)
}

.studyAgentSlashCollapseValue <- function(x) {
  if (is.null(x)) return("")
  if (is.atomic(x) && length(x) <= 1) return(as.character(x))
  if (is.atomic(x)) return(paste(as.character(x), collapse = "; "))
  if (is.list(x)) return(paste(vapply(x, .studyAgentSlashCollapseValue, character(1)), collapse = "; "))
  as.character(x)
}

.studyAgentSlashObjectElementTable <- function(x, max_items = 20L) {
  if (is.null(x) || (!is.list(x) && !is.data.frame(x))) return(NULL)
  nms <- names(x) %||% character(0)
  if (length(nms) == 0) return(NULL)
  nms <- utils::head(nms, n = max_items)
  rows <- lapply(nms, function(nm) {
    value <- x[[nm]]
    preview <- if (is.atomic(value) && length(value) <= 5) {
      paste(utils::head(as.character(value), 5L), collapse = "; ")
    } else if (is.data.frame(value)) {
      sprintf("data.frame[%s x %s]", nrow(value), ncol(value))
    } else if (is.list(value)) {
      sprintf("list[%s]", length(value))
    } else {
      as.character(class(value)[1] %||% typeof(value))
    }
    data.frame(
      element_name = as.character(nm),
      element_class = paste(class(value), collapse = ", "),
      length = length(value),
      nrow = if (is.data.frame(value)) nrow(value) else NA_integer_,
      ncol = if (is.data.frame(value)) ncol(value) else NA_integer_,
      preview = preview,
      stringsAsFactors = FALSE
    )
  })
  do.call(rbind, rows)
}

.studyAgentSlashCompactCmSpecDialogueSummary <- function(base_dir, project_state = NULL, max_items = 6L) {
  state <- .studyAgentSlashCmSpecAnalysisState(base_dir)
  exec_roots <- .studyAgentSlashDiscoverStrategusExecutionRoots(base_dir, project_state = project_state)
  execute_summary <- .studyAgentSlashReadJsonSafe(file.path(base_dir, "analysis-settings", "strategus_execute_summary.json"), simplifyVector = FALSE)
  if (is.null(state) && !dir.exists(as.character(exec_roots$results_root %||% "")) && !dir.exists(as.character(exec_roots$work_root %||% ""))) {
    return(list())
  }
  modules <- as.list(utils::head(as.character(unlist(state$modules %||% character(0), use.names = FALSE)), n = max_items))
  failed_modules <- Filter(function(item) {
    as.character(item$status %||% "") %in% c("FAILED", "ERROR")
  }, execute_summary$modules %||% list())
  compact_workflow_dialogue_context(list(
    cm_spec_results_root = as.character(exec_roots$results_root %||% NULL),
    cm_spec_work_root = as.character(exec_roots$work_root %||% NULL),
    cm_spec_modules = modules,
    cm_spec_overall_status = execute_summary$overall_status %||% NULL,
    cm_spec_failed_modules = as.list(utils::head(vapply(failed_modules, function(item) as.character(item$module_name %||% ""), character(1)), n = max_items)),
    cm_spec_ps_adjustment_strategy = state$ps_adjustment_strategy %||% NULL,
    cm_spec_ps_trimming_strategy = state$ps_trimming_strategy %||% NULL,
    cm_spec_analysis_specification_path = state$analysis_specification_path %||% NULL,
    cm_spec_execute_summary_path = file.path(base_dir, "analysis-settings", "strategus_execute_summary.json"),
    cm_spec_execute_summary_exists = file.exists(file.path(base_dir, "analysis-settings", "strategus_execute_summary.json")),
    cm_spec_execute_result_path = file.path(base_dir, "analysis-settings", "strategus_execute_result.rds"),
    cm_spec_execute_result_exists = file.exists(file.path(base_dir, "analysis-settings", "strategus_execute_result.rds"))
  ))
}

.studyAgentSlashResolveArtifactPath <- function(path, base_dir) {
  path <- as.character(path %||% "")
  if (!nzchar(trimws(path))) {
    return(.studyAgentSlashResolveProjectPath(path, base_dir))
  }
  if (grepl("^(?:[A-Za-z]:[/\\]|/|~)", path)) {
    return(normalizePath(path, winslash = "/", mustWork = FALSE))
  }

  candidates <- unique(c(
    .studyAgentSlashResolveProjectPath(path, base_dir),
    normalizePath(file.path(dirname(base_dir), path), winslash = "/", mustWork = FALSE),
    normalizePath(file.path(dirname(dirname(base_dir)), path), winslash = "/", mustWork = FALSE),
    normalizePath(file.path(getwd(), path), winslash = "/", mustWork = FALSE)
  ))
  existing <- Filter(function(candidate) {
    file.exists(candidate) || dir.exists(candidate)
  }, candidates)
  if (length(existing) > 0) {
    return(existing[[1]])
  }
  candidates[[1]]
}

.studyAgentSlashNewExplorationArtifact <- function(id,
                                                   artifact_class,
                                                   path,
                                                   base_dir,
                                                   type = NULL,
                                                   step_id = NULL,
                                                   status = NULL,
                                                   explorable = TRUE,
                                                   preview_kind = "table",
                                                   tags = character(0),
                                                   metadata = list()) {
  absolute_path <- .studyAgentSlashResolveProjectPath(path, base_dir)
  list(
    id = as.character(id),
    artifact_class = as.character(artifact_class),
    path = .studyAgentSlashRelativizeProjectPath(absolute_path, base_dir),
    absolute_path = absolute_path,
    exists = isTRUE(file.exists(absolute_path)),
    type = if (is.null(type)) NULL else as.character(type),
    step_id = if (is.null(step_id)) NULL else as.character(step_id),
    status = if (is.null(status)) NULL else as.character(status),
    explorable = isTRUE(explorable),
    preview_kind = as.character(preview_kind %||% "table"),
    tags = as.list(as.character(tags %||% character(0))),
    metadata = metadata %||% list()
  )
}

.studyAgentSlashArtifactClassFromPath <- function(path, artifact_id = "") {
  path <- as.character(path %||% "")
  artifact_id <- as.character(artifact_id %||% "")
  base_name <- basename(path)
  if (identical(base_name, "Cohorts.csv")) return("cohort_definition_set_csv")
  if (identical(base_name, "strategus-db-details.json")) return("db_details_json")
  if (identical(base_name, "strategus-execution-settings.json")) return("execution_settings_json")
  if (identical(base_name, "analysisSpecification.json")) return("analysis_specification_json")
  if (identical(base_name, "strategus_execute_result.rds")) return("strategus_execute_result_rds")
  if (identical(base_name, "cm_analysis_state.json")) return("cm_analysis_state_json")
  if (identical(base_name, "cmAnalysis.json")) return("analysis_settings_json")
  if (identical(base_name, "cg_cohort_definition.csv")) return("cohort_definition_csv")
  if (identical(base_name, "cg_cohort_count.csv")) return("cohort_counts_csv")
  if (identical(base_name, "cg_cohort_inclusion.csv")) return("cohort_inclusion_csv")
  if (identical(base_name, "cg_cohort_inc_result.csv")) return("cohort_inclusion_result_csv")
  if (identical(base_name, "cg_cohort_inc_stats.csv")) return("cohort_inclusion_stats_csv")
  if (identical(base_name, "cg_cohort_summary_stats.csv")) return("cohort_summary_stats_csv")
  if (identical(base_name, "ci_incidence_summary.csv")) return("incidence_summary_csv")
  if (identical(base_name, "ci_target_def.csv")) return("incidence_target_definition_csv")
  if (identical(base_name, "ci_outcome_def.csv")) return("incidence_outcome_definition_csv")
  if (identical(base_name, "ci_tar_def.csv")) return("incidence_tar_definition_csv")
  if (identical(base_name, "08_launch_diagnostics_explorer.R")) return("diagnostics_explorer_script")
  if (grepl("/keeper-case-review/", path, fixed = TRUE)) return("keeper_artifact")
  if (dir.exists(path) && identical(base_name, "analysis-settings")) return("analysis_settings_dir")
  if (dir.exists(path) && identical(base_name, "cm-diagnostics")) return("cohort_method_diagnostics_dir")
  if (dir.exists(path) && identical(base_name, "cm-results")) return("cohort_method_results_dir")
  if (grepl("/scripts/", path, fixed = TRUE) || endsWith(path, ".R")) return("script")
  if (dir.exists(path) && identical(base_name, "CohortGeneratorModule")) return("cohort_generation_module_dir")
  if (dir.exists(path) && identical(base_name, "cohort-generation-results")) return("cohort_generation_results_dir")
  if (dir.exists(path) && identical(base_name, "cohort-generation-work")) return("cohort_generation_work_dir")
  if (identical(artifact_id, "strategus_results_dir")) return("strategus_results_dir")
  if (identical(artifact_id, "strategus_work_dir")) return("strategus_work_dir")
  if (identical(artifact_id, "analysis_settings_dir")) return("analysis_settings_dir")
  if (nzchar(artifact_id) && grepl("cm_analysis", artifact_id, fixed = TRUE)) return("analysis_settings_json")
  "generic"
}

.studyAgentSlashRegisterExplorationArtifact <- function(registry,
                                                        id,
                                                        artifact_class,
                                                        path,
                                                        base_dir,
                                                        type = NULL,
                                                        step_id = NULL,
                                                        status = NULL,
                                                        explorable = TRUE,
                                                        preview_kind = "table",
                                                        tags = character(0),
                                                        metadata = list()) {
  registry[[as.character(id)]] <- .studyAgentSlashNewExplorationArtifact(
    id = id,
    artifact_class = artifact_class,
    path = path,
    base_dir = base_dir,
    type = type,
    step_id = step_id,
    status = status,
    explorable = explorable,
    preview_kind = preview_kind,
    tags = tags,
    metadata = metadata
  )
  registry
}

.studyAgentSlashMaybeRegisterKnownArtifact <- function(registry,
                                                       id,
                                                       path,
                                                       base_dir,
                                                       step_id = NULL,
                                                       tags = character(0),
                                                       explorable = TRUE,
                                                       preview_kind = "table") {
  absolute_path <- .studyAgentSlashResolveProjectPath(path, base_dir)
  registry <- .studyAgentSlashRegisterExplorationArtifact(
    registry = registry,
    id = id,
    artifact_class = .studyAgentSlashArtifactClassFromPath(absolute_path, id),
    path = absolute_path,
    base_dir = base_dir,
    step_id = step_id,
    explorable = explorable,
    preview_kind = preview_kind,
    tags = tags
  )
  registry
}

.studyAgentSlashBuildArtifactRegistry <- function(base_dir) {
  project_state <- .studyAgentSlashReadProjectState(base_dir)
  registry <- list()

  for (name in names(project_state$artifacts %||% list())) {
    artifact <- project_state$artifacts[[name]] %||% list()
    artifact_path <- as.character(artifact$path %||% "")
    if (!nzchar(artifact_path)) next
    absolute_path <- .studyAgentSlashResolveProjectPath(artifact_path, base_dir)
    registry[[name]] <- .studyAgentSlashNewExplorationArtifact(
      id = name,
      artifact_class = .studyAgentSlashArtifactClassFromPath(absolute_path, name),
      path = absolute_path,
      base_dir = base_dir,
      type = artifact$type %||% NULL,
      step_id = artifact$step_id %||% NULL,
      status = artifact$status %||% NULL,
      explorable = !identical(as.character(artifact$type %||% ""), "script"),
      preview_kind = if (dir.exists(absolute_path)) "dir" else "table",
      tags = as.character(unlist(artifact$tags %||% character(0), use.names = FALSE)),
      metadata = artifact$metadata %||% list()
    )
  }

  registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "db_details_json", file.path(base_dir, "strategus-db-details.json"), base_dir, tags = c("config", "db"), preview_kind = "json")
  registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "execution_settings_json", file.path(base_dir, "strategus-execution-settings.json"), base_dir, tags = c("config", "execution"), preview_kind = "json")
  registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "analysis_settings_dir", file.path(base_dir, "analysis-settings"), base_dir, tags = c("analysis", "settings"), preview_kind = "dir")
  registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "analysis_specification_json", file.path(base_dir, "analysis-settings", "analysisSpecification.json"), base_dir, step_id = if (identical(project_state$workflow_type %||% "", "strategus_cohort_methods")) "cm_spec" else "incidence_spec", tags = c("analysis", "strategus"), preview_kind = "json")
  registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "strategus_execute_result_rds", file.path(base_dir, "analysis-settings", "strategus_execute_result.rds"), base_dir, step_id = "cm_spec", tags = c("analysis", "strategus"), preview_kind = "rds")
  registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cm_analysis_state_json", file.path(base_dir, "outputs", "cm_analysis_state.json"), base_dir, step_id = "cm_spec", tags = c("analysis", "cohort_method"), preview_kind = "json")
  registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "selected_cohorts_csv", file.path(base_dir, "selected-cohorts", "Cohorts.csv"), base_dir, step_id = "generate_cohorts", tags = c("cohort", "selection"))
  diagnostics_dir <- project_state$study_context$cm_diagnostics_dir %||% file.path(base_dir, "cm-diagnostics")
  results_dir <- project_state$study_context$cm_results_dir %||% file.path(base_dir, "cm-results")
  registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cm_diagnostics_dir", diagnostics_dir, base_dir, step_id = "diagnostics", tags = c("diagnostics", "results"), preview_kind = "dir")
  registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cm_results_dir", results_dir, base_dir, step_id = "cm_spec", tags = c("cohort_method", "results"), preview_kind = "dir")

  exec_roots <- .studyAgentSlashDiscoverStrategusExecutionRoots(base_dir, project_state = project_state)
  results_root <- as.character(exec_roots$results_root %||% "")
  work_root <- as.character(exec_roots$work_root %||% "")
  if (nzchar(results_root) || nzchar(work_root)) {
    registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cohort_generation_results_dir", results_root, base_dir, step_id = "generate_cohorts", tags = c("results", "cohort_generation"), preview_kind = "dir")
    registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cohort_generation_work_dir", work_root, base_dir, step_id = "generate_cohorts", tags = c("work", "cohort_generation"), preview_kind = "dir")
    registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "strategus_results_dir", results_root, base_dir, step_id = if (identical(project_state$workflow_type %||% "", "strategus_cohort_methods")) "cm_spec" else "incidence_spec", tags = c("results", "strategus"), preview_kind = "dir")
    registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "strategus_work_dir", work_root, base_dir, step_id = if (identical(project_state$workflow_type %||% "", "strategus_cohort_methods")) "cm_spec" else "incidence_spec", tags = c("work", "strategus"), preview_kind = "dir")
    diagnostics_results_dir <- file.path(results_root, "CohortDiagnosticsModule")
    diagnostics_work_dir <- file.path(work_root, "CohortDiagnosticsModule")
    if (dir.exists(diagnostics_results_dir)) {
      registry <- .studyAgentSlashRegisterExplorationArtifact(
        registry = registry,
        id = "diagnostics_results_module_dir",
        artifact_class = "cohort_diagnostics_module_dir",
        path = diagnostics_results_dir,
        base_dir = base_dir,
        step_id = "diagnostics",
        explorable = TRUE,
        preview_kind = "dir",
        tags = c("diagnostics", "results")
      )
    }
    if (dir.exists(diagnostics_work_dir)) {
      registry <- .studyAgentSlashRegisterExplorationArtifact(
        registry = registry,
        id = "diagnostics_work_module_dir",
        artifact_class = "cohort_diagnostics_work_dir",
        path = diagnostics_work_dir,
        base_dir = base_dir,
        step_id = "diagnostics",
        explorable = TRUE,
        preview_kind = "dir",
        tags = c("diagnostics", "work")
      )
    }
    cg_dir <- file.path(results_root, "CohortGeneratorModule")
    registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cohort_generation_module_dir", cg_dir, base_dir, step_id = "generate_cohorts", tags = c("results", "cohort_generation"), preview_kind = "dir")
    registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cg_cohort_count_csv", file.path(cg_dir, "cg_cohort_count.csv"), base_dir, step_id = "generate_cohorts", tags = c("results", "counts"))
    registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cg_cohort_definition_csv", file.path(cg_dir, "cg_cohort_definition.csv"), base_dir, step_id = "generate_cohorts", tags = c("results", "definitions"))
    registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cg_cohort_inclusion_csv", file.path(cg_dir, "cg_cohort_inclusion.csv"), base_dir, step_id = "generate_cohorts", tags = c("results", "inclusion"))
    registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cg_cohort_inc_result_csv", file.path(cg_dir, "cg_cohort_inc_result.csv"), base_dir, step_id = "generate_cohorts", tags = c("results", "inclusion"))
    registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cg_cohort_inc_stats_csv", file.path(cg_dir, "cg_cohort_inc_stats.csv"), base_dir, step_id = "generate_cohorts", tags = c("results", "inclusion"))
    registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cg_cohort_summary_stats_csv", file.path(cg_dir, "cg_cohort_summary_stats.csv"), base_dir, step_id = "generate_cohorts", tags = c("results", "summary"))
    incidence_step_id <- if (identical(project_state$workflow_type %||% "", "strategus_cohort_methods")) "cm_spec" else "incidence_spec"
    ci_dir <- file.path(results_root, "CohortIncidenceModule")
    registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cohort_incidence_module_dir", ci_dir, base_dir, step_id = incidence_step_id, tags = c("results", "incidence"), preview_kind = "dir")
    registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "ci_incidence_summary_csv", file.path(ci_dir, "ci_incidence_summary.csv"), base_dir, step_id = incidence_step_id, tags = c("results", "incidence", "summary"))
    registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "ci_target_def_csv", file.path(ci_dir, "ci_target_def.csv"), base_dir, step_id = incidence_step_id, tags = c("results", "incidence", "definitions"))
    registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "ci_outcome_def_csv", file.path(ci_dir, "ci_outcome_def.csv"), base_dir, step_id = incidence_step_id, tags = c("results", "incidence", "definitions"))
    registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "ci_tar_def_csv", file.path(ci_dir, "ci_tar_def.csv"), base_dir, step_id = incidence_step_id, tags = c("results", "incidence", "definitions"))
  }

  registry
}

.studyAgentSlashArtifactRegistryForStep <- function(base_dir, step_id = NULL) {
  registry <- .studyAgentSlashBuildArtifactRegistry(base_dir)
  if (is.null(step_id) || !nzchar(trimws(as.character(step_id)))) return(registry)
  Filter(function(item) {
    item_step <- as.character(item$step_id %||% "")
    !nzchar(item_step) || identical(item_step, as.character(step_id))
  }, registry)
}

.studyAgentSlashPrepareViewerTable <- function(data, preferred_order = NULL) {
  if (is.null(data)) return(NULL)
  if (!is.data.frame(data)) data <- as.data.frame(data, stringsAsFactors = FALSE)
  if (!is.null(preferred_order)) {
    preferred_order <- intersect(as.character(preferred_order), names(data))
    remaining <- setdiff(names(data), preferred_order)
    data <- data[, c(preferred_order, remaining), drop = FALSE]
  }
  rownames(data) <- NULL
  data
}

.studyAgentSlashArtifactRegistryTable <- function(registry, viewer = FALSE) {
  rows <- lapply(registry, function(item) {
    absolute_path <- as.character(item$absolute_path %||% item$path %||% "")
    relative_path <- as.character(item$path %||% absolute_path)
    data.frame(
      artifact_id = as.character(item$id %||% ""),
      artifact_class = as.character(item$artifact_class %||% ""),
      exists = isTRUE(item$exists),
      step_id = as.character(item$step_id %||% ""),
      relative_path = relative_path,
      path = absolute_path,
      stringsAsFactors = FALSE
    )
  })
  if (length(rows) == 0) {
    return(data.frame(artifact_id = character(0), artifact_class = character(0), exists = logical(0), step_id = character(0), relative_path = character(0), path = character(0), stringsAsFactors = FALSE))
  }
  table <- do.call(rbind, rows)
  if (isTRUE(viewer)) {
    return(.studyAgentSlashPrepareViewerTable(table, preferred_order = c("artifact_id", "artifact_class", "exists", "step_id", "relative_path", "path")))
  }
  table
}

.studyAgentSlashBuildExplorationContext <- function(base_dir, project_state, runtime_state, step = NULL) {
  registry <- .studyAgentSlashBuildArtifactRegistry(base_dir)
  step_id <- as.character(step$step_id %||% project_state$resume$current_step_id %||% "")
  list(
    base_dir = base_dir,
    project_state = project_state,
    runtime_state = runtime_state,
    workflow_type = as.character(project_state$workflow_type %||% ""),
    study_context = project_state$study_context %||% list(),
    current_step_id = step_id,
    current_step_label = as.character(step$label %||% ""),
    artifact_registry = registry,
    artifact_registry_table = .studyAgentSlashArtifactRegistryTable(registry)
  )
}

.studyAgentSlashExplorationCommands <- function() {
  list(
    list(
      command_id = "artifact_inventory",
      label = "List known artifacts",
      purpose = "Show artifact ids, classes, paths, and existence.",
      workflow_types = c("strategus_incidence", "strategus_cohort_methods"),
      step_ids = character(0),
      required_packages = character(0),
      artifact_requirements = character(0),
      input_parameters = list(),
      output_kind = "table",
      safe = TRUE,
      executor = function(context) {
        list(
          status = "ok",
          title = "Artifact inventory",
          sections = list(
            .studyAgentSlashExplorationTableSection(
              data = context$artifact_registry_table,
              title = "Artifact inventory",
              preview_data = .studyAgentSlashCompactPreviewTable(context$artifact_registry_table, max_rows = 40L, max_cols = 5L)
            )
          )
        )
      }
    ),
    list(
      command_id = "results_dir_inventory",
      label = "Inventory cohort generation result files",
      purpose = "List generated result files with relative paths and sizes.",
      workflow_types = c("strategus_incidence", "strategus_cohort_methods"),
      step_ids = c("generate_cohorts", "keeper_concept_sets", "keeper_case_review", "diagnostics", "incidence_spec", "cm_spec"),
      required_packages = character(0),
      artifact_requirements = c("cohort_generation_results_dir"),
      input_parameters = list(),
      output_kind = "table",
      safe = TRUE,
      executor = function(context) {
        root <- (context$artifact_registry$cohort_generation_results_dir %||% list())$absolute_path %||% NULL
        if (is.null(root) || !dir.exists(root)) stop("Cohort generation results directory is not available.")
        paths <- list.files(root, recursive = TRUE, full.names = TRUE, all.files = FALSE, no.. = TRUE)
        if (length(paths) == 0) {
          table <- data.frame(relative_path = character(0), size_bytes = numeric(0), modified_at = character(0), stringsAsFactors = FALSE)
        } else {
          info <- file.info(paths)
          prefix <- paste0(normalizePath(root, winslash = "/", mustWork = FALSE), "/")
          rel <- sub(paste0("^", gsub("([.|()\\^{}+$*?]|\\[|\\])", "\\\\\\1", prefix)), "", normalizePath(paths, winslash = "/", mustWork = FALSE))
          table <- data.frame(
            relative_path = rel,
            size_bytes = as.numeric(info$size),
            modified_at = as.character(info$mtime),
            stringsAsFactors = FALSE
          )
        }
        list(
          status = "ok",
          title = "Cohort generation results inventory",
          sections = list(
            .studyAgentSlashExplorationTableSection(
              data = table,
              title = "Cohort generation results inventory",
              preview_data = .studyAgentSlashCompactPreviewTable(table, max_rows = 40L, max_cols = 3L)
            )
          )
        )
      }
    ),
    list(
      command_id = "cohort_definition_preview",
      label = "Preview selected cohort definitions",
      purpose = "Show selected cohort ids, names, and roles.",
      workflow_types = c("strategus_incidence", "strategus_cohort_methods"),
      step_ids = c("generate_cohorts", "keeper_concept_sets", "keeper_case_review", "diagnostics", "incidence_spec", "cm_spec"),
      required_packages = character(0),
      artifact_requirements = c("cohort_definition_set_csv"),
      input_parameters = list(),
      output_kind = "table",
      safe = TRUE,
      executor = function(context) {
        path <- (context$artifact_registry$selected_cohorts_csv %||% list())$absolute_path %||% NULL
        data <- .studyAgentSlashReadCsvSafe(path)
        if (is.null(data)) stop("Selected cohort definition file is not available.")
        keep <- intersect(c("atlas_id", "cohort_id", "cohort_name", "cohort_type", "logic_description", "generate_stats"), names(data))
        selected <- data[, keep, drop = FALSE]
        list(
          status = "ok",
          title = "Selected cohort definitions",
          sections = list(
            .studyAgentSlashExplorationTableSection(
              data = selected,
              title = "Selected cohort definitions",
              preview_data = .studyAgentSlashCompactPreviewTable(selected, max_rows = 20L, max_cols = 6L)
            )
          )
        )
      }
    ),
    list(
      command_id = "cohort_counts_summary",
      label = "Summarize generated cohort counts",
      purpose = "Show cohort entries and subjects for generated cohorts.",
      workflow_types = c("strategus_incidence", "strategus_cohort_methods"),
      step_ids = c("generate_cohorts", "keeper_concept_sets", "keeper_case_review", "diagnostics", "incidence_spec", "cm_spec"),
      required_packages = c("CohortGenerator"),
      artifact_requirements = c("cohort_counts_csv"),
      input_parameters = list(),
      output_kind = "table",
      safe = TRUE,
      executor = function(context) {
        counts_path <- (context$artifact_registry$cg_cohort_count_csv %||% list())$absolute_path %||% NULL
        selected_path <- (context$artifact_registry$selected_cohorts_csv %||% list())$absolute_path %||% NULL
        counts <- .studyAgentSlashReadCsvSafe(counts_path)
        if (is.null(counts)) stop("Cohort counts file is not available.")
        selected <- .studyAgentSlashReadCsvSafe(selected_path)
        if (!is.null(selected) && all(c("cohort_id", "cohort_name") %in% names(selected))) {
          counts <- merge(counts, unique(selected[, c("cohort_id", "cohort_name"), drop = FALSE]), by = "cohort_id", all.x = TRUE, sort = FALSE)
        }
        keep <- intersect(c("cohort_id", "cohort_name", "cohort_entries", "cohort_subjects", "database_id"), names(counts))
        if ("cohort_entries" %in% names(counts)) counts <- counts[order(-counts$cohort_entries, counts$cohort_id), , drop = FALSE]
        selected <- counts[, keep, drop = FALSE]
        list(
          status = "ok",
          title = "Generated cohort counts",
          sections = list(
            .studyAgentSlashExplorationTableSection(
              data = selected,
              title = "Generated cohort counts",
              preview_data = .studyAgentSlashCompactPreviewTable(selected, max_rows = 20L, max_cols = 5L)
            )
          )
        )
      }
    ),
    list(
      command_id = "inclusion_rules_preview",
      label = "Preview inclusion rule attrition",
      purpose = "Show inclusion rules and attrition counts for generated cohorts.",
      workflow_types = c("strategus_incidence", "strategus_cohort_methods"),
      step_ids = c("generate_cohorts", "keeper_concept_sets", "keeper_case_review", "diagnostics", "incidence_spec", "cm_spec"),
      required_packages = c("CohortGenerator"),
      artifact_requirements = c("cohort_inclusion_csv", "cohort_inclusion_stats_csv"),
      input_parameters = list(),
      output_kind = "table",
      safe = TRUE,
      executor = function(context) {
        inclusion <- .studyAgentSlashReadCsvSafe((context$artifact_registry$cg_cohort_inclusion_csv %||% list())$absolute_path %||% NULL)
        stats <- .studyAgentSlashReadCsvSafe((context$artifact_registry$cg_cohort_inc_stats_csv %||% list())$absolute_path %||% NULL)
        selected <- .studyAgentSlashReadCsvSafe((context$artifact_registry$selected_cohorts_csv %||% list())$absolute_path %||% NULL)
        if (is.null(inclusion) || is.null(stats)) stop("Inclusion rule artifacts are not available.")
        if ("mode_id" %in% names(stats)) stats <- subset(stats, mode_id == 0)
        merged <- merge(stats, inclusion, by = c("cohort_definition_id", "rule_sequence"), all.x = TRUE, sort = FALSE)
        if (!is.null(selected) && all(c("cohort_id", "cohort_name") %in% names(selected))) {
          merged <- merge(merged, unique(selected[, c("cohort_id", "cohort_name"), drop = FALSE]), by.x = "cohort_definition_id", by.y = "cohort_id", all.x = TRUE, sort = FALSE)
        }
        keep <- intersect(c("cohort_definition_id", "cohort_name", "rule_sequence", "name", "person_count", "gain_count", "person_total"), names(merged))
        selected <- merged[, keep, drop = FALSE]
        list(
          status = "ok",
          title = "Inclusion rule attrition",
          sections = list(
            .studyAgentSlashExplorationTableSection(
              data = selected,
              title = "Inclusion rule attrition",
              preview_data = .studyAgentSlashCompactPreviewTable(selected, max_rows = 20L, max_cols = 7L)
            )
          )
        )
      }
    ),
    list(
      command_id = "cohort_stats_preview",
      label = "Preview cohort generation statistics files",
      purpose = "Show available cohort-generation statistic files and a compact row sample from each.",
      workflow_types = c("strategus_incidence", "strategus_cohort_methods"),
      step_ids = c("generate_cohorts", "keeper_concept_sets", "keeper_case_review", "diagnostics", "incidence_spec", "cm_spec"),
      required_packages = character(0),
      artifact_requirements = c("cohort_generation_module_dir"),
      input_parameters = list(),
      output_kind = "mixed",
      safe = TRUE,
      executor = function(context) {
        keys <- c("cg_cohort_count_csv", "cg_cohort_inclusion_csv", "cg_cohort_inc_result_csv", "cg_cohort_inc_stats_csv", "cg_cohort_summary_stats_csv")
        labels <- c("counts", "inclusion rules", "inclusion result", "inclusion stats", "summary stats")
        sections <- list()
        for (i in seq_along(keys)) {
          item <- context$artifact_registry[[keys[[i]]]] %||% NULL
          if (is.null(item) || !isTRUE(item$exists)) next
          data <- .studyAgentSlashReadCsvSafe(item$absolute_path)
          if (is.null(data)) next
          sections[[length(sections) + 1L]] <- list(kind = "text", text = sprintf("%s: %s", labels[[i]], item$path))
          sections[[length(sections) + 1L]] <- .studyAgentSlashExplorationTableSection(
            data = data,
            title = basename(item$path %||% item$absolute_path %||% labels[[i]]),
            preview_data = .studyAgentSlashCompactPreviewTable(data, max_rows = 6L, max_cols = 6L)
          )
        }
        if (length(sections) == 0) stop("No cohort generation statistics files are available.")
        list(status = "ok", title = "Cohort generation statistics preview", sections = sections)
      }
    ),
    list(
      command_id = "incidence_summary_preview",
      label = "Preview incidence summary results",
      purpose = "Summarize CohortIncidence output with target, outcome, TAR, strata, and incidence measures.",
      workflow_types = c("strategus_incidence", "strategus_cohort_methods"),
      step_ids = c("generate_cohorts", "keeper_concept_sets", "keeper_case_review", "diagnostics", "incidence_spec", "cm_spec"),
      required_packages = character(0),
      artifact_requirements = c("incidence_summary_csv"),
      input_parameters = list(),
      output_kind = "table",
      safe = TRUE,
      executor = function(context) {
        summary <- .studyAgentSlashSummarizeIncidenceResults(context$base_dir, project_state = context$project_state)
        if (is.null(summary) || !is.data.frame(summary) || nrow(summary) == 0) {
          stop("CohortIncidence summary output is not available yet.")
        }
        list(
          status = "ok",
          title = "Incidence summary preview",
          sections = list(
            .studyAgentSlashExplorationTableSection(
              data = summary,
              title = "Incidence summary preview",
              preview_data = .studyAgentSlashCompactPreviewTable(summary, max_rows = 20L, max_cols = 8L)
            )
          )
        )
      }
    ),
    list(
      command_id = "incidence_analysis_settings_summary",
      label = "Summarize incidence analysis settings",
      purpose = "Show selected targets/outcomes, TAR definitions, strata settings, and analysis/result roots for the incidence run.",
      workflow_types = c("strategus_incidence", "strategus_cohort_methods"),
      step_ids = c("generate_cohorts", "keeper_concept_sets", "keeper_case_review", "diagnostics", "incidence_spec", "cm_spec"),
      required_packages = character(0),
      artifact_requirements = c("analysis_specification_json"),
      input_parameters = list(),
      output_kind = "mixed",
      safe = TRUE,
      executor = function(context) {
        tables <- .studyAgentSlashIncidenceAnalysisSettingsTables(context$base_dir, project_state = context$project_state)
        sections <- list(
          .studyAgentSlashExplorationTableSection(
            data = tables$overview,
            title = "Incidence analysis settings overview",
            preview_data = .studyAgentSlashCompactPreviewTable(tables$overview, max_rows = 20L, max_cols = 2L)
          )
        )
        if (!is.null(tables$tar_table) && is.data.frame(tables$tar_table) && nrow(tables$tar_table) > 0) {
          sections[[length(sections) + 1L]] <- .studyAgentSlashExplorationTableSection(
            data = tables$tar_table,
            title = "Time-at-risk definitions",
            preview_data = .studyAgentSlashCompactPreviewTable(tables$tar_table, max_rows = 12L, max_cols = 7L)
          )
        }
        list(
          status = "ok",
          title = "Incidence analysis settings summary",
          sections = sections
        )
      }
    ),
    list(
      command_id = "diagnostics_inventory",
      label = "Inventory diagnostics artifacts",
      purpose = "List discovered diagnostics result files, inferred classes, sizes, and modified times.",
      workflow_types = c("strategus_incidence", "strategus_cohort_methods"),
      step_ids = c("diagnostics", "incidence_spec", "cm_spec"),
      required_packages = character(0),
      artifact_requirements = character(0),
      input_parameters = list(),
      output_kind = "table",
      safe = TRUE,
      executor = function(context) {
        inventory <- .studyAgentSlashDiagnosticsInventoryTable(context$base_dir, project_state = context$project_state)
        if (nrow(inventory) == 0) stop("No diagnostics artifacts were discovered yet.")
        display <- inventory[, intersect(c("root", "relative_path", "artifact_class", "size_bytes", "modified_at"), names(inventory)), drop = FALSE]
        list(
          status = "ok",
          title = "Diagnostics artifact inventory",
          sections = list(
            .studyAgentSlashExplorationTableSection(
              data = display,
              title = "Diagnostics artifact inventory",
              preview_data = .studyAgentSlashCompactPreviewTable(display, max_rows = 30L, max_cols = 5L)
            )
          )
        )
      }
    ),
    list(
      command_id = "diagnostics_run_settings",
      label = "Show diagnostics run settings",
      purpose = "Show configured diagnostics output roots and enabled CohortDiagnostics module options from the generated shell script.",
      workflow_types = c("strategus_incidence", "strategus_cohort_methods"),
      step_ids = c("diagnostics", "incidence_spec", "cm_spec"),
      required_packages = character(0),
      artifact_requirements = character(0),
      input_parameters = list(),
      output_kind = "table",
      safe = TRUE,
      executor = function(context) {
        exec_path <- file.path(context$base_dir, "strategus-execution-settings.json")
        exec_cfg <- if (file.exists(exec_path)) tryCatch(readStrategusExecutionSettings(exec_path), error = function(e) NULL) else NULL
        roots <- .studyAgentSlashDiscoverDiagnosticsRoots(context$base_dir, project_state = context$project_state)
        roots_display <- if (length(roots) > 0) {
          paste(vapply(roots, function(root) .studyAgentSlashRelativizeProjectPath(root, context$base_dir), character(1)), collapse = "; ")
        } else {
          ""
        }
        data <- data.frame(
          setting = c(
            "diagnostics_roots",
            "execution_resultsFolder",
            "execution_workFolder",
            "runInclusionStatistics",
            "runIncludedSourceConcepts",
            "runOrphanConcepts",
            "runTimeSeries",
            "runVisitContext",
            "runBreakdownIndexEvents",
            "runIncidenceRate",
            "runCohortRelationship",
            "runTemporalCohortCharacterization"
          ),
          value = c(
            roots_display,
            as.character(exec_cfg$resultsFolder %||% ""),
            as.character(exec_cfg$workFolder %||% ""),
            "TRUE",
            "TRUE",
            "TRUE",
            "FALSE",
            "TRUE",
            "TRUE",
            "TRUE",
            "TRUE",
            "TRUE"
          ),
          stringsAsFactors = FALSE
        )
        list(
          status = "ok",
          title = "Diagnostics run settings",
          sections = list(
            .studyAgentSlashExplorationTableSection(
              data = data,
              title = "Diagnostics run settings",
              preview_data = data
            )
          )
        )
      }
    ),
    list(
      command_id = "diagnostics_orphan_concepts_summary",
      label = "Preview orphan concept diagnostics",
      purpose = "Preview discovered orphan concept diagnostics artifacts and compact row samples.",
      workflow_types = c("strategus_incidence", "strategus_cohort_methods"),
      step_ids = c("diagnostics", "incidence_spec", "cm_spec"),
      required_packages = character(0),
      artifact_requirements = character(0),
      input_parameters = list(),
      output_kind = "mixed",
      safe = TRUE,
      executor = function(context) {
        summary_data <- .studyAgentSlashSummarizeDiagnosticsOrphanConcepts(context$base_dir, project_state = context$project_state)
        if (is.null(summary_data) || nrow(summary_data) == 0) stop("No orphan concept diagnostics artifacts were discovered.")
        list(
          status = "ok",
          title = "Orphan concept diagnostics",
          sections = list(
            .studyAgentSlashExplorationTableSection(
              data = summary_data,
              title = "Orphan concept diagnostics",
              preview_data = .studyAgentSlashCompactPreviewTable(summary_data, max_rows = 25L, max_cols = 9L)
            )
          )
        )
      }
    ),
    list(
      command_id = "diagnostics_source_concepts_summary",
      label = "Preview included source concept diagnostics",
      purpose = "Preview discovered included source concept artifacts and compact row samples.",
      workflow_types = c("strategus_incidence", "strategus_cohort_methods"),
      step_ids = c("diagnostics", "incidence_spec", "cm_spec"),
      required_packages = character(0),
      artifact_requirements = character(0),
      input_parameters = list(),
      output_kind = "mixed",
      safe = TRUE,
      executor = function(context) {
        summary_data <- .studyAgentSlashSummarizeDiagnosticsSourceConcepts(context$base_dir, project_state = context$project_state)
        if (is.null(summary_data) || nrow(summary_data) == 0) stop("No included source concept diagnostics artifacts were discovered.")
        list(
          status = "ok",
          title = "Included source concept diagnostics",
          sections = list(
            .studyAgentSlashExplorationTableSection(
              data = summary_data,
              title = "Included source concept diagnostics",
              preview_data = .studyAgentSlashCompactPreviewTable(summary_data, max_rows = 25L, max_cols = 11L)
            )
          )
        )
      }
    ),
    list(
      command_id = "diagnostics_visit_context_summary",
      label = "Preview visit context diagnostics",
      purpose = "Preview discovered visit context artifacts and compact row samples.",
      workflow_types = c("strategus_incidence", "strategus_cohort_methods"),
      step_ids = c("diagnostics", "incidence_spec", "cm_spec"),
      required_packages = character(0),
      artifact_requirements = character(0),
      input_parameters = list(),
      output_kind = "mixed",
      safe = TRUE,
      executor = function(context) {
        summary_data <- .studyAgentSlashSummarizeDiagnosticsVisitContext(context$base_dir, project_state = context$project_state)
        if (is.null(summary_data) || nrow(summary_data) == 0) stop("No visit context diagnostics artifacts were discovered.")
        list(
          status = "ok",
          title = "Visit context diagnostics",
          sections = list(
            .studyAgentSlashExplorationTableSection(
              data = summary_data,
              title = "Visit context diagnostics",
              preview_data = .studyAgentSlashCompactPreviewTable(summary_data, max_rows = 25L, max_cols = 7L)
            )
          )
        )
      }
    ),

    list(
      command_id = "cm_spec_artifact_inventory",
      label = "Inventory cohort method specification artifacts",
      purpose = "List analysis-settings and Strategus result/work artifacts for the cohort method specification step using full resolved paths.",
      workflow_types = c("strategus_cohort_methods"),
      step_ids = c("cm_spec"),
      required_packages = character(0),
      artifact_requirements = character(0),
      input_parameters = list(),
      output_kind = "table",
      safe = TRUE,
      executor = function(context) {
        inventory <- .studyAgentSlashCmSpecInventoryTable(context$base_dir, project_state = context$project_state)
        if (nrow(inventory) == 0) stop("No cohort method specification artifacts were discovered yet.")
        display <- inventory[, intersect(c("root_path", "relative_path", "artifact_class", "size_bytes", "modified_at", "absolute_path"), names(inventory)), drop = FALSE]
        list(
          status = "ok",
          title = "Cohort method specification artifact inventory",
          sections = list(
            .studyAgentSlashExplorationTableSection(
              data = display,
              title = "Cohort method specification artifact inventory",
              preview_data = .studyAgentSlashCompactPreviewTable(display, max_rows = 30L, max_cols = 6L)
            )
          )
        )
      }
    ),
    list(
      command_id = "cm_spec_run_settings",
      label = "Show cohort method specification run settings",
      purpose = "Show resolved Strategus roots and the key comparative-effect settings chosen for the cohort method specification run.",
      workflow_types = c("strategus_cohort_methods"),
      step_ids = c("cm_spec"),
      required_packages = character(0),
      artifact_requirements = character(0),
      input_parameters = list(),
      output_kind = "table",
      safe = TRUE,
      executor = function(context) {
        state <- .studyAgentSlashCmSpecAnalysisState(context$base_dir)
        if (is.null(state)) stop("cm_analysis_state.json is not available yet.")
        exec_roots <- .studyAgentSlashDiscoverStrategusExecutionRoots(context$base_dir, project_state = context$project_state)
        data <- data.frame(
          setting = c(
            "comparison_label",
            "target_id",
            "comparator_id",
            "outcome_ids",
            "modules",
            "ps_adjustment_strategy",
            "ps_trimming_strategy",
            "analytic_settings_profile_name",
            "analysis_specification_path",
            "cm_analysis_json_path",
            "concept_set_selections_path",
            "strategus_results_root",
            "strategus_work_root",
            "strategus_execute_result_path"
          ),
          value = c(
            .studyAgentSlashCollapseValue(state$comparison_label %||% ""),
            .studyAgentSlashCollapseValue(state$target_id %||% ""),
            .studyAgentSlashCollapseValue(state$comparator_id %||% ""),
            .studyAgentSlashCollapseValue(unlist(state$outcome_ids %||% list(), use.names = FALSE)),
            .studyAgentSlashCollapseValue(unlist(state$modules %||% list(), use.names = FALSE)),
            .studyAgentSlashCollapseValue(state$ps_adjustment_strategy %||% ""),
            .studyAgentSlashCollapseValue(state$ps_trimming_strategy %||% ""),
            .studyAgentSlashCollapseValue(state$analytic_settings_profile_name %||% ""),
            .studyAgentSlashCollapseValue(state$analysis_specification_path %||% ""),
            .studyAgentSlashCollapseValue(state$cm_analysis_json_path %||% ""),
            .studyAgentSlashCollapseValue(state$concept_set_selections_path %||% ""),
            .studyAgentSlashCollapseValue(exec_roots$results_root %||% ""),
            .studyAgentSlashCollapseValue(exec_roots$work_root %||% ""),
            file.path(context$base_dir, "analysis-settings", "strategus_execute_result.rds")
          ),
          stringsAsFactors = FALSE
        )
        list(
          status = "ok",
          title = "Cohort method specification run settings",
          sections = list(
            .studyAgentSlashExplorationTableSection(
              data = data,
              title = "Cohort method specification run settings",
              preview_data = data
            )
          )
        )
      }
    ),
    list(
      command_id = "cm_spec_analysis_spec",
      label = "Summarize saved Strategus analysis specification",
      purpose = "Summarize the saved analysisSpecification.json and preview its top-level structure and module content.",
      workflow_types = c("strategus_cohort_methods"),
      step_ids = c("cm_spec"),
      required_packages = character(0),
      artifact_requirements = character(0),
      input_parameters = list(),
      output_kind = "mixed",
      safe = TRUE,
      executor = function(context) {
        spec_path <- file.path(context$base_dir, "analysis-settings", "analysisSpecification.json")
        spec <- .studyAgentSlashReadJsonSafe(spec_path, simplifyVector = FALSE)
        if (is.null(spec)) stop("analysisSpecification.json is not available yet.")
        state <- .studyAgentSlashCmSpecAnalysisState(context$base_dir)
        info <- file.info(spec_path)
        summary <- data.frame(
          property = c("analysis_specification_path", "size_bytes", "modified_at", "top_level_keys", "module_names", "shared_resource_count", "module_specification_count"),
          value = c(
            spec_path,
            as.character(as.numeric(info$size)),
            as.character(info$mtime),
            paste(names(spec) %||% character(0), collapse = "; "),
            .studyAgentSlashCollapseValue(unlist(state$modules %||% list(), use.names = FALSE)),
            as.character(length(spec$sharedResources %||% list())),
            as.character(length(spec$moduleSpecifications %||% list()))
          ),
          stringsAsFactors = FALSE
        )
        sections <- list(
          .studyAgentSlashExplorationTableSection(
            data = summary,
            title = "Strategus analysis specification summary",
            preview_data = summary
          )
        )
        element_table <- .studyAgentSlashObjectElementTable(spec, max_items = 20L)
        if (!is.null(element_table) && nrow(element_table) > 0) {
          sections[[length(sections) + 1L]] <- .studyAgentSlashExplorationTableSection(
            data = element_table,
            title = "Strategus analysis specification elements",
            preview_data = .studyAgentSlashCompactPreviewTable(element_table, max_rows = 20L, max_cols = 6L)
          )
        }
        list(status = "ok", title = "Strategus analysis specification", sections = sections)
      }
    ),
    list(
      command_id = "cm_spec_execute_result",
      label = "Summarize saved Strategus execute result",
      purpose = "Summarize module outcomes, failures, and key analysis context from the saved Strategus execute result.",
      workflow_types = c("strategus_cohort_methods"),
      step_ids = c("cm_spec"),
      required_packages = character(0),
      artifact_requirements = character(0),
      input_parameters = list(),
      output_kind = "mixed",
      safe = TRUE,
      executor = function(context) {
        result_path <- file.path(context$base_dir, "analysis-settings", "strategus_execute_result.rds")
        result <- .studyAgentSlashReadRdsSafe(result_path)
        summary_path <- file.path(context$base_dir, "analysis-settings", "strategus_execute_summary.json")
        execute_summary <- .studyAgentSlashReadJsonSafe(summary_path, simplifyVector = FALSE)
        if (is.null(result) && is.null(execute_summary)) stop("strategus_execute_result.rds is not available yet.")
        info <- file.info(result_path)
        state <- .studyAgentSlashCmSpecAnalysisState(context$base_dir)
        exec_roots <- .studyAgentSlashDiscoverStrategusExecutionRoots(context$base_dir, project_state = context$project_state)
        module_rows <- if (!is.null(execute_summary$modules) && length(execute_summary$modules) > 0) {
          do.call(rbind, lapply(execute_summary$modules, function(item) {
            data.frame(
              module_name = as.character(item$module_name %||% item$moduleName %||% ""),
              status = as.character(item$status %||% ""),
              execution_time = as.character(item$execution_time %||% item$executionTime %||% ""),
              error_message = as.character(item$error_message %||% item$errorMessage %||% ""),
              stringsAsFactors = FALSE
            )
          }))
        } else if (is.list(result) && length(result) > 0) {
          do.call(rbind, lapply(result, function(item) {
            data.frame(
              module_name = as.character(item$moduleName %||% ""),
              status = as.character(item$status %||% ""),
              execution_time = as.character(item$executionTime %||% ""),
              error_message = as.character(item$errorMessage %||% ""),
              stringsAsFactors = FALSE
            )
          }))
        } else {
          data.frame(module_name = character(0), status = character(0), execution_time = character(0), error_message = character(0), stringsAsFactors = FALSE)
        }
        failed_rows <- if (nrow(module_rows) > 0) module_rows[module_rows$status %in% c("FAILED", "ERROR"), , drop = FALSE] else module_rows
        overall_status <- if (!is.null(execute_summary$overall_status) && nzchar(as.character(execute_summary$overall_status))) {
          as.character(execute_summary$overall_status)
        } else if (nrow(module_rows) == 0) {
          "unknown"
        } else if (nrow(failed_rows) > 0) {
          "partial_failure"
        } else if (all(module_rows$status %in% c("SUCCESS", "COMPLETED"))) {
          "success"
        } else {
          "mixed"
        }
        summary <- data.frame(
          property = c(
            "overall_status",
            "module_count",
            "successful_module_count",
            "failed_module_count",
            "failed_modules",
            "comparison_label",
            "target_id",
            "comparator_id",
            "outcome_ids",
            "ps_adjustment_strategy",
            "ps_trimming_strategy",
            "results_root",
            "work_root",
            "summary_path",
            "result_path",
            "size_bytes",
            "modified_at"
          ),
          value = c(
            overall_status,
            nrow(module_rows),
            sum(module_rows$status %in% c("SUCCESS", "COMPLETED"), na.rm = TRUE),
            nrow(failed_rows),
            if (nrow(failed_rows) > 0) paste(failed_rows$module_name, collapse = "; ") else "",
            .studyAgentSlashCollapseValue(state$comparison_label %||% ""),
            .studyAgentSlashCollapseValue(state$target_id %||% ""),
            .studyAgentSlashCollapseValue(state$comparator_id %||% ""),
            .studyAgentSlashCollapseValue(unlist(state$outcome_ids %||% list(), use.names = FALSE)),
            .studyAgentSlashCollapseValue(state$ps_adjustment_strategy %||% ""),
            .studyAgentSlashCollapseValue(state$ps_trimming_strategy %||% ""),
            .studyAgentSlashCollapseValue(exec_roots$results_root %||% ""),
            .studyAgentSlashCollapseValue(exec_roots$work_root %||% ""),
            summary_path,
            result_path,
            as.character(as.numeric(info$size)),
            as.character(info$mtime)
          ),
          stringsAsFactors = FALSE
        )
        sections <- list(
          .studyAgentSlashExplorationTableSection(
            data = summary,
            title = "Strategus execute result summary",
            preview_data = summary
          )
        )
        if (nrow(module_rows) > 0) {
          sections[[length(sections) + 1L]] <- .studyAgentSlashExplorationTableSection(
            data = module_rows,
            title = "Module execution outcomes",
            preview_data = module_rows
          )
        }
        if (nrow(failed_rows) > 0) {
          sections[[length(sections) + 1L]] <- list(
            kind = "text",
            text = paste(
              "One or more Strategus modules failed. Use x cm_spec_cohort_method_summary for CohortMethod-specific partial outputs.",
              "If your HADES environment provides a CohortMethod results Shiny app, launch it from a separate R script against the Strategus results/work roots above for deeper interactive review."
            )
          )
        }
        list(status = "ok", title = "Strategus execute result", sections = sections)
      }
    ),
    list(
      command_id = "keeper_case_review_metrics",
      label = "Summarize Keeper review precision and recall limits",
      purpose = "Compute reviewed-sample precision/PPV from Keeper labels and explain why true recall is not identifiable from this sample alone.",
      workflow_types = c("strategus_incidence", "strategus_cohort_methods"),
      step_ids = c("keeper_case_review", "diagnostics", "incidence_spec", "cm_spec"),
      required_packages = character(0),
      artifact_requirements = character(0),
      input_parameters = list(),
      output_kind = "mixed",
      safe = TRUE,
      executor = function(context) {
        paths <- .studyAgentSlashDiscoverKeeperReviewCsvPaths(context$base_dir)
        if (length(paths) <= 0) stop("No Keeper review CSV artifacts are available yet.")
        rows <- lapply(paths, function(path) {
          data <- .studyAgentSlashReadCsvSafe(path)
          if (is.null(data) || nrow(data) <= 0) return(NULL)
          metrics <- .studyAgentSlashSummarizeKeeperReviewMetrics(data)
          if (is.null(metrics)) return(NULL)
          metrics$review_file <- basename(path)
          metrics$role <- as.character(data$role[[1]] %||% "")
          metrics$cohort_definition_id <- as.character(data$cohort_definition_id[[1]] %||% "")
          metrics$phenotype_name <- as.character(data$phenotype_name[[1]] %||% "")
          metrics
        })
        rows <- Filter(Negate(is.null), rows)
        if (length(rows) <= 0) stop("Keeper review artifacts were found, but none contained reviewed rows.")
        per_file <- do.call(rbind, rows)
        total_yes <- sum(per_file$yes_count, na.rm = TRUE)
        total_no <- sum(per_file$no_count, na.rm = TRUE)
        total_unknown <- sum(per_file$unknown_count, na.rm = TRUE)
        total_reviewed <- sum(per_file$reviewed_rows, na.rm = TRUE)
        total_evaluable <- total_yes + total_no
        overall <- data.frame(
          review_file = "ALL_REVIEW_FILES",
          role = "all",
          cohort_definition_id = "",
          reviewed_rows = total_reviewed,
          yes_count = total_yes,
          no_count = total_no,
          unknown_count = total_unknown,
          evaluable_rows = total_evaluable,
          precision_ppv = if (total_evaluable > 0) total_yes / total_evaluable else NA_real_,
          recall_estimate = NA_real_,
          recall_note = "Not estimable from a reviewed sample drawn only from cohort-positive rows.",
          phenotype_name = "",
          stringsAsFactors = FALSE
        )
        keep_cols <- c("review_file", "role", "cohort_definition_id", "reviewed_rows", "yes_count", "no_count", "unknown_count", "evaluable_rows", "precision_ppv", "recall_estimate", "recall_note", "phenotype_name")
        per_file <- per_file[, intersect(keep_cols, names(per_file)), drop = FALSE]
        list(
          status = "ok",
          title = "Keeper case-review metrics",
          sections = list(
            list(
              kind = "text",
              text = paste(
                "Precision/PPV is estimated from reviewed Keeper labels as yes / (yes + no), excluding unknown labels.",
                "True recall is not identifiable from this design because the reviewed sample is drawn from cohort-positive rows only and does not include a sampled set of external true positives missed by the cohort."
              )
            ),
            .studyAgentSlashExplorationTableSection(
              data = overall,
              title = "Overall Keeper review metrics",
              preview_data = overall
            ),
            .studyAgentSlashExplorationTableSection(
              data = per_file,
              title = "Per-file Keeper review metrics",
              preview_data = .studyAgentSlashCompactPreviewTable(per_file, max_rows = 20L, max_cols = 10L)
            )
          )
        )
      }
    )
  )
}

.studyAgentSlashListExplorationCommands <- function(base_dir, workflow_type, step_id = NULL) {
  project_state <- tryCatch(.studyAgentSlashReconcileProjectState(base_dir, write = FALSE)$project_state, error = function(e) .studyAgentSlashReadProjectState(base_dir))
  registry <- .studyAgentSlashBuildArtifactRegistry(base_dir)
  commands <- .studyAgentSlashExplorationCommands()
  requested_step_id <- as.character(step_id %||% "")
  eligible_step_ids <- if (nzchar(trimws(requested_step_id))) {
    plan_steps <- project_state$execution_plan %||% list()
    statuses <- vapply(plan_steps, function(step) as.character(step$status %||% ""), character(1))
    step_ids <- vapply(plan_steps, function(step) as.character(step$step_id %||% ""), character(1))
    unique(c(
      requested_step_id,
      step_ids[statuses %in% c("completed", "failed", "stale", "running", "skipped")]
    ))
  } else {
    plan_steps <- project_state$execution_plan %||% list()
    statuses <- vapply(plan_steps, function(step) as.character(step$status %||% ""), character(1))
    step_ids <- vapply(plan_steps, function(step) as.character(step$step_id %||% ""), character(1))
    unique(step_ids[statuses %in% c("completed", "failed", "stale", "running", "skipped")])
  }
  Filter(function(cmd) {
    workflow_ok <- as.character(workflow_type %||% "") %in% as.character(cmd$workflow_types %||% character(0))
    step_ids <- as.character(cmd$step_ids %||% character(0))
    step_ok <- length(step_ids) == 0 || any(step_ids %in% eligible_step_ids)
    requirements <- as.character(cmd$artifact_requirements %||% character(0))
    requirements_ok <- all(vapply(requirements, function(req) {
      item <- Filter(function(artifact) identical(as.character(artifact$artifact_class %||% ""), req), registry)
      length(item) > 0 && any(vapply(item, function(artifact) isTRUE(artifact$exists), logical(1)))
    }, logical(1)))
    isTRUE(workflow_ok && step_ok && requirements_ok)
  }, commands)
}

.studyAgentSlashFindExplorationCommand <- function(command_id) {
  command_id <- as.character(command_id %||% "")
  for (cmd in .studyAgentSlashExplorationCommands()) {
    if (identical(as.character(cmd$command_id %||% ""), command_id)) return(cmd)
  }
  NULL
}

.studyAgentSlashExplorationCommandTable <- function(commands) {
  rows <- lapply(commands, function(cmd) {
    data.frame(
      command_id = as.character(cmd$command_id %||% ""),
      label = as.character(cmd$label %||% ""),
      purpose = as.character(cmd$purpose %||% ""),
      stringsAsFactors = FALSE
    )
  })
  if (length(rows) == 0) {
    return(data.frame(command_id = character(0), label = character(0), purpose = character(0), stringsAsFactors = FALSE))
  }
  do.call(rbind, rows)
}

.studyAgentSlashRenderExplorationResult <- function(result, viewer = FALSE, display = NULL) {
  if (!identical(as.character(result$status %||% ""), "ok")) {
    cat(sprintf("Exploration failed: %s
", as.character(result$error %||% "unknown error")))
    return(invisible(NULL))
  }
  render_mode <- .studyAgentSlashResolveExecutionTableDisplay(display = display, viewer = viewer)
  cat(sprintf("
%s
", as.character(result$title %||% "Exploration result")))
  for (section in result$sections %||% list()) {
    kind <- as.character(section$kind %||% "text")
    if (identical(kind, "text")) {
      cat(sprintf("%s
", as.character(section$text %||% "")))
      next
    }
    if (identical(kind, "table")) {
      if (isTRUE(render_mode$show_console)) {
        print(section$data)
      }
      if (isTRUE(render_mode$open_viewer)) {
        .studyAgentSlashOpenTableViewer(
          data = section$view_data %||% section$data,
          title = section$view_title %||% result$title %||% "Study Agent"
        )
      } else if ((isTRUE(viewer) || !is.null(display)) && !isTRUE(render_mode$supports_viewer)) {
        cat("Viewer mode is not available in this R session; showing the compact console table instead.
")
      }
      next
    }
  }
  cat("
")
  invisible(NULL)
}

.studyAgentSlashRunExplorationCommand <- function(base_dir, command_id) {
  project_state <- .studyAgentSlashReadProjectState(base_dir)
  runtime_state <- .studyAgentSlashReadRuntimeState(base_dir)
  step_id <- as.character(project_state$resume$current_step_id %||% "")
  step <- if (nzchar(step_id)) .studyAgentSlashFindPlanStep(project_state, step_id) else NULL
  command <- .studyAgentSlashFindExplorationCommand(command_id)
  if (is.null(command)) stop(sprintf("Unknown exploration command: %s", command_id))
  available <- .studyAgentSlashListExplorationCommands(base_dir, workflow_type = project_state$workflow_type %||% "", step_id = step_id)
  available_ids <- vapply(available, function(item) as.character(item$command_id %||% ""), character(1))
  if (!(as.character(command_id) %in% available_ids)) stop(sprintf("Exploration command is not available in the current workflow state: %s", command_id))
  context <- .studyAgentSlashBuildExplorationContext(base_dir, project_state, runtime_state, step = step)
  tryCatch(
    command$executor(context),
    error = function(e) list(status = "error", error = conditionMessage(e))
  )
}
