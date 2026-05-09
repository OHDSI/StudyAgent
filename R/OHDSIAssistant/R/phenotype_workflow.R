#' Suggest phenotypes for a study protocol (ACP flow)
#' @param protocolPath optional path to protocol markdown/text
#' @param studyIntent optional study intent string (overrides protocolPath)
#' @param topK number of candidates to retrieve from MCP
#' @param maxResults max phenotypes to return
#' @param candidateLimit max candidates to pass to the LLM (optional)
#' @param interactive print plan and recommendations
#' @return list response from ACP flow or local stub
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
  if (is.null(studyIntent) || !nzchar(trimws(studyIntent))) {
    if (interactive) {
      studyIntent <- utils::edit("Enter study intent text below and save/close to continue.")
    }
  }
  if (is.null(studyIntent) || !nzchar(trimws(studyIntent))) {
    stop("Provide studyIntent or protocolPath (with content) to suggestPhenotypes().")
  }

  body <- list(
    study_intent = studyIntent,
    top_k = topK,
    max_results = maxResults
  )
  if (!is.null(candidateLimit)) {
    body$candidate_limit <- candidateLimit
  }

  res <- if (!is.null(acp_state$url)) {
    .acp_post("/flows/phenotype_recommendation", body)
  } else {
    local_phenotype_recommendations(studyIntent, maxResults)
  }

  res$artifact <- list(protocolRef = protocolPath)
  core <- res$recommendations %||% res
  if (interactive) {
    cat("
== Phenotype Suggestions ==
")
    cat(core$plan %||% "", "
")
    if (!is.null(core$mode)) cat(sprintf("Mode: %s
", core$mode))
    recs <- core$phenotype_recommendations %||% list()
    if (length(recs) == 0) {
      cat("  [stub] No recommendations (LLM not connected or no matches).
")
    } else {
      for (r in recs) {
        cat(sprintf("  - %s (%s): %s
",
                    r$phenotype_name %||% "<unknown>",
                    r$phenotype_id %||% "?",
                    r$justification %||% ""))
      }
    }
  }
  res
}

#' Pull phenotype definitions to a local folder
#' @param cohortIds character vector of ACP phenotype ids, typically selected from suggestPhenotypes()
#' @param outputDir directory to write JSON definitions
#' @param overwrite logical; if FALSE, auto-version the filename
#' @return character vector of written file paths
pullPhenotypeDefinitions <- function(cohortIds,
                                     outputDir = ".",
                                     overwrite = FALSE) {
  phenotype_ids <- as.character(cohortIds %||% character(0))
  if (length(phenotype_ids) == 0) return(character(0))

  unsupported <- phenotype_ids[!grepl("^ohdsi:", phenotype_ids)]
  if (length(unsupported) > 0) {
    stop(
      sprintf(
        paste0(
          "pullPhenotypeDefinitions() currently supports OHDSI phenotype ids only. ",
          "Conversion of non-OHDSI phenotypes to computable OHDSI cohort definitions is not implemented yet. ",
          "Unsupported ids: %s"
        ),
        paste(unique(unsupported), collapse = ", ")
      )
    )
  }

  index_dir <- Sys.getenv("PHENOTYPE_INDEX_DIR", "data/phenotype_index")
  index_dir <- normalizePath(index_dir, winslash = "/", mustWork = FALSE)
  index_def_dir <- file.path(index_dir, "definitions")
  if (!dir.exists(index_def_dir)) {
    stop(sprintf("Missing phenotype index definitions folder: %s", index_def_dir))
  }

  outputDir <- normalizePath(outputDir, winslash = "/", mustWork = FALSE)
  if (!dir.exists(outputDir)) dir.create(outputDir, recursive = TRUE)

  definition_path <- function(phenotype_id) {
    file.path(index_def_dir, sprintf("%s.json", gsub(":", "__", phenotype_id, fixed = TRUE)))
  }

  written <- character(0)
  for (phenotype_id in phenotype_ids) {
    src <- definition_path(phenotype_id)
    if (!file.exists(src)) {
      stop(sprintf("Phenotype JSON not found: %s", src))
    }

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

#' Review phenotype definitions for improvements (prototype)
#' @param protocolPath path to protocol markdown/text
#' @param cohortJsonPaths character vector of cohort definition JSON paths
#' @param characterizationPaths optional vector of paths to characterization outputs
#' @param interactive logical; print plan and summaries
#' @return list response from ACP or local stub
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

  body <- list(
    protocol_path = protocolPath,
    cohort_paths = as.list(cohortJsonPaths)
  )
  if (!is.null(characterizationPaths) && length(characterizationPaths) > 0) {
    warning("characterizationPaths are not yet forwarded to /flows/phenotype_improvements; ignoring them for now.")
  }

  res <- if (!is.null(acp_state$url)) {
    .acp_post("/flows/phenotype_improvements", body)
  } else {
    local_phenotype_improvements()
  }

  res$artifact <- list(protocolPath = protocolPath, cohortPaths = cohortJsonPaths)
  core <- res$full_result %||% res
  if (interactive) {
    cat("
== Phenotype Improvements ==
")
    cat(core$plan %||% "", "
")
    if (!is.null(core$mode)) cat(sprintf("Mode: %s
", core$mode))
    imp <- core$phenotype_improvements %||% list()
    if (length(imp) == 0) {
      cat("  [stub] No improvements returned (LLM not connected).
")
    } else {
      for (p in imp) {
        cat(sprintf("  - [%s] %s
",
                    p$targetCohortId %||% "?",
                    p$summary %||% jsonlite::toJSON(p, auto_unbox = TRUE)))
      }
    }
  }
  if (apply) {
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
    if (interactive && length(picks$written)) {
      cat("
Saved improvement notes:
")
      cat(paste(sprintf("  - %s", picks$written), collapse = "
"), "
")
    }
  }
  res
}

#' Select phenotype recommendations (interactive or programmatic)
#' @param recommendations list from suggestPhenotypes()$phenotype_recommendations
#' @param select either phenotype ids, integer indices, or "all"/NULL to pick all
#' @param interactive if TRUE and select is NULL, prompt user
#' @return character vector of chosen phenotype ids
selectPhenotypeRecommendations <- function(recommendations,
                                           select = NULL,
                                           interactive = interactive()) {
  recs <- recommendations %||% list()
  if (length(recs) == 0) return(character(0))

  ids <- vapply(recs, function(r) r$phenotype_id %||% NA_character_, character(1))

  if (is.null(select) || identical(select, "all")) {
    if (interactive) {
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

  # explicit selection provided
  if (is.numeric(select)) {
    # if they look like indices (<= length), map to ids; else assume ids already supplied
    if (all(select %% 1 == 0) && all(select >= 1) && all(select <= length(ids))) {
      return(as.character(ids[select]))
    }
    return(as.character(select))
  }

  if (is.character(select)) {
    if (all(select %in% ids)) {
      return(as.character(select))
    }
    idx <- suppressWarnings(as.integer(select))
    if (!anyNA(idx) && all(idx >= 1) && all(idx <= length(ids))) {
      return(as.character(ids[idx]))
    }
  }

  character(0)
}


#' Select phenotype improvements and optionally persist notes
#' @param improvements list from reviewPhenotypes()$phenotype_improvements
#' @param cohortJsonPaths character vector of cohort JSON paths
#' @param select optional vector of phenotype ids, indices, or "all"/NULL to pick all
#' @param apply logical; if TRUE, write selected improvements to disk
#' @param outputDir directory for notes; defaults to directory of first cohortJsonPath
#' @param interactive prompt user selection when select is NULL
#' @return list with `selected` improvements and `written` file paths (if any)
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
  cohortPathIds <- vapply(cohortJsonPaths, .extractCohortIdFromPath, integer(1), USE.NAMES = FALSE)

  # selection logic
  idx <- integer(0)
  if (is.null(select) || identical(select, "all")) {
    if (interactive) {
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

  if (apply && length(picked)) {
    if (is.null(outputDir)) {
      outputDir <- dirname(cohortJsonPaths[[1]] %||% ".")
    }
    if (!dir.exists(outputDir)) dir.create(outputDir, recursive = TRUE, showWarnings = FALSE)
    written <- .writePhenotypeImprovementNotes(picked, cohortJsonPaths, cohortPathIds, outputDir)
  }

  list(selected = picked, written = written)
}


.extractCohortIdFromPath <- function(path) {
  base <- basename(path %||% "")
  m <- regexpr("[0-9]+", base)
  if (m[1] > 0) {
    val <- substr(base, m[1], m[1] + attr(m, "match.length") - 1)
    return(suppressWarnings(as.integer(val)))
  }
  NA_integer_
}


.writePhenotypeImprovementNotes <- function(improvements, cohortJsonPaths, cohortPathIds, outputDir) {
  written <- character(0)
  if (length(improvements) == 0) return(written)
  ids <- vapply(improvements, function(x) x$targetCohortId %||% NA_integer_, integer(1))
  for (cid in unique(ids)) {
    if (is.na(cid)) next
    idx_imp <- which(ids == cid)
    if (length(idx_imp) == 0) next
    path_idx <- match(cid, cohortPathIds, nomatch = 0)
    fname_base <- if (path_idx > 0) tools::file_path_sans_ext(basename(cohortJsonPaths[[path_idx]])) else paste0("cohort_", cid)
    target <- file.path(outputDir, sprintf("%s_improvements.json", fname_base))
    jsonlite::write_json(improvements[idx_imp], path = target, auto_unbox = TRUE, pretty = TRUE)
    written <- c(written, target)
  }
  written
}


local_phenotype_recommendations <- function(studyIntent,
                                            maxResults = 10) {
  recs <- list()
  list(
    plan = "Stub: deterministic phenotype suggestions (LLM not connected).",
    phenotype_recommendations = recs,
    mode = "stub"
  )
}


local_phenotype_improvements <- function() {
  list(
    plan = "Stub: no phenotype improvements available without LLM.",
    phenotype_improvements = list(),
    code_suggestion = NULL,
    mode = "stub"
  )
}
