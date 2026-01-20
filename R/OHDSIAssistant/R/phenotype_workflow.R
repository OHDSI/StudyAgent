#' Suggest phenotypes for a study protocol (prototype)
#' @param protocolPath path to protocol markdown/text
#' @param cohortsCatalogPath path/URL to Cohorts.csv catalog
#' @param maxResults max phenotypes to return
#' @param interactive print plan and recommendations
#' @return list response from ACP or local stub
suggestPhenotypes <- function(protocolPath,
                              cohortsCatalogPath,
                              maxResults = 5,
                              interactive = TRUE) {
  protocolPath <- normalizePath(protocolPath, winslash = "/", mustWork = FALSE)
  cohortsCatalogPath <- normalizePath(cohortsCatalogPath, winslash = "/", mustWork = FALSE)
  protocol_txt <- paste(readLines(protocolPath, warn = FALSE), collapse = "\n")
  body <- list(
    protocolRef = protocolPath,
    cohortsCatalogRef = cohortsCatalogPath,
    maxResults = maxResults
  )
  res <- if (!is.null(acp_state$url)) {
    .acp_post("/tools/phenotype_recommendations", body)
  } else {
    local_phenotype_recommendations(protocol_txt, cohortsCatalogPath, maxResults)
  }
  res$artifact <- list(protocolRef = protocolPath, cohortsCatalogRef = cohortsCatalogPath)
  if (interactive) {
    cat("\n== Phenotype Suggestions ==\n")
    cat(res$plan %||% "", "\n")
    if (!is.null(res$mode)) cat(sprintf("Mode: %s\n", res$mode))
    recs <- res$phenotype_recommendations %||% list()
    if (length(recs) == 0) {
      cat("  [stub] No recommendations (LLM not connected or no matches).\n")
    } else {
      for (r in recs) {
        cat(sprintf("  - %s (%s): %s\n",
                    r$cohortName %||% "<unknown>",
                    r$cohortId %||% "?",
                    r$justification %||% ""))
      }
    }
  }
  res
}

#' Pull phenotype definitions to a local folder
#' @param cohortIds integer vector of cohortIds
#' @param outputDir directory to write JSON definitions
#' @param overwrite logical; if FALSE, auto-version the filename
#' @return character vector of written file paths
pullPhenotypeDefinitions <- function(cohortIds,
                                     outputDir = ".",
                                     overwrite = FALSE) {
  outputDir <- normalizePath(outputDir, winslash = "/", mustWork = FALSE)
  if (!dir.exists(outputDir)) dir.create(outputDir, recursive = TRUE)
  cds <- PhenotypeLibrary::getPlCohortDefinitionSet(as.integer(cohortIds))
  written <- character(0)
  for (i in seq_len(nrow(cds))) {
    nm <- cds$cohortName[i] %||% ""
    safe <- gsub("[^A-Za-z0-9_-]+", "_", nm)
    if (identical(safe, "") || is.na(safe)) safe <- paste0("cohort_", cds$cohortId[i])
    fname_base <- file.path(outputDir, sprintf("%s_%s.json", cds$cohortId[i], safe))
    target <- fname_base
    if (!overwrite) {
      idx <- 1
      while (file.exists(target)) {
        target <- file.path(outputDir, sprintf("%s_%s-v%d.json", cds$cohortId[i], safe, idx))
        idx <- idx + 1
      }
    }
    writeLines(cds$json[i], con = target, useBytes = TRUE)
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
    protocolRef = protocolPath,
    cohortRefs = as.list(cohortJsonPaths),
    characterizationRefs = as.list(characterizationPaths %||% list())
  )
  res <- if (!is.null(acp_state$url)) {
    .acp_post("/tools/phenotype_improvements", body)
  } else {
    local_phenotype_improvements()
  }
  res$artifact <- list(protocolRef = protocolPath, cohortRefs = cohortJsonPaths)
  if (interactive) {
    cat("\n== Phenotype Improvements ==\n")
    cat(res$plan %||% "", "\n")
    if (!is.null(res$mode)) cat(sprintf("Mode: %s\n", res$mode))
    imp <- res$phenotype_improvements %||% list()
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
  if (apply) {
    picks <- selectPhenotypeImprovements(
      improvements = res$phenotype_improvements,
      cohortJsonPaths = cohortJsonPaths,
      select = select,
      apply = TRUE,
      outputDir = outputDir,
      interactive = interactive
    )
    res$selected_improvements <- picks$selected
    res$written <- picks$written
    if (interactive && length(picks$written)) {
      cat("\nSaved improvement notes:\n")
      cat(paste(sprintf("  - %s", picks$written), collapse = "\n"), "\n")
    }
  }
  res
}

#' Select phenotype recommendations (interactive or programmatic)
#' @param recommendations list from suggestPhenotypes()$phenotype_recommendations
#' @param select either numeric cohortIds, integer indices, or "all"/NULL to pick all
#' @param interactive if TRUE and select is NULL, prompt user
#' @return integer vector of chosen cohortIds
selectPhenotypeRecommendations <- function(recommendations,
                                           select = NULL,
                                           interactive = interactive()) {
  recs <- recommendations %||% list()
  if (length(recs) == 0) return(integer(0))

  # normalize to cohortIds
  ids <- vapply(recs, function(r) r$cohortId %||% NA_real_, numeric(1))

  if (is.null(select) || identical(select, "all")) {
    if (interactive) {
      labels <- vapply(seq_along(recs), function(i) {
        sprintf("%s (%s)", recs[[i]]$cohortName %||% "<unknown>", recs[[i]]$cohortId %||% "?")
      }, character(1))
      picks <- utils::select.list(labels, multiple = TRUE, title = "Select phenotypes to pull")
      if (length(picks) == 0) return(integer(0))
      idx <- match(picks, labels)
      return(as.integer(ids[idx]))
    }
    return(as.integer(ids))
  }

  # explicit selection provided
  if (is.numeric(select)) {
    # if they look like indices (<= length), map to ids; else assume cohortIds
    if (all(select %% 1 == 0) && all(select >= 1) && all(select <= length(ids))) {
      return(as.integer(ids[select]))
    }
    return(as.integer(select))
  }

  integer(0)
}


#' Select phenotype improvements and optionally persist notes
#' @param improvements list from reviewPhenotypes()$phenotype_improvements
#' @param cohortJsonPaths character vector of cohort JSON paths
#' @param select optional vector of cohortIds/indices or "all"/NULL to pick all
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


local_phenotype_recommendations <- function(protocolText,
                                            cohortsCatalogPath,
                                            maxResults = 5) {
  cat_rows <- tryCatch(read.csv(cohortsCatalogPath, stringsAsFactors = FALSE), error = function(e) NULL)
  recs <- list()
  if (!is.null(cat_rows) && NROW(cat_rows) > 0) {
    n <- min(maxResults, NROW(cat_rows))
    for (i in seq_len(n)) {
      recs[[i]] <- list(
        cohortId = cat_rows$cohortId[i],
        cohortName = cat_rows$cohortNameLong[i] %||% cat_rows$cohortName[i] %||% "",
        justification = "Stub recommendation from deterministic fallback (no LLM)."
      )
    }
  }
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
