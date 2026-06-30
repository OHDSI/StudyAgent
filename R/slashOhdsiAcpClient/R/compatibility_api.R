.acp_default_state <- local({
  env <- new.env(parent = emptyenv())
  env$client <- NULL
  env
})

#' Connect to ACP and store a default client
#' @param url ACP base URL
#' @param token optional bearer token
#' @return invisible TRUE
#' @export
acp_connect <- function(url = "http://127.0.0.1:8765", token = NULL) {
  .acp_default_state$client <- acp_client(url = url, token = token, check = TRUE)
  invisible(TRUE)
}

#' Get the default ACP client if connected
#' @return ACP client object or NULL
#' @export
acp_get_default_client <- function() {
  .acp_default_state$client
}

.extract_cohort_id_from_path <- function(path) {
  base <- basename(path %||% "")
  match <- regexpr("[0-9]+", base)
  if (match[[1]] < 1) return(NA_integer_)
  suppressWarnings(as.integer(substr(base, match[[1]], match[[1]] + attr(match, "match.length") - 1)))
}

.write_phenotype_improvement_notes <- function(improvements, cohortJsonPaths, cohortPathIds, outputDir) {
  ids <- vapply(improvements, function(x) x$targetCohortId %||% NA_integer_, integer(1))
  written <- character(0)
  for (i in seq_along(improvements)) {
    cohort_id <- ids[[i]]
    src_path <- cohortJsonPaths[match(cohort_id, cohortPathIds, nomatch = 0)] %||% ""
    stem <- if (nzchar(src_path)) tools::file_path_sans_ext(basename(src_path)) else paste0("cohort_", cohort_id)
    out_path <- file.path(outputDir, sprintf("%s_improvements.json", stem))
    jsonlite::write_json(improvements[[i]], out_path, pretty = TRUE, auto_unbox = TRUE)
    written <- c(written, out_path)
  }
  written
}

local_phenotype_recommendations <- function(studyIntent, maxResults = 3) {
  list(
    source = "stub_no_acp",
    status = "stub",
    recommendations = list(
      plan = sprintf("Local stub phenotype recommendations for: %s", studyIntent),
      mode = "stub_no_acp",
      phenotype_recommendations = vector("list", length = 0)
    )
  )
}

local_phenotype_improvements <- function() {
  list(
    source = "stub_no_acp",
    status = "stub",
    full_result = list(
      plan = "Local stub phenotype improvements",
      mode = "stub_no_acp",
      phenotype_improvements = vector("list", length = 0)
    )
  )
}

#' Suggest phenotypes for a study protocol
#' @param protocolPath optional path to protocol markdown/text
#' @param studyIntent optional study intent string
#' @param topK number of candidates to retrieve from MCP
#' @param maxResults max phenotypes to return
#' @param candidateLimit max candidates to pass to the LLM
#' @param interactive print plan and recommendations
#' @return list response from ACP flow or local stub
#' @export
suggestPhenotypes <- function(protocolPath = NULL,
                              studyIntent = NULL,
                              topK = 20,
                              maxResults = 3,
                              candidateLimit = 10,
                              interactive = TRUE) {
  if (!is.null(protocolPath)) {
    protocolPath <- normalizePath(protocolPath, winslash = "/", mustWork = FALSE)
  }
  if (is.null(studyIntent) && !is.null(protocolPath)) {
    studyIntent <- paste(readLines(protocolPath, warn = FALSE), collapse = "\n")
  }
  if (is.null(studyIntent) && isTRUE(interactive)) {
    studyIntent <- utils::edit("Enter study intent text below and save/close to continue.")
  }
  if (is.null(studyIntent) || !nzchar(trimws(studyIntent))) {
    stop("Provide studyIntent or protocolPath (with content) to suggestPhenotypes().")
  }

  client <- acp_get_default_client()
  res <- if (!is.null(client)) {
    acp_suggest_phenotypes(
      client = client,
      study_intent = studyIntent,
      top_k = topK,
      max_results = maxResults,
      candidate_limit = candidateLimit
    )
  } else {
    local_phenotype_recommendations(studyIntent, maxResults)
  }

  res$artifact <- list(protocolRef = protocolPath)
  core <- res$recommendations %||% res
  if (isTRUE(interactive)) {
    cat("\n== Phenotype Suggestions ==\n")
    cat(core$plan %||% "", "\n")
    if (!is.null(core$mode)) cat(sprintf("Mode: %s\n", core$mode))
    recs <- core$phenotype_recommendations %||% list()
    if (length(recs) == 0) {
      cat("  [stub] No recommendations (LLM not connected or no matches).\n")
    } else {
      for (r in recs) {
        cat(sprintf("  - %s (%s): %s\n",
                    r$phenotype_name %||% "<unknown>",
                    r$phenotype_id %||% "?",
                    r$justification %||% ""))
      }
    }
  }
  res
}

