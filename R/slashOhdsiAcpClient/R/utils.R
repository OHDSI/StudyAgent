`%||%` <- function(a, b) if (is.null(a)) b else a

.normalize_acp_body <- function(body) {
  if (!is.list(body)) return(body)
  if (!is.null(body$protocolRef)) body$protocolRef <- as.character(body$protocolRef)
  if (!is.null(body$cohortsCatalogRef)) body$cohortsCatalogRef <- as.character(body$cohortsCatalogRef)
  if (!is.null(body$cohortRefs)) {
    body$cohortRefs <- as.list(unname(vapply(body$cohortRefs, as.character, character(1))))
  }
  if (!is.null(body$characterizationRefs)) {
    body$characterizationRefs <- as.list(unname(vapply(body$characterizationRefs, as.character, character(1))))
  }
  body
}

.acp_timeout_seconds <- function(default = 180) {
  timeout_seconds <- as.numeric(Sys.getenv("ACP_TIMEOUT", as.character(default)))
  if (is.na(timeout_seconds) || timeout_seconds <= 0) timeout_seconds <- default
  timeout_seconds
}

.acp_normalize_local_path <- function(path, label = "path") {
  path <- trimws(as.character(path %||% ""))
  if (!nzchar(path)) stop("Provide a non-empty ", label, ".")
  normalized <- normalizePath(path, winslash = "/", mustWork = FALSE)
  if (!file.exists(normalized)) stop("Missing ", label, ": ", normalized)
  normalized
}

.acp_read_text_file <- function(path, label = "file") {
  normalized <- .acp_normalize_local_path(path, label = label)
  size <- file.info(normalized)$size %||% 0
  readChar(normalized, nchars = size, useBytes = TRUE)
}

.acp_read_json_file <- function(path, label = "json file") {
  normalized <- .acp_normalize_local_path(path, label = label)
  jsonlite::fromJSON(normalized, simplifyVector = FALSE)
}

.acp_infer_id_from_path <- function(path) {
  base <- basename(as.character(path %||% ""))
  if (!nzchar(base)) return(NULL)
  chars <- strsplit(base, "", fixed = TRUE)[[1]]
  digits <- character(0)
  for (ch in chars) {
    if (grepl("[0-9]", ch)) {
      digits <- c(digits, ch)
    } else if (length(digits)) {
      break
    }
  }
  if (!length(digits)) return(NULL)
  suppressWarnings(as.integer(paste0(digits, collapse = "")))
}

.acp_patch_cohort_id_from_path <- function(cohort, path) {
  if (!is.list(cohort)) stop("Cohort JSON must decode to an object.")
  current_id <- cohort$id %||% cohort$cohortId %||% cohort$CohortId %||% NULL
  if (!is.null(current_id)) return(cohort)
  inferred_id <- .acp_infer_id_from_path(path)
  if (!is.null(inferred_id) && !is.na(inferred_id)) cohort$id <- inferred_id
  cohort
}

.acp_load_cohort_from_path <- function(path, label = "cohort_path") {
  cohort <- .acp_read_json_file(path, label = label)
  .acp_patch_cohort_id_from_path(cohort, path)
}

.acp_load_keeper_concept_sets <- function(path) {
  payload <- .acp_read_json_file(path, label = "keeper_concept_sets_path")
  if (is.list(payload$concept_sets)) return(payload$concept_sets)
  if (is.list(payload$keeper_concept_sets)) return(payload$keeper_concept_sets)
  if (is.list(payload) && length(payload) > 0 && is.list(payload[[1]])) return(payload)
  stop("Unsupported keeper concept-set payload: ", .acp_normalize_local_path(path, label = "keeper_concept_sets_path"))
}

.acp_select_keeper_row <- function(rows, row_index = NULL) {
  if (!length(rows)) return(NULL)
  if (is.null(row_index)) return(rows[[1]])
  idx <- suppressWarnings(as.integer(row_index))
  if (is.na(idx) || idx < 1L || idx > length(rows)) stop("row_index_out_of_bounds: ", row_index)
  rows[[idx]]
}

.acp_load_keeper_row <- function(path, row_index = NULL) {
  normalized <- .acp_normalize_local_path(path, label = "keeper_row_path")
  if (grepl("\\.csv$", normalized, ignore.case = TRUE)) {
    data <- utils::read.csv(normalized, stringsAsFactors = FALSE, check.names = FALSE)
    rows <- lapply(seq_len(nrow(data)), function(i) as.list(data[i, , drop = FALSE]))
    return(.acp_select_keeper_row(rows, row_index = row_index))
  }

  payload <- jsonlite::fromJSON(normalized, simplifyVector = FALSE)
  if (is.list(payload$rows)) return(.acp_select_keeper_row(payload$rows, row_index = row_index))
  if (is.list(payload) && length(payload) > 0 && is.list(payload[[1]])) {
    return(.acp_select_keeper_row(payload, row_index = row_index))
  }
  if (!is.null(row_index) && as.integer(row_index) != 1L) {
    stop("row_index_unsupported_for_payload: ", row_index)
  }
  payload
}
