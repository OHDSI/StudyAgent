#' Interactive shell to generate Strategus CohortIncidence scripts
#' @param outputDir directory where scripts and artifacts will be written
#' @param acpUrl ACP base URL
#' @param studyIntent study intent text
#' @param topK number of candidates retrieved from MCP search
#' @param maxResults max phenotypes to show
#' @param candidateLimit max candidates to pass to LLM
#' @param indexDir phenotype index directory (contains definitions/)
#' @param interactive whether to prompt for inputs
#' @param bannerPath optional path to ASCII banner
#' @param studyAgentBaseDir base directory to resolve relative paths (outputDir, indexDir, bannerPath)
#' @param reset when TRUE, delete outputDir before running
#' @param allowCache reuse cached artifacts when present
#' @param promptOnCache prompt before using cached artifacts
#' @param autoApplyImprovements when TRUE, apply improvements without prompting (defaults to TRUE for non-interactive)
#' @param resume when TRUE, resume from last checkpoint if present
#' @return invisible list with output paths
#' @export
runStrategusIncidenceShell <- function(outputDir = "demo-strategus-cohort-incidence",
                                      acpUrl = "http://127.0.0.1:8765",
                                      studyIntent = NULL,
                                      topK = 20,
                                      maxResults = 20,
                                      candidateLimit = 20,
                                      indexDir = Sys.getenv("PHENOTYPE_INDEX_DIR", "data/phenotype_index"),
                                      interactive = TRUE,
                                      bannerPath = "ohdsi-logo-ascii.txt",
                                      studyAgentBaseDir = Sys.getenv("STUDY_AGENT_BASE_DIR", ""),
                                      reset = FALSE,
                                      allowCache = TRUE,
                                      promptOnCache = TRUE,
                                      autoApplyImprovements = NA,
                                      resume = FALSE) {
  `%||%` <- function(x, y) if (is.null(x)) y else x

  ensure_dir <- function(path) {
    if (!dir.exists(path)) dir.create(path, recursive = TRUE)
  }

  prompt_yesno <- function(prompt, default = TRUE) {
    if (!isTRUE(interactive)) return(default)
    suffix <- if (default) "[Y/n]" else "[y/N]"
    resp <- tolower(trimws(readline(sprintf("%s %s ", prompt, suffix))))
    if (resp == "") return(default)
    if (resp %in% c("y", "yes")) return(TRUE)
    if (resp %in% c("n", "no")) return(FALSE)
    default
  }

  maybe_use_cache <- function(path, label) {
    if (!allowCache || !file.exists(path)) return(FALSE)
    if (!promptOnCache) return(TRUE)
    prompt_yesno(sprintf("Use cached %s at %s?", label, path), default = TRUE)
  }

  if (is.na(autoApplyImprovements)) {
    autoApplyImprovements <- !isTRUE(interactive)
  }

  read_json <- function(path) {
    jsonlite::fromJSON(path, simplifyVector = FALSE)
  }

  write_json <- function(x, path) {
    jsonlite::write_json(x, path, pretty = TRUE, auto_unbox = TRUE)
  }

  acp_try <- function(path, body, label) {
    repeat {
      resp <- NULL
      err <- NULL
      resp <- tryCatch(
        .acp_post(path, body),
        error = function(e) {
          err <<- e
          NULL
        }
      )
      if (is.null(err)) return(resp)
      msg <- conditionMessage(err)
      if (!isTRUE(interactive)) stop(msg)
      retry <- prompt_yesno(sprintf("ACP call failed (%s). Try again?", msg), default = TRUE)
      if (!retry) {
        mark_checkpoint(label, list(path = path, error = msg))
        stop(sprintf("Stopping after ACP error. Resume with resume=TRUE once ready. (%s)", label))
      }
    }
  }

  checkpoint_path <- function(label) {
    file.path(output_dir, paste0("checkpoint_", label, ".json"))
  }

  mark_checkpoint <- function(label, payload = list()) {
    checkpoint <- list(step = label)
    if (length(payload) > 0) checkpoint <- c(checkpoint, payload)
    write_json(checkpoint, checkpoint_path(label))
  }

  has_checkpoint <- function(label) {
    file.exists(checkpoint_path(label))
  }

  is_absolute_path <- function(path) {
    grepl("^(/|[A-Za-z]:[\\\\/])", path)
  }

  resolve_path <- function(path, base_dir = "") {
    if (!nzchar(path)) return(path)
    if (is_absolute_path(path)) return(path)
    if (nzchar(base_dir)) return(file.path(base_dir, path))
    path
  }

  copy_cohort_json_multi <- function(source_id, dest_id, dest_dirs, index_def_dir) {
    src <- file.path(index_def_dir, sprintf("%s.json", source_id))
    if (!file.exists(src)) stop(sprintf("Cohort JSON not found: %s", src))
    dests <- character(0)
    for (dest_dir in dest_dirs) {
      ensure_dir(dest_dir)
      dest <- file.path(dest_dir, sprintf("%s.json", dest_id))
      file.copy(src, dest, overwrite = TRUE)
      dests <- c(dests, dest)
    }
    dests
  }

  apply_action <- function(obj, action) {
    path <- action$path %||% ""
    value <- action$value
    if (!nzchar(path)) return(obj)
    segs <- strsplit(path, "/", fixed = TRUE)[[1]]
    segs <- segs[segs != ""]

    set_in <- function(x, segs, value) {
      if (length(segs) == 0) return(value)
      seg <- segs[[1]]
      name <- seg
      idx <- NA_integer_
      if (grepl("\\[\\d+\\]$", seg)) {
        name <- sub("\\[\\d+\\]$", "", seg)
        idx <- as.integer(sub("^.*\\[(\\d+)\\]$", "\\1", seg))
      }
      if (name != "") {
        if (is.null(x[[name]])) x[[name]] <- list()
        if (length(segs) == 1) {
          if (!is.na(idx)) {
            if (length(x[[name]]) < idx) {
              while (length(x[[name]]) < idx) x[[name]][[length(x[[name]]) + 1]] <- NULL
            }
            x[[name]][[idx]] <- value
          } else {
            x[[name]] <- value
          }
          return(x)
        }
        if (!is.na(idx)) {
          if (length(x[[name]]) < idx) {
            while (length(x[[name]]) < idx) x[[name]][[length(x[[name]]) + 1]] <- list()
          }
          x[[name]][[idx]] <- set_in(x[[name]][[idx]], segs[-1], value)
        } else {
          x[[name]] <- set_in(x[[name]], segs[-1], value)
        }
        return(x)
      }
      idx <- suppressWarnings(as.integer(seg))
      if (is.na(idx)) return(x)
      if (idx == 0) idx <- 1
      if (length(x) < idx) {
        while (length(x) < idx) x[[length(x) + 1]] <- list()
      }
      if (length(segs) == 1) {
        x[[idx]] <- value
        return(x)
      }
      x[[idx]] <- set_in(x[[idx]], segs[-1], value)
      x
    }

    set_in(obj, segs, value)
  }

  study_base_dir <- ""
  if (nzchar(studyAgentBaseDir)) {
    study_base_dir <- normalizePath(studyAgentBaseDir, winslash = "/", mustWork = FALSE)
  }
  outputDir <- resolve_path(outputDir, study_base_dir)
  outputDir <- normalizePath(outputDir, winslash = "/", mustWork = FALSE)
  if (isTRUE(reset) && dir.exists(outputDir)) {
    ok <- TRUE
    if (isTRUE(interactive)) {
      ok <- prompt_yesno(sprintf("Delete existing output directory %s?", outputDir), default = FALSE)
    }
    if (ok) {
      unlink(outputDir, recursive = TRUE, force = TRUE)
    }
  }
  base_dir <- outputDir
  index_dir <- resolve_path(indexDir, study_base_dir)
  index_dir <- normalizePath(index_dir, winslash = "/", mustWork = FALSE)
  if (!dir.exists(index_dir) && !is_absolute_path(indexDir) && !nzchar(studyAgentBaseDir)) {
    alt <- file.path(getwd(), "OHDSI-Study-Agent", indexDir)
    if (dir.exists(alt)) index_dir <- normalizePath(alt, winslash = "/", mustWork = FALSE)
  }
  index_def_dir <- file.path(index_dir, "definitions")
  if (!dir.exists(index_def_dir)) stop(sprintf("Missing phenotype index definitions folder: %s", index_def_dir))

  output_dir <- file.path(base_dir, "outputs")
  selected_dir <- file.path(base_dir, "selected-cohorts")
  patched_dir <- file.path(base_dir, "patched-cohorts")
  selected_target_dir <- file.path(base_dir, "selected-target-cohorts")
  selected_outcome_dir <- file.path(base_dir, "selected-outcome-cohorts")
  patched_target_dir <- file.path(base_dir, "patched-target-cohorts")
  patched_outcome_dir <- file.path(base_dir, "patched-outcome-cohorts")
  keeper_dir <- file.path(base_dir, "keeper-case-review")
  analysis_settings_dir <- file.path(base_dir, "analysis-settings")
  scripts_dir <- file.path(base_dir, "scripts")

  ensure_dir(output_dir)
  ensure_dir(selected_dir)
  ensure_dir(patched_dir)
  ensure_dir(selected_target_dir)
  ensure_dir(selected_outcome_dir)
  ensure_dir(patched_target_dir)
  ensure_dir(patched_outcome_dir)
  ensure_dir(keeper_dir)
  ensure_dir(analysis_settings_dir)
  ensure_dir(scripts_dir)

  if (interactive) {
    banner_path <- resolve_path(bannerPath, study_base_dir)
    banner_path <- normalizePath(banner_path, winslash = "/", mustWork = FALSE)
    if (!file.exists(banner_path) && !is_absolute_path(bannerPath) && !nzchar(studyAgentBaseDir)) {
      alt <- file.path(getwd(), "OHDSI-Study-Agent", bannerPath)
      if (file.exists(alt)) banner_path <- normalizePath(alt, winslash = "/", mustWork = FALSE)
    }
    if (file.exists(banner_path)) {
      cat(paste(readLines(banner_path, warn = FALSE), collapse = "\n"), "\n")
    }
    cat("\nStudy Agent: Strategus CohortIncidence shell\n")
  }

  default_intent <- studyIntent %||% "What is the risk of GI bleed in new users of Celecoxib compared to new users of Diclofenac?"
  if (interactive) {
    entered <- readline(sprintf("Study intent [%s]: ", default_intent))
    if (nzchar(trimws(entered))) studyIntent <- entered else studyIntent <- default_intent
  } else {
    if (is.null(studyIntent) || !nzchar(trimws(studyIntent))) studyIntent <- default_intent
  }

  if (interactive) {
    cat("\nConnecting to ACP...\n")
  }
  acp_connect(acpUrl)

  intent_split_path <- file.path(output_dir, "intent_split.json")
  intent_response <- NULL
  if (interactive) {
    cat("\n== Step 1: Parse study intent into target/outcome statements ==\n")
  }
  if (maybe_use_cache(intent_split_path, "intent split")) {
    intent_response <- read_json(intent_split_path)
  } else {
    message("Calling ACP flow: phenotype_intent_split")
    intent_response <- acp_try("/flows/phenotype_intent_split", list(study_intent = studyIntent), "intent_split")
    write_json(intent_response, intent_split_path)
  }
  intent_core <- intent_response$intent_split %||% intent_response
  target_statement <- intent_core$target_statement %||% ""
  outcome_statement <- intent_core$outcome_statement %||% ""
  rationale <- intent_core$rationale %||% ""
  if (interactive) {
    if (nzchar(rationale)) {
      cat("\nSuggested rationale:\n")
      cat(rationale, "\n")
    }
    if (length(intent_core$questions %||% list()) > 0) {
      cat("Questions to clarify:\n")
      for (q in intent_core$questions) cat(sprintf("  - %s\n", q))
    }
    inp <- readline(sprintf("Target cohort statement [%s]: ", target_statement))
    if (nzchar(trimws(inp))) target_statement <- inp
    inp <- readline(sprintf("Outcome cohort statement [%s]: ", outcome_statement))
    if (nzchar(trimws(inp))) outcome_statement <- inp
  }
  if (!nzchar(trimws(target_statement))) stop("Missing target cohort statement.")
  if (!nzchar(trimws(outcome_statement))) stop("Missing outcome cohort statement.")

  recs_target_path <- file.path(output_dir, "recommendations_target.json")
  recs_outcome_path <- file.path(output_dir, "recommendations_outcome.json")
  used_cached_recs_target <- FALSE
  used_cached_recs_outcome <- FALSE
  used_window2_target <- FALSE
  used_window2_outcome <- FALSE
  used_advice_target <- FALSE
  used_advice_outcome <- FALSE
  rec_response_target <- NULL
  rec_response_outcome <- NULL

  do_target_recs <- !isTRUE(resume) || !has_checkpoint("target_advice")
  if (interactive && !do_target_recs) {
    cat("\n== Step 2: Target phenotype recommendations (resumed) ==\n")
  }
  if (do_target_recs) {
    if (interactive) {
      cat("\n== Step 2: Target phenotype recommendations ==\n")
    }
    if (maybe_use_cache(recs_target_path, "target recommendations")) {
      rec_response_target <- read_json(recs_target_path)
      used_cached_recs_target <- TRUE
    } else {
      message("Calling ACP flow: phenotype_recommendation (target)")
      body <- list(
        study_intent = target_statement,
        top_k = topK,
        max_results = maxResults,
        candidate_limit = candidateLimit
      )
      rec_response_target <- acp_try("/flows/phenotype_recommendation", body, "target_recommendation")
      write_json(rec_response_target, recs_target_path)
    }
  } else if (file.exists(recs_target_path)) {
    rec_response_target <- read_json(recs_target_path)
    used_cached_recs_target <- TRUE
  } else {
    do_target_recs <- TRUE
    message("No cached target recommendations found; rerunning target recommendations.")
    body <- list(
      study_intent = target_statement,
      top_k = topK,
      max_results = maxResults,
      candidate_limit = candidateLimit
    )
    rec_response_target <- acp_try("/flows/phenotype_recommendation", body, "target_recommendation_resume")
    write_json(rec_response_target, recs_target_path)
  }

  recs_core_target <- rec_response_target$recommendations %||% rec_response_target
  recommendations_target <- recs_core_target$phenotype_recommendations %||% list()
  if (length(recommendations_target) == 0) stop("No target phenotype recommendations returned.")

  cat("\n== Target Phenotype Recommendations ==\n")
  for (i in seq_along(recommendations_target)) {
    rec <- recommendations_target[[i]]
    cat(sprintf("%d. %s (ID %s)\n", i, rec$cohortName %||% "<unknown>", rec$cohortId %||% "?"))
    if (!is.null(rec$justification)) cat(sprintf("   %s\n", rec$justification))
  }

  if (interactive) {
    ok_any <- prompt_yesno("Are any of these acceptable for the target?", default = TRUE)
    if (!ok_any) {
      widen <- prompt_yesno("Widen candidate pool and try again?", default = TRUE)
      if (widen) {
        message("Generating additional recommendations (next window)...")
        used_window2_target <- TRUE
        body <- list(
          study_intent = target_statement,
          top_k = topK,
          max_results = maxResults,
          candidate_limit = candidateLimit,
          candidate_offset = candidateLimit
        )
        rec_response_target <- acp_try("/flows/phenotype_recommendation", body, "target_recommendation_window2")
        recs_target_path <- file.path(output_dir, "recommendations_target_window2.json")
        write_json(rec_response_target, recs_target_path)

        recs_core_target <- rec_response_target$recommendations %||% rec_response_target
        recommendations_target <- recs_core_target$phenotype_recommendations %||% list()
        cat("\n== Target Phenotype Recommendations (window 2) ==\n")
        for (i in seq_along(recommendations_target)) {
          rec <- recommendations_target[[i]]
          cat(sprintf("%d. %s (ID %s)\n", i, rec$cohortName %||% "<unknown>", rec$cohortId %||% "?"))
          if (!is.null(rec$justification)) cat(sprintf("   %s\n", rec$justification))
        }
        ok_any <- prompt_yesno("Are any of these acceptable?", default = TRUE)
      }
      if (!ok_any) {
        message("Generating advisory guidance (this may take a moment)...")
        advice <- acp_try("/flows/phenotype_recommendation_advice", list(study_intent = studyIntent), "target_advice_call")
        used_advice_target <- TRUE
        advice_core <- advice$advice %||% advice
        cat("\n== Advisory guidance ==\n")
        cat(advice_core$advice %||% "", "\n")
        if (length(advice_core$next_steps %||% list()) > 0) {
          cat("Next steps:\n")
          for (step in advice_core$next_steps) cat(sprintf("  - %s\n", step))
        }
        if (length(advice_core$questions %||% list()) > 0) {
          cat("Questions to clarify:\n")
          for (q in advice_core$questions) cat(sprintf("  - %s\n", q))
        }
        mark_checkpoint("target_advice", list(recommendations_path = recs_target_path))
        cat("\nHint: rerun with resume=TRUE after updating phenotypes to continue.\n")
        stop("Stopping after target advice. Resume with resume=TRUE once phenotypes are updated.")
      }
    }
  }

  if (interactive) {
    if (!prompt_yesno("Continue to target cohort selection?", default = TRUE)) {
      return(invisible(list(output_dir = output_dir, recommendations = recs_target_path)))
    }
    cat("\n== Step 3: Select target cohorts ==\n")
  }

  selected_ids_target <- NULL
  if (interactive) {
    labels <- vapply(seq_along(recommendations_target), function(i) {
      rec <- recommendations_target[[i]]
      sprintf("%s (ID %s)", rec$cohortName %||% "<unknown>", rec$cohortId %||% "?")
    }, character(1))
    picks <- utils::select.list(labels, multiple = FALSE, title = "Select target phenotype")
    if (nzchar(picks)) {
      idx <- which(labels == picks)[1]
      selected_ids_target <- recommendations_target[[idx]]$cohortId
    }
  } else {
    selected_ids_target <- recommendations_target[[1]]$cohortId
  }
  selected_ids_target <- as.integer(selected_ids_target)
  if (length(selected_ids_target) == 0) stop("No target cohort selected.")

  use_mapping <- FALSE
  if (interactive) {
    use_mapping <- prompt_yesno("Map cohort IDs to a new range (avoid collisions)?", default = TRUE)
  }
  cohort_id_base <- NA_integer_
  next_id <- NA_integer_
  if (use_mapping) {
    cohort_id_base <- sample(10000:50000, 1)
    if (interactive) {
      msg <- sprintf("Enter cohort ID base (10000-50000) or press Enter to use %s: ", cohort_id_base)
      inp <- trimws(readline(msg))
      if (nzchar(inp)) cohort_id_base <- as.integer(inp)
    }
    next_id <- cohort_id_base
  }

  map_ids <- function(ids) {
    if (!use_mapping) return(ids)
    new <- seq(next_id, length.out = length(ids))
    next_id <<- max(new) + 1
    new
  }

  new_ids_target <- map_ids(selected_ids_target)

  copy_cohort_json_multi(selected_ids_target, new_ids_target, c(selected_target_dir, selected_dir), index_def_dir)

  do_target_improvements <- TRUE
  if (interactive) {
    do_target_improvements <- prompt_yesno("Continue to target phenotype improvements?", default = TRUE)
    if (do_target_improvements) {
      cat("\n== Step 4: Target phenotype improvements ==\n")
    }
  }

  improvements_target_path <- file.path(output_dir, "improvements_target.json")
  imp_response_target <- list()
  improvements_applied <- FALSE
  used_cached_improvements_target <- FALSE
  if (isTRUE(do_target_improvements)) {
    if (maybe_use_cache(improvements_target_path, "target improvements")) {
      imp_response_target <- read_json(improvements_target_path)
      used_cached_improvements_target <- TRUE
      if (interactive) {
        cat(sprintf("\nLoaded cached target improvements from %s\n", improvements_target_path))
      }
    } else {
      cohort_obj <- read_json(file.path(selected_target_dir, sprintf("%s.json", new_ids_target)))
      cohort_obj$id <- new_ids_target
      body <- list(
        protocol_text = studyIntent,
        cohorts = list(cohort_obj)
      )
      message(sprintf("Calling ACP flow: phenotype_improvements (target cohort %s)", new_ids_target))
      resp <- acp_try("/flows/phenotype_improvements", body, "target_improvements")
      imp_response_target[[as.character(new_ids_target)]] <- resp
      write_json(imp_response_target, improvements_target_path)
    }

    if (interactive) {
      for (cid in names(imp_response_target)) {
        resp <- imp_response_target[[cid]]
        core <- resp$full_result %||% resp
        items <- core$phenotype_improvements %||% list()
        cat(sprintf("\n== Improvements for target cohort %s ==\n", cid))
        for (item in items) {
          cat(sprintf("- %s\n", item$summary %||% "(no summary)"))
          if (!is.null(item$actions)) {
            for (act in item$actions) {
              cat(sprintf("  action: %s %s\n", act$type %||% "set", act$path %||% ""))
            }
          }
        }
        if (length(items) == 0) {
          cat("  No improvements returned for this cohort.\n")
          next
        }
        if (prompt_yesno(sprintf("Apply improvements for target cohort %s now?", cid), default = FALSE)) {
          cohort_path <- file.path(selected_target_dir, sprintf("%s.json", cid))
          cohort_obj <- read_json(cohort_path)
          for (item in items) {
            if (is.null(item$actions)) next
            for (act in item$actions) {
              cohort_obj <- apply_action(cohort_obj, act)
            }
          }
          ensure_dir(patched_target_dir)
          ensure_dir(patched_dir)
          out_path <- file.path(patched_target_dir, sprintf("%s.json", cid))
          write_json(cohort_obj, out_path)
          file.copy(out_path, file.path(patched_dir, sprintf("%s.json", cid)), overwrite = TRUE)
          improvements_applied <- TRUE
          cat(sprintf("Patched target cohort saved: %s\n", out_path))
        }
      }
    }
    if (!isTRUE(interactive) && isTRUE(autoApplyImprovements)) {
      for (cid in names(imp_response_target)) {
        resp <- imp_response_target[[cid]]
        core <- resp$full_result %||% resp
        items <- core$phenotype_improvements %||% list()
        if (length(items) == 0) next
        cohort_path <- file.path(selected_target_dir, sprintf("%s.json", cid))
        cohort_obj <- read_json(cohort_path)
        for (item in items) {
          if (is.null(item$actions)) next
          for (act in item$actions) {
            cohort_obj <- apply_action(cohort_obj, act)
          }
        }
        ensure_dir(patched_target_dir)
        ensure_dir(patched_dir)
        out_path <- file.path(patched_target_dir, sprintf("%s.json", cid))
        write_json(cohort_obj, out_path)
        file.copy(out_path, file.path(patched_dir, sprintf("%s.json", cid)), overwrite = TRUE)
        improvements_applied <- TRUE
      }
    }
  }

  do_outcome_recs <- !isTRUE(resume) || !has_checkpoint("outcome_advice")
  if (interactive && !do_outcome_recs) {
    cat("\n== Step 5: Outcome phenotype recommendations (resumed) ==\n")
  }
  if (do_outcome_recs) {
    if (interactive) {
      cat("\n== Step 5: Outcome phenotype recommendations ==\n")
    }
    if (maybe_use_cache(recs_outcome_path, "outcome recommendations")) {
      rec_response_outcome <- read_json(recs_outcome_path)
      used_cached_recs_outcome <- TRUE
    } else {
      message("Calling ACP flow: phenotype_recommendation (outcome)")
      body <- list(
        study_intent = outcome_statement,
        top_k = topK,
        max_results = maxResults,
        candidate_limit = candidateLimit
      )
      rec_response_outcome <- acp_try("/flows/phenotype_recommendation", body, "outcome_recommendation")
      write_json(rec_response_outcome, recs_outcome_path)
    }
  } else if (file.exists(recs_outcome_path)) {
    rec_response_outcome <- read_json(recs_outcome_path)
    used_cached_recs_outcome <- TRUE
  } else {
    do_outcome_recs <- TRUE
    message("No cached outcome recommendations found; rerunning outcome recommendations.")
    body <- list(
      study_intent = outcome_statement,
      top_k = topK,
      max_results = maxResults,
      candidate_limit = candidateLimit
    )
    rec_response_outcome <- acp_try("/flows/phenotype_recommendation", body, "outcome_recommendation_resume")
    write_json(rec_response_outcome, recs_outcome_path)
  }

  recs_core_outcome <- rec_response_outcome$recommendations %||% rec_response_outcome
  recommendations_outcome <- recs_core_outcome$phenotype_recommendations %||% list()
  if (length(recommendations_outcome) == 0) stop("No outcome phenotype recommendations returned.")

  cat("\n== Outcome Phenotype Recommendations ==\n")
  for (i in seq_along(recommendations_outcome)) {
    rec <- recommendations_outcome[[i]]
    cat(sprintf("%d. %s (ID %s)\n", i, rec$cohortName %||% "<unknown>", rec$cohortId %||% "?"))
    if (!is.null(rec$justification)) cat(sprintf("   %s\n", rec$justification))
  }

  if (interactive) {
    ok_any <- prompt_yesno("Are any of these acceptable for the outcomes?", default = TRUE)
    if (!ok_any) {
      widen <- prompt_yesno("Widen candidate pool and try again?", default = TRUE)
      if (widen) {
        message("Generating additional recommendations (next window)...")
        used_window2_outcome <- TRUE
        body <- list(
          study_intent = outcome_statement,
          top_k = topK,
          max_results = maxResults,
          candidate_limit = candidateLimit,
          candidate_offset = candidateLimit
        )
        rec_response_outcome <- acp_try("/flows/phenotype_recommendation", body, "outcome_recommendation_window2")
        recs_outcome_path <- file.path(output_dir, "recommendations_outcome_window2.json")
        write_json(rec_response_outcome, recs_outcome_path)

        recs_core_outcome <- rec_response_outcome$recommendations %||% rec_response_outcome
        recommendations_outcome <- recs_core_outcome$phenotype_recommendations %||% list()
        cat("\n== Outcome Phenotype Recommendations (window 2) ==\n")
        for (i in seq_along(recommendations_outcome)) {
          rec <- recommendations_outcome[[i]]
          cat(sprintf("%d. %s (ID %s)\n", i, rec$cohortName %||% "<unknown>", rec$cohortId %||% "?"))
          if (!is.null(rec$justification)) cat(sprintf("   %s\n", rec$justification))
        }
        ok_any <- prompt_yesno("Are any of these acceptable?", default = TRUE)
      }
      if (!ok_any) {
        message("Generating advisory guidance (this may take a moment)...")
        advice <- acp_try("/flows/phenotype_recommendation_advice", list(study_intent = studyIntent), "outcome_advice_call")
        used_advice_outcome <- TRUE
        advice_core <- advice$advice %||% advice
        cat("\n== Advisory guidance ==\n")
        cat(advice_core$advice %||% "", "\n")
        if (length(advice_core$next_steps %||% list()) > 0) {
          cat("Next steps:\n")
          for (step in advice_core$next_steps) cat(sprintf("  - %s\n", step))
        }
        if (length(advice_core$questions %||% list()) > 0) {
          cat("Questions to clarify:\n")
          for (q in advice_core$questions) cat(sprintf("  - %s\n", q))
        }
        mark_checkpoint("outcome_advice", list(recommendations_path = recs_outcome_path))
        cat("\nHint: rerun with resume=TRUE after updating phenotypes to continue.\n")
        stop("Stopping after outcome advice. Resume with resume=TRUE once phenotypes are updated.")
      }
    }
  }

  if (interactive) {
    if (!prompt_yesno("Continue to outcome cohort selection?", default = TRUE)) {
      return(invisible(list(output_dir = output_dir, recommendations = recs_outcome_path)))
    }
    cat("\n== Step 6: Select outcome cohorts ==\n")
  }

  selected_ids_outcome <- NULL
  if (interactive) {
    labels <- vapply(seq_along(recommendations_outcome), function(i) {
      rec <- recommendations_outcome[[i]]
      sprintf("%s (ID %s)", rec$cohortName %||% "<unknown>", rec$cohortId %||% "?")
    }, character(1))
    picks <- utils::select.list(labels, multiple = TRUE, title = "Select outcome phenotypes")
    selected_ids_outcome <- vapply(picks, function(label) {
      idx <- which(labels == label)[1]
      recommendations_outcome[[idx]]$cohortId
    }, numeric(1))
  } else {
    if (length(recommendations_outcome) >= 2) {
      selected_ids_outcome <- vapply(recommendations_outcome[-1], function(r) r$cohortId, numeric(1))
    } else {
      selected_ids_outcome <- vapply(recommendations_outcome, function(r) r$cohortId, numeric(1))
    }
  }
  selected_ids_outcome <- as.integer(selected_ids_outcome)
  if (length(selected_ids_outcome) == 0) stop("No outcome cohorts selected.")

  new_ids_outcome <- map_ids(selected_ids_outcome)

  for (i in seq_along(new_ids_outcome)) {
    copy_cohort_json_multi(selected_ids_outcome[[i]], new_ids_outcome[[i]], c(selected_outcome_dir, selected_dir), index_def_dir)
  }

  do_outcome_improvements <- TRUE
  if (interactive) {
    do_outcome_improvements <- prompt_yesno("Continue to outcome phenotype improvements?", default = TRUE)
    if (do_outcome_improvements) {
      cat("\n== Step 7: Outcome phenotype improvements ==\n")
    }
  }

  improvements_outcome_path <- file.path(output_dir, "improvements_outcome.json")
  imp_response_outcome <- list()
  used_cached_improvements_outcome <- FALSE
  if (isTRUE(do_outcome_improvements)) {
    if (maybe_use_cache(improvements_outcome_path, "outcome improvements")) {
      imp_response_outcome <- read_json(improvements_outcome_path)
      used_cached_improvements_outcome <- TRUE
      if (interactive) {
        cat(sprintf("\nLoaded cached outcome improvements from %s\n", improvements_outcome_path))
      }
    } else {
      for (i in seq_along(new_ids_outcome)) {
        cid <- new_ids_outcome[[i]]
        cohort_obj <- read_json(file.path(selected_outcome_dir, sprintf("%s.json", cid)))
        cohort_obj$id <- cid
        body <- list(
          protocol_text = studyIntent,
          cohorts = list(cohort_obj)
        )
        message(sprintf("Calling ACP flow: phenotype_improvements (outcome cohort %s)", cid))
        resp <- acp_try("/flows/phenotype_improvements", body, "outcome_improvements")
        imp_response_outcome[[as.character(cid)]] <- resp
      }
      write_json(imp_response_outcome, improvements_outcome_path)
    }

    if (interactive) {
      for (cid in names(imp_response_outcome)) {
        resp <- imp_response_outcome[[cid]]
        core <- resp$full_result %||% resp
        items <- core$phenotype_improvements %||% list()
        cat(sprintf("\n== Improvements for outcome cohort %s ==\n", cid))
        for (item in items) {
          cat(sprintf("- %s\n", item$summary %||% "(no summary)"))
          if (!is.null(item$actions)) {
            for (act in item$actions) {
              cat(sprintf("  action: %s %s\n", act$type %||% "set", act$path %||% ""))
            }
          }
        }
        if (length(items) == 0) {
          cat("  No improvements returned for this cohort.\n")
          next
        }
        if (prompt_yesno(sprintf("Apply improvements for outcome cohort %s now?", cid), default = FALSE)) {
          cohort_path <- file.path(selected_outcome_dir, sprintf("%s.json", cid))
          cohort_obj <- read_json(cohort_path)
          for (item in items) {
            if (is.null(item$actions)) next
            for (act in item$actions) {
              cohort_obj <- apply_action(cohort_obj, act)
            }
          }
          ensure_dir(patched_outcome_dir)
          ensure_dir(patched_dir)
          out_path <- file.path(patched_outcome_dir, sprintf("%s.json", cid))
          write_json(cohort_obj, out_path)
          file.copy(out_path, file.path(patched_dir, sprintf("%s.json", cid)), overwrite = TRUE)
          improvements_applied <- TRUE
          cat(sprintf("Patched outcome cohort saved: %s\n", out_path))
        }
      }
    }
    if (!isTRUE(interactive) && isTRUE(autoApplyImprovements)) {
      for (cid in names(imp_response_outcome)) {
        resp <- imp_response_outcome[[cid]]
        core <- resp$full_result %||% resp
        items <- core$phenotype_improvements %||% list()
        if (length(items) == 0) next
        cohort_path <- file.path(selected_outcome_dir, sprintf("%s.json", cid))
        cohort_obj <- read_json(cohort_path)
        for (item in items) {
          if (is.null(item$actions)) next
          for (act in item$actions) {
            cohort_obj <- apply_action(cohort_obj, act)
          }
        }
        ensure_dir(patched_outcome_dir)
        ensure_dir(patched_dir)
        out_path <- file.path(patched_outcome_dir, sprintf("%s.json", cid))
        write_json(cohort_obj, out_path)
        file.copy(out_path, file.path(patched_dir, sprintf("%s.json", cid)), overwrite = TRUE)
        improvements_applied <- TRUE
      }
    }
  }

  id_map <- data.frame(
    original_id = c(selected_ids_target, selected_ids_outcome),
    cohort_id = c(new_ids_target, new_ids_outcome),
    role = c(rep("target", length(new_ids_target)), rep("outcome", length(new_ids_outcome))),
    stringsAsFactors = FALSE
  )
  write_json(list(mapping = id_map), file.path(output_dir, "cohort_id_map.json"))

  roles_path <- file.path(output_dir, "cohort_roles.json")
  target_ids <- as.integer(new_ids_target)
  outcome_ids <- as.integer(new_ids_outcome)
  write_json(list(targets = target_ids, outcomes = outcome_ids), roles_path)
  if (length(target_ids) == 0) {
    stop("No target cohort assigned. Update cohort_roles.json and re-run.")
  }

  cohort_csv <- file.path(selected_dir, "Cohorts.csv")
  cohort_rows <- list()
  if (length(new_ids_target) > 0) {
    for (i in seq_along(new_ids_target)) {
      cid <- selected_ids_target[[i]]
      new_id <- new_ids_target[[i]]
      rec <- recommendations_target[[which(vapply(recommendations_target, function(r) r$cohortId == cid, logical(1)))]]
      cohort_rows[[length(cohort_rows) + 1]] <- data.frame(
        atlas_id = cid,
        cohort_id = new_id,
        cohort_name = rec$cohortName %||% paste0("Cohort ", new_id),
        logic_description = rec$justification %||% NA_character_,
        generate_stats = TRUE,
        stringsAsFactors = FALSE
      )
    }
  }
  if (length(new_ids_outcome) > 0) {
    for (i in seq_along(new_ids_outcome)) {
      cid <- selected_ids_outcome[[i]]
      new_id <- new_ids_outcome[[i]]
      rec <- recommendations_outcome[[which(vapply(recommendations_outcome, function(r) r$cohortId == cid, logical(1)))]]
      cohort_rows[[length(cohort_rows) + 1]] <- data.frame(
        atlas_id = cid,
        cohort_id = new_id,
        cohort_name = rec$cohortName %||% paste0("Cohort ", new_id),
        logic_description = rec$justification %||% NA_character_,
        generate_stats = TRUE,
        stringsAsFactors = FALSE
      )
    }
  }
  cohort_df <- do.call(rbind, cohort_rows)
  write.csv(cohort_df, cohort_csv, row.names = FALSE)


  state <- list(
    study_intent = studyIntent,
    target_statement = target_statement,
    outcome_statement = outcome_statement,
    output_dir = output_dir,
    selected_dir = selected_dir,
    patched_dir = patched_dir,
    selected_target_dir = selected_target_dir,
    selected_outcome_dir = selected_outcome_dir,
    patched_target_dir = patched_target_dir,
    patched_outcome_dir = patched_outcome_dir,
    keeper_dir = keeper_dir,
    analysis_settings_dir = analysis_settings_dir,
    index_def_dir = index_def_dir,
    intent_split_path = intent_split_path,
    recommendations_target_path = recs_target_path,
    recommendations_outcome_path = recs_outcome_path,
    improvements_target_path = improvements_target_path,
    improvements_outcome_path = improvements_outcome_path,
    cohort_csv = cohort_csv,
    cohort_id_map = id_map,
    cohort_id_base = cohort_id_base,
    cohort_roles_path = roles_path,
    target_ids = target_ids,
    outcome_ids = outcome_ids,
    resume_enabled = resume,
    checkpoint_target_advice = has_checkpoint("target_advice"),
    checkpoint_outcome_advice = has_checkpoint("outcome_advice"),
    used_cached_recommendations_target = used_cached_recs_target,
    used_cached_recommendations_outcome = used_cached_recs_outcome,
    used_cached_improvements_target = used_cached_improvements_target,
    used_cached_improvements_outcome = used_cached_improvements_outcome,
    used_window2_target = used_window2_target,
    used_window2_outcome = used_window2_outcome,
    used_advisory_flow_target = used_advice_target,
    used_advisory_flow_outcome = used_advice_outcome,
    improvements_applied = improvements_applied
  )
  state_path <- file.path(output_dir, "study_agent_state.json")
  write_json(state, state_path)

  # ---- Generate scripts ----
  if (interactive) {
    cat("\n== Step 8: Generate scripts ==\n")
  }
  write_lines <- function(path, lines) {
    writeLines(lines, con = path, useBytes = TRUE)
  }

  script_header <- c(
    "# Generated by OHDSIAssistant::runStrategusIncidenceShell",
    "# Edit values as needed and run in order.",
    if (improvements_applied) "# NOTE: improvements were already applied in the shell run; this script is a portable record."
    else "# NOTE: improvements not applied yet; see 02_apply_improvements.R.",
    ""
  )

  # 01 - select
  script_01 <- c(
    script_header,
    "`%||%` <- function(x, y) if (is.null(x)) y else x",
    "copy_cohort_json <- function(source_id, dest_id, dest_dirs, index_def_dir) {",
    "  src <- file.path(index_def_dir, sprintf('%s.json', source_id))",
    "  if (!file.exists(src)) stop('Cohort JSON not found: ', src)",
    "  for (dest_dir in dest_dirs) {",
    "    dir.create(dest_dir, recursive = TRUE, showWarnings = FALSE)",
    "    dest <- file.path(dest_dir, sprintf('%s.json', dest_id))",
    "    file.copy(src, dest, overwrite = TRUE)",
    "  }",
    "}",
    sprintf("base_dir <- '%s'", base_dir),
    "output_dir <- file.path(base_dir, 'outputs')",
    sprintf("index_def_dir <- '%s'", index_def_dir),
    "selected_dir <- file.path(base_dir, 'selected-cohorts')",
    "selected_target_dir <- file.path(base_dir, 'selected-target-cohorts')",
    "selected_outcome_dir <- file.path(base_dir, 'selected-outcome-cohorts')",
    "dir.create(selected_dir, recursive = TRUE, showWarnings = FALSE)",
    "dir.create(selected_target_dir, recursive = TRUE, showWarnings = FALSE)",
    "dir.create(selected_outcome_dir, recursive = TRUE, showWarnings = FALSE)",
    "recs_target <- jsonlite::fromJSON(file.path(output_dir, 'recommendations_target.json'), simplifyVector = FALSE)",
    "recs_outcome <- jsonlite::fromJSON(file.path(output_dir, 'recommendations_outcome.json'), simplifyVector = FALSE)",
    "items_target <- (recs_target$recommendations %||% recs_target)$phenotype_recommendations %||% list()",
    "items_outcome <- (recs_outcome$recommendations %||% recs_outcome)$phenotype_recommendations %||% list()",
    "labels_target <- vapply(seq_along(items_target), function(i) sprintf('%s (ID %s)', items_target[[i]]$cohortName %||% '<unknown>', items_target[[i]]$cohortId %||% '?'), character(1))",
    "labels_outcome <- vapply(seq_along(items_outcome), function(i) sprintf('%s (ID %s)', items_outcome[[i]]$cohortName %||% '<unknown>', items_outcome[[i]]$cohortId %||% '?'), character(1))",
    "target_pick <- utils::select.list(labels_target, multiple = FALSE, title = 'Select target phenotype')",
    "target_ids <- if (nzchar(target_pick)) items_target[[which(labels_target == target_pick)[1]]]$cohortId else integer(0)",
    "outcome_picks <- utils::select.list(labels_outcome, multiple = TRUE, title = 'Select outcome phenotypes')",
    "outcome_ids <- vapply(outcome_picks, function(label) items_outcome[[which(labels_outcome == label)[1]]]$cohortId, numeric(1))",
    "if (length(target_ids) == 0) stop('No target cohort selected.')",
    "if (length(outcome_ids) == 0) stop('No outcome cohorts selected.')",
    "resp <- tolower(trimws(readline('Map cohort IDs to a new range (avoid collisions)? [Y/n]: ')))",
    "use_mapping <- !(resp %in% c('n', 'no'))",
    "cohort_id_base <- NA_integer_",
    "next_id <- NA_integer_",
    "if (use_mapping) {",
    "  cohort_id_base <- sample(10000:50000, 1)",
    "  inp <- trimws(readline(sprintf('Enter cohort ID base (10000-50000) or press Enter to use %s: ', cohort_id_base)))",
    "  if (nzchar(inp)) cohort_id_base <- as.integer(inp)",
    "  next_id <- cohort_id_base",
    "}",
    "map_ids <- function(ids) {",
    "  if (!use_mapping) return(ids)",
    "  new <- seq(next_id, length.out = length(ids))",
    "  next_id <<- max(new) + 1",
    "  new",
    "}",
    "new_ids_target <- map_ids(target_ids)",
    "new_ids_outcome <- map_ids(outcome_ids)",
    "for (i in seq_along(target_ids)) copy_cohort_json(target_ids[[i]], new_ids_target[[i]], c(selected_target_dir, selected_dir), index_def_dir)",
    "for (i in seq_along(outcome_ids)) copy_cohort_json(outcome_ids[[i]], new_ids_outcome[[i]], c(selected_outcome_dir, selected_dir), index_def_dir)",
    "id_map <- data.frame(",
    "  original_id = c(target_ids, outcome_ids),",
    "  cohort_id = c(new_ids_target, new_ids_outcome),",
    "  role = c(rep('target', length(new_ids_target)), rep('outcome', length(new_ids_outcome))),",
    "  stringsAsFactors = FALSE",
    ")",
    "jsonlite::write_json(list(mapping = id_map), file.path(output_dir, 'cohort_id_map.json'), pretty = TRUE, auto_unbox = TRUE)",
    "jsonlite::write_json(list(targets = new_ids_target, outcomes = new_ids_outcome), file.path(output_dir, 'cohort_roles.json'), pretty = TRUE, auto_unbox = TRUE)",
    "cohort_rows <- list()",
    "for (i in seq_along(new_ids_target)) {",
    "  cid <- target_ids[[i]]",
    "  new_id <- new_ids_target[[i]]",
    "  rec <- items_target[[which(vapply(items_target, function(r) r$cohortId == cid, logical(1)))[1]]]",
    "  cohort_rows[[length(cohort_rows) + 1]] <- data.frame(atlas_id = cid, cohort_id = new_id, cohort_name = rec$cohortName %||% paste0('Cohort ', new_id), logic_description = rec$justification %||% NA_character_, generate_stats = TRUE, stringsAsFactors = FALSE)",
    "}",
    "for (i in seq_along(new_ids_outcome)) {",
    "  cid <- outcome_ids[[i]]",
    "  new_id <- new_ids_outcome[[i]]",
    "  rec <- items_outcome[[which(vapply(items_outcome, function(r) r$cohortId == cid, logical(1)))[1]]]",
    "  cohort_rows[[length(cohort_rows) + 1]] <- data.frame(atlas_id = cid, cohort_id = new_id, cohort_name = rec$cohortName %||% paste0('Cohort ', new_id), logic_description = rec$justification %||% NA_character_, generate_stats = TRUE, stringsAsFactors = FALSE)",
    "}",
    "cohort_df <- do.call(rbind, cohort_rows)",
    "write.csv(cohort_df, file.path(selected_dir, 'Cohorts.csv'), row.names = FALSE)",
    ""
  )
  write_lines(file.path(scripts_dir, "01_recommend_and_select.R"), script_01)

  # 02 - apply improvements
  script_02 <- c(
    script_header,
    "`%||%` <- function(x, y) if (is.null(x)) y else x",
    "apply_action <- function(obj, action) {",
    "  path <- action$path %||% ''",
    "  value <- action$value",
    "  if (!nzchar(path)) return(obj)",
    "  segs <- strsplit(path, '/', fixed = TRUE)[[1]]",
    "  segs <- segs[segs != '']",
    "  set_in <- function(x, segs, value) {",
    "    if (length(segs) == 0) return(value)",
    "    seg <- segs[[1]]",
    "    name <- seg",
    "    idx <- NA_integer_",
    "    if (grepl('\\\\[\\\\d+\\\\]$', seg)) {",
    "      name <- sub('\\\\[\\\\d+\\\\]$', '', seg)",
    "      idx <- as.integer(sub('^.*\\\\[(\\\\d+)\\\\]$', '\\\\1', seg))",
    "    }",
    "    if (name != '') {",
    "      if (is.null(x[[name]])) x[[name]] <- list()",
    "      if (length(segs) == 1) {",
    "        if (!is.na(idx)) {",
    "          if (length(x[[name]]) < idx) while (length(x[[name]]) < idx) x[[name]][[length(x[[name]]) + 1]] <- NULL",
    "          x[[name]][[idx]] <- value",
    "        } else {",
    "          x[[name]] <- value",
    "        }",
    "        return(x)",
    "      }",
    "      if (!is.na(idx)) {",
    "        if (length(x[[name]]) < idx) while (length(x[[name]]) < idx) x[[name]][[length(x[[name]]) + 1]] <- list()",
    "        x[[name]][[idx]] <- set_in(x[[name]][[idx]], segs[-1], value)",
    "      } else {",
    "        x[[name]] <- set_in(x[[name]], segs[-1], value)",
    "      }",
    "      return(x)",
    "    }",
    "    idx <- suppressWarnings(as.integer(seg))",
    "    if (is.na(idx)) return(x)",
    "    if (idx == 0) idx <- 1",
    "    if (length(x) < idx) while (length(x) < idx) x[[length(x) + 1]] <- list()",
    "    if (length(segs) == 1) { x[[idx]] <- value; return(x) }",
    "    x[[idx]] <- set_in(x[[idx]], segs[-1], value)",
    "    x",
    "  }",
    "  set_in(obj, segs, value)",
    "}",
    sprintf("base_dir <- '%s'", base_dir),
    "output_dir <- file.path(base_dir, 'outputs')",
    "selected_dir <- file.path(base_dir, 'selected-cohorts')",
    "selected_target_dir <- file.path(base_dir, 'selected-target-cohorts')",
    "selected_outcome_dir <- file.path(base_dir, 'selected-outcome-cohorts')",
    "patched_dir <- file.path(base_dir, 'patched-cohorts')",
    "patched_target_dir <- file.path(base_dir, 'patched-target-cohorts')",
    "patched_outcome_dir <- file.path(base_dir, 'patched-outcome-cohorts')",
    "dir.create(patched_dir, recursive = TRUE, showWarnings = FALSE)",
    "dir.create(patched_target_dir, recursive = TRUE, showWarnings = FALSE)",
    "dir.create(patched_outcome_dir, recursive = TRUE, showWarnings = FALSE)",
    "improvements_target_path <- file.path(output_dir, 'improvements_target.json')",
    "improvements_outcome_path <- file.path(output_dir, 'improvements_outcome.json')",
    "improvements_target <- if (file.exists(improvements_target_path)) jsonlite::fromJSON(improvements_target_path, simplifyVector = FALSE) else list()",
    "improvements_outcome <- if (file.exists(improvements_outcome_path)) jsonlite::fromJSON(improvements_outcome_path, simplifyVector = FALSE) else list()",
    "apply_for_role <- function(improvements, selected_role_dir, patched_role_dir) {",
    "  for (cid in names(improvements)) {",
    "    resp <- improvements[[cid]]",
    "    core <- resp$full_result %||% resp",
    "    items <- core$phenotype_improvements %||% list()",
    "    if (length(items) == 0) next",
    "    cohort_path <- file.path(selected_role_dir, sprintf('%s.json', cid))",
    "    cohort_obj <- jsonlite::fromJSON(cohort_path, simplifyVector = FALSE)",
    "    for (item in items) {",
    "      if (is.null(item$actions)) next",
    "      for (act in item$actions) cohort_obj <- apply_action(cohort_obj, act)",
    "    }",
    "    out_path <- file.path(patched_role_dir, sprintf('%s.json', cid))",
    "    jsonlite::write_json(cohort_obj, out_path, pretty = TRUE, auto_unbox = TRUE)",
    "    file.copy(out_path, file.path(patched_dir, sprintf('%s.json', cid)), overwrite = TRUE)",
    "  }",
    "}",
    "apply_for_role(improvements_target, selected_target_dir, patched_target_dir)",
    "apply_for_role(improvements_outcome, selected_outcome_dir, patched_outcome_dir)",
    ""
  )
  write_lines(file.path(scripts_dir, "02_apply_improvements.R"), script_02)

  # 03 - generate cohorts
  script_03 <- c(
    script_header,
    "library(Strategus)",
    "library(CohortGenerator)",
    "library(DatabaseConnector)",
    "library(dplyr)",
    "library(CirceR)",
    "library(SqlRender)",
    "",
    "# loads the OHDSI StudyAssistant since it is not yet an installed package",
    "if (!requireNamespace('OHDSIAssistant', quietly = TRUE)) {",
    "  if (requireNamespace('devtools', quietly = TRUE)) {",
    "    devtools::load_all('OHDSI-Study-Agent/R/OHDSIAssistant')",
    "  } else {",
    "    source('OHDSI-Study-Agent/R/OHDSIAssistant/R/zzz.R')",
    "  }",
    "}",
    "library(OHDSIAssistant)",
    "library(jsonlite)",
    "library(ParallelLogger)",
    "`%||%` <- function(x, y) if (is.null(x)) y else x",
    "",
    sprintf("base_dir <- '%s'", base_dir),
    "output_dir <- file.path(base_dir, 'outputs')",
    "selected_dir <- file.path(base_dir, 'selected-cohorts')",
    "patched_dir <- file.path(base_dir, 'patched-cohorts')",
    "cohort_csv <- file.path(selected_dir, 'Cohorts.csv')",
    "cohort_json_dir <- if (length(list.files(patched_dir, pattern = '\\\\.(json)$')) > 0) patched_dir else selected_dir",
    "sql_dir <- file.path(selected_dir, 'sql')",
    "dir.create(sql_dir, recursive = TRUE, showWarnings = FALSE)",
    "",
    "connectionDetails <- OHDSIAssistant::createStrategusConnectionDetails(path='<FILL IN>')",
    "dbms <- connectionDetails$dbms %||% 'postgresql'",
    "exec <- OHDSIAssistant::createStrategusExecutionSettings()",
    "executionSettings_cohorts <- exec$executionSettings",
    "cdmDatabaseSchema <- exec$cdmDatabaseSchema",
    "workDatabaseSchema <- exec$workDatabaseSchema",
    "resultsDatabaseSchema <- exec$resultsDatabaseSchema",
    "vocabularyDatabaseSchema <- exec$vocabularyDatabaseSchema",
    "cohortTable <- exec$cohortTable",
    "cohortIdFieldName <- exec$cohortIdFieldName",
    "dir.create(exec$workFolder, recursive = TRUE, showWarnings = FALSE)",
    "dir.create(exec$resultsFolder, recursive = TRUE, showWarnings = FALSE)",
    "",
    "cohort_settings <- read.csv(cohort_csv, stringsAsFactors = FALSE)",
    "if (nrow(cohort_settings) > 0) {",
    "  id_col <- if ('cohort_id' %in% names(cohort_settings)) 'cohort_id' else 'cohortId'",
    "  for (i in seq_len(nrow(cohort_settings))) {",
    "    cohort_id <- cohort_settings[[id_col]][i]",
    "    sql_path <- file.path(sql_dir, sprintf('%s.sql', cohort_id))",
    "    if (!file.exists(sql_path)) {",
    "      json_path <- file.path(cohort_json_dir, sprintf('%s.json', cohort_id))",
    "      if (!file.exists(json_path)) stop('Missing cohort JSON: ', json_path)",
    "      json_text <- readChar(json_path, nchars = file.info(json_path)$size, useBytes = TRUE)",
    "      cohort_expression <- CirceR::cohortExpressionFromJson(json_text)",
    "      generateOptions <- CirceR::createGenerateOptions(",
    "        cohortIdFieldName = cohortIdFieldName,",
    "        cdmSchema = cdmDatabaseSchema,",
    "        targetTable = paste0(workDatabaseSchema, '.', cohortTable),",
    "        resultSchema = resultsDatabaseSchema,",
    "        vocabularySchema = vocabularyDatabaseSchema,",
    "        generateStats = TRUE",
    "      )",
    "      sql <- CirceR::buildCohortQuery(cohort_expression, generateOptions)",
    "      sql <- SqlRender::render(sql)",
    "      sql <- SqlRender::translate(sql, targetDialect = dbms)",
    "      writeLines(sql, sql_path, useBytes = TRUE)",
    "    }",
    "  }",
    "}",
    "",
    "cohortDefinitionSet <- CohortGenerator::getCohortDefinitionSet(",
    "  settingsFileName = cohort_csv,",
    "  jsonFolder = cohort_json_dir,",
    "  sqlFolder = sql_dir",
    ")",
    "",
    "cgModule <- CohortGeneratorModule$new()",
    "cohortDefinitionSharedResource <- cgModule$createCohortSharedResourceSpecifications(",
    "  cohortDefinitionSet = cohortDefinitionSet",
    ")",
    "cohortGeneratorModuleSpecifications <- cgModule$createModuleSpecifications(generateStats = TRUE)",
    "",
    "analysisSpecifications <- createEmptyAnalysisSpecifications() %>%",
    "  addSharedResources(cohortDefinitionSharedResource) %>%",
    "  addModuleSpecifications(cohortGeneratorModuleSpecifications)",
    "",
    "execute(",
    "   analysisSpecifications = analysisSpecifications,",
    "   executionSettings = executionSettings_cohorts,",
    "   connectionDetails = connectionDetails",
    ")",
    ""
  )
  write_lines(file.path(scripts_dir, "03_generate_cohorts.R"), script_03)

  # 04 - Keeper review
  script_04 <- c(
    script_header,
    "library(Keeper)",
    "library(jsonlite)",
    "library(DatabaseConnector)",
    "",
    "# loads the OHDSI StudyAssistant since it is not yet an installed package",
    "if (!requireNamespace('OHDSIAssistant', quietly = TRUE)) {",
    "  if (requireNamespace('devtools', quietly = TRUE)) {",
    "    devtools::load_all('OHDSI-Study-Agent/R/OHDSIAssistant')",
    "  } else {",
    "    source('OHDSI-Study-Agent/R/OHDSIAssistant/R/zzz.R')",
    "  }",
    "}",
    "library(OHDSIAssistant)",
    "`%||%` <- function(x, y) if (is.null(x)) y else x",
    "",
    sprintf("base_dir <- '%s'", base_dir),
    "output_dir <- file.path(base_dir, 'outputs')",
    "keeper_dir <- file.path(base_dir, 'keeper-case-review')",
    "dir.create(keeper_dir, recursive = TRUE, showWarnings = FALSE)",
    "id_map <- jsonlite::fromJSON(file.path(output_dir, 'cohort_id_map.json'))$mapping",
    "connectionDetails <- OHDSIAssistant::createStrategusConnectionDetails(path='<FILL IN>')",
    "",
    "exec <- OHDSIAssistant::createStrategusExecutionSettings()",
    "# TODO: fill in databaseId (used by Keeper for labeling outputs)",
    "databaseId <- '<FILL IN>'",
    "cdmDatabaseSchema <- exec$cdmDatabaseSchema",
    "cohortDatabaseSchema <- exec$workDatabaseSchema",
    "cohortTable <- exec$cohortTable",
    "",
    "for (cid in id_map$cohort_id) {",
    "  keeper <- createKeeper(",
    "    connectionDetails = connectionDetails,",
    "    databaseId = databaseId,",
    "    cdmDatabaseSchema = cdmDatabaseSchema,",
    "    cohortDatabaseSchema = cohortDatabaseSchema,",
    "    cohortTable = cohortTable,",
    "    cohortDefinitionId = cid,",
    "    cohortName = paste('Cohort', cid),",
    "    sampleSize = 100,",
    "    assignNewId = TRUE,",
    "    useAncestor = TRUE,",
    "    doi = c(4202064, 192671, 2108878, 2108900, 2002608),",
    "    symptoms = c(4103703, 443530, 4245614, 28779),",
    "    comorbidities = c(81893, 201606, 313217, 318800, 432585, 4027663, 4180790, 4212540,
                         40481531, 42535737, 46271022),",
    "    drugs = c(904453, 906780, 923645, 929887, 948078, 953076, 961047, 985247, 992956,
               997276, 1102917, 1113648, 1115008, 1118045, 1118084, 1124300, 1126128,
               1136980, 1146810, 1150345, 1153928, 1177480, 1178663, 1185922, 1195492,
               1236607, 1303425, 1313200, 1353766, 1507835, 1522957, 1721543, 1746940,
               1777806, 19044727, 19119253, 36863425),",
    "    diagnosticProcedures = c(4087381, 4143985, 4294382, 42872565, 45888171, 46257627),",
    "    measurements = c(3000905, 3000963, 3003458, 3012471, 3016251, 3018677, 3020416,
                      3022217, 3023314, 3024929, 3034426),",
    "    alternativeDiagnosis = c(24966, 76725, 195562, 316457, 318800, 4096682),",
    "    treatmentProcedures = c(0),",
    "    complications = c(132797, 196152, 439777, 4192647)",
    "  )",
    "  out_path <- file.path(keeper_dir, sprintf('%s.csv', cid))",
    "  write.csv(keeper, out_path, row.names = FALSE)",
    "}",
    "# Optional: if ACP is available, use phenotype_validation_review on rows from keeper_dir.",
    "# Uncomment to enable:",
    " if (requireNamespace('OHDSIAssistant', quietly = TRUE) || 'OHDSIAssistant' %in% loadedNamespaces()) {",
    "   OHDSIAssistant::acp_connect('http://127.0.0.1:8765')",
    "   roles <- jsonlite::fromJSON(file.path(output_dir, 'cohort_roles.json'), simplifyVector = TRUE)",
    "   intent <- jsonlite::fromJSON(file.path(output_dir, 'intent_split.json'), simplifyVector = TRUE)",
    "   cohort_type <- utils::select.list(c('target', 'outcome'), title = 'Keeper review for which cohort type?')",
    "   if (!nzchar(cohort_type)) stop('No cohort type selected.')",
    "   get_intent_field <- function(obj, field) {",
    "     if (!is.null(obj$intent_split) && !is.null(obj$intent_split[[field]])) return(obj$intent_split[[field]])",
    "     obj[[field]]",
    "   }",
    "   default_disease <- if (cohort_type == 'target') get_intent_field(intent, 'target_statement') else get_intent_field(intent, 'outcome_statement')",
    "   disease_name <- readline(sprintf('Disease name [%s]: ', default_disease))",
    "   if (!nzchar(trimws(disease_name))) disease_name <- default_disease",
    "   sample_n <- as.integer(readline('How many cases per cohort to review? [5]: '))",
    "   if (is.na(sample_n) || sample_n <= 0) sample_n <- 5",
    "   random_pick <- tolower(trimws(readline('Randomly sample cases? [Y/n]: ')))",
    "   random_pick <- !(random_pick %in% c('n', 'no'))",
    "   write_output <- tolower(trimws(readline('Write LLM review rows to file? [Y/n]: ')))",
    "   write_output <- !(write_output %in% c('n', 'no'))",
    "   cohort_ids <- if (cohort_type == 'target') roles$targets else roles$outcomes",
    "   for (cid in cohort_ids) {",
    "     keeper_path <- file.path(keeper_dir, sprintf('%s.csv', cid))",
    "     keeper_rows <- read.csv(keeper_path, stringsAsFactors = FALSE)",
    "     if (nrow(keeper_rows) == 0) next",
    "     n <- min(sample_n, nrow(keeper_rows))",
    "     idx <- if (random_pick) sample(seq_len(nrow(keeper_rows)), n) else seq_len(n)",
    "     selected <- keeper_rows[idx, , drop = FALSE]",
    "     results <- list()",
    "     for (i in seq_len(nrow(selected))) {",
    "       row_payload <- as.list(selected[i, , drop = FALSE])",
    "       row_payload <- lapply(row_payload, function(x) if (length(x) == 0) NA else x)",
    "       resp <- OHDSIAssistant:::`.acp_post`(",
    "         '/flows/phenotype_validation_review',",
    "         list(keeper_row = row_payload, disease_name = disease_name)",
    "       )",
    "       if (!is.null(resp$status) && resp$status == 'error') {",
    "         out <- c(row_payload, list(label = NA, rationale = NA, acp_error = resp$error %||% 'acp_error'))",
    "         results[[length(results) + 1]] <- as.data.frame(out, stringsAsFactors = FALSE, check.names = FALSE)",
    "         next",
    "       }",
    "       label <- resp$label",
    "       rationale <- resp$rationale",
    "       if (is.null(label) && !is.null(resp$full_result$label)) label <- resp$full_result$label",
    "       if (is.null(rationale) && !is.null(resp$full_result$rationale)) rationale <- resp$full_result$rationale",
    "       if (is.null(label) && !is.null(resp$result$label)) label <- resp$result$label",
    "       if (is.null(rationale) && !is.null(resp$result$rationale)) rationale <- resp$result$rationale",
    "       if (is.null(label)) label <- NA",
    "       if (is.null(rationale)) rationale <- NA",
    "       out <- c(row_payload, list(label = label, rationale = rationale))",
    "       results[[length(results) + 1]] <- as.data.frame(out, stringsAsFactors = FALSE, check.names = FALSE)",
    "     }",
    "     if (length(results) > 0) {",
    "       out_df <- do.call(rbind, results)",
    "       if (write_output) {",
    "         out_path <- file.path(keeper_dir, sprintf('%s_llm_review.csv', cid))",
    "         write.csv(out_df, out_path, row.names = FALSE)",
    "       }",
    "       print(out_df)",
    "     }",
    "   }",
    " }",
    ""
  )
  write_lines(file.path(scripts_dir, "04_keeper_review.R"), script_04)

  # 05 - diagnostics
  script_05 <- c(
    script_header,
    "library(Strategus)",
    "library(CohortDiagnostics)",
    "library(CohortGenerator)",
    "library(DatabaseConnector)",
    "library(dplyr)",
    "",
    "# loads the OHDSI StudyAssistant since it is not yet an installed package",
    "if (!requireNamespace('OHDSIAssistant', quietly = TRUE)) {",
    "  if (requireNamespace('devtools', quietly = TRUE)) {",
    "    devtools::load_all('OHDSI-Study-Agent/R/OHDSIAssistant')",
    "  } else {",
    "    source('OHDSI-Study-Agent/R/OHDSIAssistant/R/zzz.R')",
    "  }",
    "}",
    "library(OHDSIAssistant)",
    "library(jsonlite)",
    "library(ParallelLogger)",
    "`%||%` <- function(x, y) if (is.null(x)) y else x",
    "",
    sprintf("base_dir <- '%s'", base_dir),
    "output_dir <- file.path(base_dir, 'outputs')",
    "selected_dir <- file.path(base_dir, 'selected-cohorts')",
    "patched_dir <- file.path(base_dir, 'patched-cohorts')",
    "cohort_csv <- file.path(selected_dir, 'Cohorts.csv')",
    "cohort_json_dir <- if (length(list.files(patched_dir, pattern = '\\\\.(json)$')) > 0) patched_dir else selected_dir",
    "sql_dir <- file.path(selected_dir, 'sql')",
    "dir.create(sql_dir, recursive = TRUE, showWarnings = FALSE)",
    "",
    "connectionDetails <- OHDSIAssistant::createStrategusConnectionDetails(path='<FILL IN>')",
    "exec <- OHDSIAssistant::createStrategusExecutionSettings(path='<FILL IN>')",
    "executionSettings_diagnostics <- exec$executionSettings",
    "",
    "cohortDefinitionSet <- CohortGenerator::getCohortDefinitionSet(",
    "  settingsFileName = cohort_csv,",
    "  jsonFolder = cohort_json_dir,",
    "  sqlFolder = sql_dir",
    ")",
    "",
    "cgModule <- CohortGeneratorModule$new()",
    "cohortDefinitionSharedResource <- cgModule$createCohortSharedResourceSpecifications(",
    "  cohortDefinitionSet = cohortDefinitionSet",
    ")",
    "",
    "cdModule <- CohortDiagnosticsModule$new()",
    "cohortDiagnosticsModuleSpecifications <- cdModule$createModuleSpecifications(",
    "  runInclusionStatistics = TRUE,",
    "  runIncludedSourceConcepts = TRUE,",
    "  runOrphanConcepts = TRUE,",
    "  runTimeSeries = FALSE,",
    "  runVisitContext = TRUE,",
    "  runBreakdownIndexEvents = TRUE,",
    "  runIncidenceRate = TRUE,",
    "  runCohortRelationship = TRUE,",
    "  runTemporalCohortCharacterization = TRUE",
    ")",
    "analysisSpecifications <- createEmptyAnalysisSpecifications() %>%",
    "  addSharedResources(cohortDefinitionSharedResource) %>%",
    "  addModuleSpecifications(cohortDiagnosticsModuleSpecifications)",
    "",
    " execute(",
    "   analysisSpecifications = analysisSpecifications,",
    "   executionSettings = executionSettings_diagnostics,",
    "   connectionDetails = connectionDetails",
    " )",
    ""
  )
  write_lines(file.path(scripts_dir, "05_diagnostics.R"), script_05)

  # 06 - incidence spec
  script_06 <- c(
    script_header,
    "library(Strategus)",
    "library(CohortGenerator)",
    "library(CohortIncidence)",
    "library(DatabaseConnector)",
    "library(dplyr)",
    "",
    "# loads the OHDSI StudyAssistant since it is not yet an installed package",
    "if (!requireNamespace('OHDSIAssistant', quietly = TRUE)) {",
    "  if (requireNamespace('devtools', quietly = TRUE)) {",
    "    devtools::load_all('OHDSI-Study-Agent/R/OHDSIAssistant')",
    "  } else {",
    "    source('OHDSI-Study-Agent/R/OHDSIAssistant/R/zzz.R')",
    "  }",
    "}",
    "library(OHDSIAssistant)",
    "library(jsonlite)",
    "library(ParallelLogger)",
    "`%||%` <- function(x, y) if (is.null(x)) y else x",
    "",
    sprintf("base_dir <- '%s'", base_dir),
    "output_dir <- file.path(base_dir, 'outputs')",
    "analysis_settings_dir <- file.path(base_dir, 'analysis-settings')",
    "dir.create(analysis_settings_dir, recursive = TRUE, showWarnings = FALSE)",
    "selected_dir <- file.path(base_dir, 'selected-cohorts')",
    "patched_dir <- file.path(base_dir, 'patched-cohorts')",
    "cohort_csv <- file.path(selected_dir, 'Cohorts.csv')",
    "cohort_json_dir <- if (length(list.files(patched_dir, pattern = '\\\\.(json)$')) > 0) patched_dir else selected_dir",
    "sql_dir <- file.path(selected_dir, 'sql')",
    "dir.create(sql_dir, recursive = TRUE, showWarnings = FALSE)",
    "",
    "connectionDetails <- OHDSIAssistant::createStrategusConnectionDetails(path='<FILL IN>')",
    "exec <- OHDSIAssistant::createStrategusExecutionSettings(path='<FILL IN>')",
    "executionSettings_incidence <- exec$executionSettings",
    "",
    "cohortDefinitionSet <- CohortGenerator::getCohortDefinitionSet(",
    "  settingsFileName = cohort_csv,",
    "  jsonFolder = cohort_json_dir,",
    "  sqlFolder = sql_dir",
    ")",
    "",
    "roles <- jsonlite::fromJSON(file.path(output_dir, 'cohort_roles.json'), simplifyVector = TRUE)",
    "target_ids <- as.integer(roles$targets %||% integer(0))",
    "outcome_ids <- as.integer(roles$outcomes %||% integer(0))",
    "if (length(target_ids) == 0) stop('No target cohorts defined in cohort_roles.json')",
    "if (length(outcome_ids) == 0) stop('No outcome cohorts defined in cohort_roles.json')",
    "cgModule <- CohortGeneratorModule$new()",
    "cohortDefinitionSharedResource <- cgModule$createCohortSharedResourceSpecifications(",
    "  cohortDefinitionSet = cohortDefinitionSet",
    ")",
    "targets <- lapply(target_ids, function(id) {",
    "  row <- cohortDefinitionSet[cohortDefinitionSet$cohortId == id, ]",
    "  CohortIncidence::createCohortRef(id = id, name = row$cohortName[1])",
    "})",
    "outcomes <- lapply(outcome_ids, function(id) {",
    "  row <- cohortDefinitionSet[cohortDefinitionSet$cohortId == id, ]",
    "  CohortIncidence::createOutcomeDef(id = id, name = row$cohortName[1])",
    "})",
    "",
    "tars <- list(",
    "  CohortIncidence::createTimeAtRiskDef(id = 1, startWith = 'start', endWith = 'end'),",
    "  CohortIncidence::createTimeAtRiskDef(id = 2, startWith = 'start', endWith = 'start', endOffset = 365)",
    ")",
    "",
    "analysis1 <- CohortIncidence::createIncidenceAnalysis(",
    "  targets = sapply(targets, function(x) x$id),",
    "  outcomes = sapply(outcomes, function(x) x$id),",
    "  tars = c(1, 2)",
    ")",
    "",
    "irDesign <- CohortIncidence::createIncidenceDesign(",
    "  targetDefs = targets,",
    "  outcomeDefs = outcomes,",
    "  tars = tars,",
    "  analysisList = list(analysis1),",
    "  strataSettings = CohortIncidence::createStrataSettings(byYear = TRUE, byGender = TRUE)",
    ")",
    "",
    "ciModule <- CohortIncidenceModule$new()",
    "cohortIncidenceModuleSpecifications <- ciModule$createModuleSpecifications(",
    "  irDesign = irDesign$toList()",
    ")",
    "",
    "analysisSpecifications <- createEmptyAnalysisSpecifications() %>%",
    "  addSharedResources(cohortDefinitionSharedResource) %>%",
    "  addModuleSpecifications(cohortIncidenceModuleSpecifications)",
    "analysis_spec_path <- file.path(analysis_settings_dir, 'analysisSpecification.json')",
    "ParallelLogger::saveSettingsToJson(analysisSpecifications, analysis_spec_path)",
    "",
    " execute(",
    "   analysisSpecifications = analysisSpecifications,",
    "   executionSettings = executionSettings_incidence,",
    "   connectionDetails = connectionDetails",
    " )",
    ""
  )
  write_lines(file.path(scripts_dir, "06_incidence_spec.R"), script_06)

  if (interactive) {
    cat("\n== Session Summary ==\n")
    cat("Target cohort statement:\n")
    cat(sprintf("  %s\n", target_statement))
    cat("Outcome cohort statement:\n")
    cat(sprintf("  %s\n", outcome_statement))
    cat("Target cohorts:\n")
    for (i in seq_along(new_ids_target)) {
      rec <- recommendations_target[[which(vapply(recommendations_target, function(r) r$cohortId == selected_ids_target[[i]], logical(1)))]]
      cat(sprintf("  - %s (atlas %s -> cohort %s)\n", rec$cohortName %||% "<unknown>", selected_ids_target[[i]], new_ids_target[[i]]))
    }
    cat("Outcome cohorts:\n")
    for (i in seq_along(new_ids_outcome)) {
      rec <- recommendations_outcome[[which(vapply(recommendations_outcome, function(r) r$cohortId == selected_ids_outcome[[i]], logical(1)))]]
      cat(sprintf("  - %s (atlas %s -> cohort %s)\n", rec$cohortName %||% "<unknown>", selected_ids_outcome[[i]], new_ids_outcome[[i]]))
    }
    cat("JSON outputs:\n")
    cat(sprintf("  - Selected target cohorts: %s\n", selected_target_dir))
    cat(sprintf("  - Selected outcome cohorts: %s\n", selected_outcome_dir))
    cat(sprintf("  - Selected cohorts (combined): %s\n", selected_dir))
    if (improvements_applied) {
      cat(sprintf("  - Patched target cohorts: %s\n", patched_target_dir))
      cat(sprintf("  - Patched outcome cohorts: %s\n", patched_outcome_dir))
      cat(sprintf("  - Patched cohorts (combined): %s\n", patched_dir))
    } else {
      cat("  - Patched cohorts: (not applied)\n")
    }
    cat("Scripts written:\n")
    cat(sprintf("  - %s\n", scripts_dir))
    cat("Recommended run order (if you want to re-run outside the shell):\n")
    cat("  1) Rscript scripts/03_generate_cohorts.R\n")
    cat("  2) Rscript scripts/04_keeper_review.R\n")
    cat("  3) Rscript scripts/05_diagnostics.R\n")
    cat("  4) Rscript scripts/06_incidence_spec.R\n")
    cat("Notes:\n")
    if (improvements_applied) {
      cat("  - Improvements were already applied in this session; scripts are a portable record.\n")
    } else {
      cat("  - Improvements were not applied; see scripts/02_apply_improvements.R if desired.\n")
    }
    cat(sprintf("Session state saved to %s\n", state_path))
  }
  message("Study agent shell complete. Scripts written to: ", scripts_dir)
  invisible(list(
    output_dir = output_dir,
    scripts_dir = scripts_dir,
    intent_split = intent_split_path,
    recommendations_target = recs_target_path,
    recommendations_outcome = recs_outcome_path,
    improvements_target = improvements_target_path,
    improvements_outcome = improvements_outcome_path,
    cohort_csv = cohort_csv
  ))
}