#' Pull phenotype definitions to a local folder
#' @param cohortIds character vector of ACP phenotype ids
#' @param outputDir directory to write JSON definitions
#' @param overwrite logical; if FALSE, auto-version the filename
#' @return character vector of written file paths
#' @export
pullPhenotypeDefinitions <- function(cohortIds,
                                     outputDir = ".",
                                     overwrite = FALSE) {
  phenotype_ids <- as.character(cohortIds %||% character(0))
  if (length(phenotype_ids) == 0) return(character(0))

  unsupported <- phenotype_ids[!grepl("^ohdsi:", phenotype_ids)]
  if (length(unsupported) > 0) {
    stop(sprintf(
      paste0(
        "pullPhenotypeDefinitions() currently supports OHDSI phenotype ids only. ",
        "Conversion of non-OHDSI phenotypes to computable OHDSI cohort definitions is not implemented yet. ",
        "Unsupported ids: %s"
      ),
      paste(unique(unsupported), collapse = ", ")
    ))
  }

  index_dir <- Sys.getenv("PHENOTYPE_INDEX_DIR", "data/phenotype_index")
  index_dir <- normalizePath(index_dir, winslash = "/", mustWork = FALSE)
  index_def_dir <- file.path(index_dir, "definitions")
  if (!dir.exists(index_def_dir)) stop(sprintf("Missing phenotype index definitions folder: %s", index_def_dir))

  outputDir <- normalizePath(outputDir, winslash = "/", mustWork = FALSE)
  if (!dir.exists(outputDir)) dir.create(outputDir, recursive = TRUE)

  definition_path <- function(phenotype_id) {
    file.path(index_def_dir, sprintf("%s.json", gsub(":", "__", phenotype_id, fixed = TRUE)))
  }

  written <- character(0)
  for (phenotype_id in phenotype_ids) {
    src <- definition_path(phenotype_id)
    if (!file.exists(src)) stop(sprintf("Phenotype JSON not found: %s", src))
    safe <- gsub("[^A-Za-z0-9_-]+", "_", phenotype_id)
    target <- file.path(outputDir, sprintf("%s.json", safe))
    if (!overwrite) {
      idx <- 1
      while (file.exists(target)) {
        target <- file.path(outputDir, sprintf("%s-v%d.json", safe, idx))
        idx <- idx + 1
      }
    }
    file.copy(src, target, overwrite = TRUE)
    written <- c(written, target)
  }
  written
}

#' Review phenotype definitions for improvements
#' @param protocolPath local path to protocol markdown/text; the client loads and sends inline protocol_text to ACP
#' @param cohortJsonPaths character vector of local cohort definition JSON paths; the client loads and sends inline cohorts to ACP
#' @param characterizationPaths optional vector of characterization outputs
#' @param interactive logical; print plan and summaries
#' @param apply logical; write selected improvements to disk
#' @param select selection vector for improvements
#' @param outputDir directory for written improvement notes
#' @return list response from ACP or local stub
#' @export
reviewPhenotypes <- function(protocolPath,
                             cohortJsonPaths,
                             characterizationPaths = NULL,
                             interactive = TRUE,
                             apply = FALSE,
                             select = NULL,
                             outputDir = NULL) {
  protocolPath <- normalizePath(protocolPath, winslash = "/", mustWork = FALSE)
  cohortJsonPaths <- unname(vapply(cohortJsonPaths, normalizePath, character(1), winslash = "/", mustWork = FALSE))
  if (length(cohortJsonPaths) == 0) stop("No cohortJsonPaths provided to reviewPhenotypes().")
  if (!is.null(characterizationPaths)) {
    characterizationPaths <- unname(vapply(characterizationPaths, normalizePath, character(1), winslash = "/", mustWork = FALSE))
  }

  client <- acp_get_default_client()
  res <- if (!is.null(client)) {
    acp_review_phenotypes(client, protocol_path = protocolPath, cohort_paths = cohortJsonPaths)
  } else {
    local_phenotype_improvements()
  }

  res$artifact <- list(protocolPath = protocolPath, cohortPaths = cohortJsonPaths)
  core <- res$full_result %||% res
  if (isTRUE(interactive)) {
    cat("\n== Phenotype Improvements ==\n")
    cat(core$plan %||% "", "\n")
    if (!is.null(core$mode)) cat(sprintf("Mode: %s\n", core$mode))
    imp <- core$phenotype_improvements %||% list()
    if (length(imp) == 0) {
      cat("  [stub] No improvements returned (LLM not connected).\n")
    } else {
      for (p in imp) {
        cat(sprintf("  - [%s] %s\n",
                    p$targetCohortId %||% "?",
                    p$summary %||% jsonlite::toJSON(p, auto_unbox = TRUE)))
      }
    }
  }
  if (isTRUE(apply)) {
    picks <- selectPhenotypeImprovements(
      improvements = core$phenotype_improvements,
      cohortJsonPaths = cohortJsonPaths,
      select = select,
      apply = TRUE,
      outputDir = outputDir,
      interactive = interactive
    )
    res$selected_improvements <- picks$selected
    res$written <- picks$written
  }
  res
}

#' Select phenotype recommendations
#' @param recommendations list from suggestPhenotypes()$phenotype_recommendations
#' @param select phenotype ids, integer indices, or "all"/NULL
#' @param interactive if TRUE and select is NULL, prompt user
#' @return character vector of chosen phenotype ids
#' @export
selectPhenotypeRecommendations <- function(recommendations,
                                           select = NULL,
                                           interactive = interactive()) {
  recs <- recommendations %||% list()
  if (length(recs) == 0) return(character(0))
  ids <- vapply(recs, function(r) r$phenotype_id %||% NA_character_, character(1))
  if (is.null(select) || identical(select, "all")) {
    if (isTRUE(interactive)) {
      labels <- vapply(seq_along(recs), function(i) {
        sprintf("%s (%s)", recs[[i]]$phenotype_name %||% "<unknown>", recs[[i]]$phenotype_id %||% "?")
      }, character(1))
      picks <- utils::select.list(labels, multiple = TRUE, title = "Select phenotypes to pull")
      if (length(picks) == 0) return(character(0))
      idx <- match(picks, labels)
      return(as.character(ids[idx]))
    }
    return(as.character(ids))
  }
  if (is.numeric(select)) {
    if (all(select %% 1 == 0) && all(select >= 1) && all(select <= length(ids))) return(as.character(ids[select]))
    return(as.character(select))
  }
  if (is.character(select)) {
    if (all(select %in% ids)) return(as.character(select))
    idx <- suppressWarnings(as.integer(select))
    if (!anyNA(idx) && all(idx >= 1) && all(idx <= length(ids))) return(as.character(ids[idx]))
  }
  character(0)
}

#' Select phenotype improvements and optionally persist notes
#' @param improvements list from reviewPhenotypes()$phenotype_improvements
#' @param cohortJsonPaths cohort JSON paths
#' @param select selection vector or "all"/NULL
#' @param apply when TRUE, write selected improvements to disk
#' @param outputDir destination directory
#' @param interactive prompt user when select is NULL
#' @return list with selected improvements and written file paths
#' @export
selectPhenotypeImprovements <- function(improvements,
                                        cohortJsonPaths,
                                        select = NULL,
                                        apply = FALSE,
                                        outputDir = NULL,
                                        interactive = interactive()) {
  imps <- improvements %||% list()
  if (length(imps) == 0) return(list(selected = list(), written = character(0)))
  ids <- vapply(imps, function(x) x$targetCohortId %||% NA_real_, numeric(1))
  cohortJsonPaths <- cohortJsonPaths %||% character(0)
  cohortPathIds <- vapply(cohortJsonPaths, .extract_cohort_id_from_path, integer(1), USE.NAMES = FALSE)

  idx <- integer(0)
  if (is.null(select) || identical(select, "all")) {
    if (isTRUE(interactive)) {
      labels <- vapply(seq_along(imps), function(i) {
        cid <- ids[[i]] %||% NA_real_
        path_hint <- cohortJsonPaths[match(cid, cohortPathIds, nomatch = 0)] %||% ""
        sprintf("Cohort %s: %s%s",
                cid %||% "?",
                imps[[i]]$summary %||% "<no summary>",
                ifelse(path_hint != "", sprintf(" [%s]", basename(path_hint)), ""))
      }, character(1))
      picks <- utils::select.list(labels, multiple = TRUE, title = "Select phenotype improvements to keep")
      if (length(picks) == 0) return(list(selected = list(), written = character(0)))
      idx <- match(picks, labels)
    } else {
      idx <- seq_along(imps)
    }
  } else if (is.numeric(select)) {
    if (all(select %% 1 == 0) && all(select >= 1) && all(select <= length(imps))) {
      idx <- as.integer(select)
    } else {
      idx <- which(ids %in% as.integer(select))
    }
  }

  if (length(idx) == 0) return(list(selected = list(), written = character(0)))
  picked <- imps[idx]
  written <- character(0)
  if (isTRUE(apply) && length(picked)) {
    if (is.null(outputDir)) outputDir <- dirname(cohortJsonPaths[[1]] %||% ".")
    if (!dir.exists(outputDir)) dir.create(outputDir, recursive = TRUE, showWarnings = FALSE)
    written <- .write_phenotype_improvement_notes(picked, cohortJsonPaths, cohortPathIds, outputDir)
  }
  list(selected = picked, written = written)
}
