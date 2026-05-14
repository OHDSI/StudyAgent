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
                                      candidateLimit = 5,
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

  normalize_dialogue_step <- .studyAgentSlashNormalizeIncidenceDialogueStep

  dialogue_step_label <- .studyAgentSlashIncidenceDialogueStepLabel
  compact_dialogue_context <- .studyAgentSlashCompactWorkflowDialogueContext

  dialogue_acp_client <- new.env(parent = emptyenv())
  dialogue_acp_client$client <- NULL
  build_workflow_stage_context <- function(studyIntent, dialogue_state) {
    .studyAgentSlashBuildIncidenceWorkflowStageContext(
      study_intent = studyIntent,
      dialogue_state = dialogue_state,
      interactive = interactive
    )
  }
  acp_timeout_seconds <- function(default = 180) {
    timeout_seconds <- as.numeric(Sys.getenv("ACP_TIMEOUT", as.character(default)))
    if (is.na(timeout_seconds) || timeout_seconds <= 0) timeout_seconds <- default
    timeout_seconds
  }

  acp_client_is_ready <- function(client) {
    .studyAgentSlashAcpIsConnected(client)
  }

  create_acp_client <- function(url, token = NULL, check = TRUE) {
    .studyAgentSlashCreateAcpClient(url = url, token = token, check = check)
  }

  ensure_workflow_dialogue_client <- function(url) {
    if (acp_client_is_ready(dialogue_acp_client$client)) return(TRUE)
    if (is.null(url) || !nzchar(trimws(url))) return(FALSE)
    tryCatch({
      dialogue_acp_client$client <- create_acp_client(url = url, check = TRUE)
      TRUE
    }, error = function(e) {
      FALSE
    })
  }

  call_shell_acp_flow <- function(flow_name, body, url = acpUrl) {
    if (!acp_client_is_ready(dialogue_acp_client$client)) {
      if (!ensure_workflow_dialogue_client(url)) stop("ACP bridge unavailable.")
    }
    .studyAgentSlashCallAcpFlow(dialogue_acp_client$client, flow_name = flow_name, body = body)
  }

  dialogue_session <- .studyAgentSlashNewWorkflowDialogueSession(
    interactive = interactive,
    study_intent_getter = function() studyIntent,
    build_stage_context = build_workflow_stage_context,
    call_dialogue = function(stage_context, message) {
      if (!ensure_workflow_dialogue_client(acpUrl)) {
        stop("ACP bridge unavailable. Connect ACP before using /ohdsi.")
      }
      message("Calling ACP flow: workflow_context_dialogue")
      .studyAgentSlashWorkflowContextDialogue(dialogue_acp_client$client, stage_context, message)
    },
    empty_question_message = "Enter a question after /ohdsi. Example: /ohdsi why are these candidates weak here?"
  )
  dialogue_state <- dialogue_session$state
  set_dialogue_context <- dialogue_session$set_context
  readline_with_dialogue <- dialogue_session$readline
  is_back_signal <- function(value) inherits(value, "workflow_navigation_signal") && identical(value$action %||% "", "back")
  readline_with_navigation <- function(prompt) readline_with_dialogue(prompt, allow_back = TRUE)

  prompt_yesno <- function(prompt, default = TRUE) {
    if (!isTRUE(interactive)) return(default)
    suffix <- if (default) "[Y/n]" else "[y/N]"
    resp <- tolower(trimws(readline_with_dialogue(sprintf("%s %s ", prompt, suffix))))
    if (resp == "") return(default)
    if (resp %in% c("y", "yes")) return(TRUE)
    if (resp %in% c("n", "no")) return(FALSE)
    default
  }

  prompt_yesno_navigation <- function(prompt, default = TRUE) {
    if (!isTRUE(interactive)) return(default)
    suffix <- if (default) "[Y/n]" else "[y/N]"
    resp <- readline_with_navigation(sprintf("%s %s ", prompt, suffix))
    if (is_back_signal(resp)) return(resp)
    resp <- tolower(trimws(as.character(resp %||% "")))
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

  default_time_at_risk_settings <- function() {
    list(
      time_at_risk_defs = list(
        list(id = 1L, name = "During exposure", startWith = "start", startOffset = 0L, endWith = "end", endOffset = 0L),
        list(id = 2L, name = "365 days after cohort start", startWith = "start", startOffset = 0L, endWith = "start", endOffset = 365L)
      ),
      analysis_tar_ids = c(1L, 2L),
      strata_settings = list(byYear = TRUE, byGender = TRUE, byAge = FALSE, ageBreaks = c(18L, 45L, 65L))
    )
  }

  normalize_time_at_risk_settings <- function(settings) {
    settings <- settings %||% list()
    defs <- settings$time_at_risk_defs %||% settings$tars %||% list()
    if (!is.list(defs) || length(defs) == 0) defs <- default_time_at_risk_settings()$time_at_risk_defs

    normalized_defs <- lapply(seq_along(defs), function(i) {
      item <- defs[[i]] %||% list()
      id <- suppressWarnings(as.integer(item$id %||% i))
      if (is.na(id) || id <= 0L) stop(sprintf("time_at_risk_defs[%s].id must be a positive integer.", i))
      start_with <- tolower(trimws(as.character(item$startWith %||% "start")))
      end_with <- tolower(trimws(as.character(item$endWith %||% "end")))
      if (!start_with %in% c("start", "end")) stop(sprintf("time_at_risk_defs[%s].startWith must be 'start' or 'end'.", i))
      if (!end_with %in% c("start", "end")) stop(sprintf("time_at_risk_defs[%s].endWith must be 'start' or 'end'.", i))
      start_offset <- suppressWarnings(as.integer(item$startOffset %||% 0L))
      end_offset <- suppressWarnings(as.integer(item$endOffset %||% 0L))
      if (is.na(start_offset)) stop(sprintf("time_at_risk_defs[%s].startOffset must be an integer.", i))
      if (is.na(end_offset)) stop(sprintf("time_at_risk_defs[%s].endOffset must be an integer.", i))
      name <- trimws(as.character(item$name %||% sprintf("TAR %s", id)))
      if (!nzchar(name)) name <- sprintf("TAR %s", id)
      list(
        id = as.integer(id),
        name = name,
        startWith = start_with,
        startOffset = as.integer(start_offset),
        endWith = end_with,
        endOffset = as.integer(end_offset)
      )
    })

    ids <- vapply(normalized_defs, function(item) as.integer(item$id), integer(1))
    if (length(unique(ids)) != length(ids)) stop("time_at_risk_defs ids must be unique.")

    analysis_tar_ids <- suppressWarnings(as.integer(unlist(settings$analysis_tar_ids %||% ids, use.names = FALSE)))
    analysis_tar_ids <- unique(analysis_tar_ids[!is.na(analysis_tar_ids)])
    if (length(analysis_tar_ids) == 0) analysis_tar_ids <- ids
    if (!all(analysis_tar_ids %in% ids)) stop("analysis_tar_ids must reference defined time_at_risk_defs ids.")

    strata <- settings$strata_settings %||% list()
    by_year <- isTRUE(strata$byYear %||% TRUE)
    by_gender <- isTRUE(strata$byGender %||% TRUE)
    by_age <- isTRUE(strata$byAge %||% FALSE)
    age_breaks <- suppressWarnings(as.integer(unlist(strata$ageBreaks %||% c(18L, 45L, 65L), use.names = FALSE)))
    age_breaks <- unique(age_breaks[!is.na(age_breaks)])
    age_breaks <- sort(age_breaks)
    if (isTRUE(by_age) && length(age_breaks) == 0) stop("strata_settings.ageBreaks must contain at least one integer when byAge is TRUE.")

    list(
      time_at_risk_defs = normalized_defs,
      analysis_tar_ids = as.integer(analysis_tar_ids),
      strata_settings = list(
        byYear = by_year,
        byGender = by_gender,
        byAge = by_age,
        ageBreaks = as.integer(age_breaks)
      )
    )
  }

  print_time_at_risk_settings <- function(settings) {
    settings <- normalize_time_at_risk_settings(settings)
    cat("\nCurrent time-at-risk settings\n")
    for (item in settings$time_at_risk_defs) {
      cat(sprintf(
        "  - TAR %s [%s]: start=%s %+d days, end=%s %+d days\n",
        item$id,
        item$name,
        item$startWith,
        item$startOffset,
        item$endWith,
        item$endOffset
      ))
    }
    cat(sprintf("  Analysis TAR ids: %s\n", paste(settings$analysis_tar_ids, collapse = ", ")))
    strata <- settings$strata_settings
    cat(sprintf(
      "  Strata: byYear=%s, byGender=%s, byAge=%s%s\n",
      strata$byYear,
      strata$byGender,
      strata$byAge,
      if (isTRUE(strata$byAge) && length(strata$ageBreaks) > 0) paste0(", ageBreaks=", paste(strata$ageBreaks, collapse = ",")) else ""
    ))
  }

  collect_time_at_risk_settings <- function(seed_settings,
                                            study_intent,
                                            target_statement,
                                            outcome_statement,
                                            target_ids,
                                            outcome_ids) {
    settings <- normalize_time_at_risk_settings(seed_settings)

    set_dialogue_context(
      "time_at_risk_configuration",
      context = list(
        study_intent = study_intent,
        target_statement = target_statement,
        outcome_statement = outcome_statement,
        selected_target_ids = as.list(target_ids %||% list()),
        selected_outcome_ids = as.list(outcome_ids %||% list()),
        time_at_risk_settings = settings,
        denominator_guidance = "Denominators depend on cohort entry logic, TAR definitions, and chosen strata settings."
      )
    )

    if (isTRUE(interactive)) cat("\n== Step 8: Configure time at risk ==\n")
    print_time_at_risk_settings(settings)
    if (!isTRUE(interactive)) return(settings)
    use_current_settings <- prompt_yesno_navigation("Use these time-at-risk and strata settings?", default = TRUE)
    if (is_back_signal(use_current_settings)) return(use_current_settings)
    if (isTRUE(use_current_settings)) return(settings)

    prompt_integer_value <- function(prompt, current, min_value = NULL) {
      repeat {
        entered <- trimws(readline_with_dialogue(sprintf("%s [%s]: ", prompt, current)))
        if (!nzchar(entered)) return(as.integer(current))
        parsed <- suppressWarnings(as.integer(entered))
        if (!is.na(parsed) && (is.null(min_value) || parsed >= min_value)) return(as.integer(parsed))
        cat("Please enter a valid integer.\n")
      }
    }

    prompt_choice_value <- function(prompt, current, choices) {
      repeat {
        entered <- tolower(trimws(readline_with_dialogue(sprintf("%s [%s]: ", prompt, current))))
        if (!nzchar(entered)) return(current)
        if (entered %in% choices) return(entered)
        cat(sprintf("Please enter one of: %s\n", paste(choices, collapse = ", ")))
      }
    }

    prompt_text_value <- function(prompt, current) {
      entered <- readline_with_dialogue(sprintf("%s [%s]: ", prompt, current))
      if (!nzchar(trimws(entered))) current else trimws(entered)
    }

    tar_count <- prompt_integer_value("Number of time-at-risk definitions", length(settings$time_at_risk_defs), min_value = 1L)
    defs <- vector("list", tar_count)
    for (i in seq_len(tar_count)) {
      current <- settings$time_at_risk_defs[[min(i, length(settings$time_at_risk_defs))]] %||% list(
        id = i,
        name = sprintf("TAR %s", i),
        startWith = "start",
        startOffset = 0L,
        endWith = "end",
        endOffset = 0L
      )
      cat(sprintf("\nTAR %s\n", i))
      defs[[i]] <- list(
        id = prompt_integer_value("  TAR id", current$id, min_value = 1L),
        name = prompt_text_value("  TAR label", current$name %||% sprintf("TAR %s", i)),
        startWith = prompt_choice_value("  startWith (start/end)", current$startWith %||% "start", c("start", "end")),
        startOffset = prompt_integer_value("  startOffset (days)", current$startOffset %||% 0L),
        endWith = prompt_choice_value("  endWith (start/end)", current$endWith %||% "end", c("start", "end")),
        endOffset = prompt_integer_value("  endOffset (days)", current$endOffset %||% 0L)
      )
    }

    default_analysis_ids <- paste(vapply(defs, function(item) as.integer(item$id), integer(1)), collapse = ",")
    analysis_ids_text <- trimws(readline_with_dialogue(sprintf("Analysis TAR ids (comma-separated) [%s]: ", default_analysis_ids)))
    analysis_ids <- if (!nzchar(analysis_ids_text)) {
      suppressWarnings(as.integer(strsplit(default_analysis_ids, ",", fixed = TRUE)[[1]]))
    } else {
      suppressWarnings(as.integer(trimws(strsplit(analysis_ids_text, ",", fixed = TRUE)[[1]])))
    }

    strata_settings <- settings$strata_settings
    by_year <- prompt_yesno("Stratify incidence by calendar year?", default = isTRUE(strata_settings$byYear))
    by_gender <- prompt_yesno("Stratify incidence by gender?", default = isTRUE(strata_settings$byGender))
    by_age <- prompt_yesno("Stratify incidence by age?", default = isTRUE(strata_settings$byAge))
    age_breaks_default <- paste(strata_settings$ageBreaks %||% c(18L, 45L, 65L), collapse = ",")
    age_breaks <- strata_settings$ageBreaks %||% c(18L, 45L, 65L)
    if (isTRUE(by_age)) {
      age_breaks_text <- trimws(readline_with_dialogue(sprintf("Age breaks (comma-separated integers) [%s]: ", age_breaks_default)))
      if (nzchar(age_breaks_text)) {
        age_breaks <- suppressWarnings(as.integer(trimws(strsplit(age_breaks_text, ",", fixed = TRUE)[[1]])))
      }
    }

    settings <- normalize_time_at_risk_settings(list(
      time_at_risk_defs = defs,
      analysis_tar_ids = analysis_ids,
      strata_settings = list(
        byYear = by_year,
        byGender = by_gender,
        byAge = by_age,
        ageBreaks = age_breaks
      )
    ))
    print_time_at_risk_settings(settings)
    settings
  }

  acp_try <- function(path, body, label) {
    repeat {
      resp <- NULL
      err <- NULL
      flow_name <- sub("^/flows/", "", as.character(path))
      resp <- tryCatch(
        call_shell_acp_flow(flow_name, body),
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

  phenotype_definition_path <- function(phenotype_id, index_def_dir) {
    file.path(index_def_dir, sprintf("%s.json", gsub(":", "__", phenotype_id, fixed = TRUE)))
  }

  stop_if_unsupported_selected <- function(phenotype_ids, role_label) {
    unsupported <- phenotype_ids[!grepl("^ohdsi:", phenotype_ids %||% character(0))]
    if (length(unsupported) > 0) {
      stop(
        sprintf(
          paste0(
            "Selected %s phenotype(s) include non-OHDSI ids (%s). ",
            "This demo workflow does not yet support converting non-OHDSI phenotype definitions ",
            "into computable OHDSI cohort definitions. Please re-run and choose an OHDSI phenotype."
          ),
          role_label,
          paste(unique(unsupported), collapse = ", ")
        )
      )
    }
  }

  default_cohort_id_from_source <- function(source_id) {
    source_id <- as.character(source_id %||% "")
    if (!nzchar(source_id)) return(NA_integer_)
    if (grepl("^ohdsi:[0-9]+$", source_id)) {
      return(suppressWarnings(as.integer(sub("^ohdsi:", "", source_id))))
    }
    suppressWarnings(as.integer(source_id))
  }

  default_cohort_ids_from_sources <- function(source_ids, role_label = "selected") {
    source_ids <- as.character(source_ids %||% character(0))
    if (length(source_ids) == 0) return(integer(0))
    derived <- vapply(source_ids, default_cohort_id_from_source, integer(1))
    if (any(is.na(derived))) {
      bad <- source_ids[is.na(derived)]
      stop(sprintf(
        "Could not derive numeric cohort IDs for %s phenotype(s): %s",
        role_label,
        paste(unique(bad), collapse = ", ")
      ))
    }
    as.integer(derived)
  }

  copy_cohort_json_multi <- function(source_id, dest_id, dest_dirs, index_def_dir) {
    src <- phenotype_definition_path(source_id, index_def_dir)
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
    cat("Use /ohdsi for contextual guidance. Type /back at supported stage boundaries to return to the previous step.\n")
  }

  default_intent <- studyIntent %||% "What is the risk of GI bleed in new users of Celecoxib compared to new users of Diclofenac?"
  repeat {
    if (interactive) {
      set_dialogue_context("study_intent", context = list(default_intent = default_intent))
      entered <- readline_with_navigation(sprintf("Study intent [%s]: ", default_intent))
      if (is_back_signal(entered)) {
        cat("Already at the first step\n")
        next
      }
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
    set_dialogue_context("intent_split", context = list(study_intent = studyIntent))
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
      back_to_study_intent <- FALSE
      repeat {
        set_dialogue_context("intent_split", "target", context = list(study_intent = studyIntent, target_statement = target_statement, outcome_statement = outcome_statement))
        inp <- readline_with_navigation(sprintf("Target cohort statement [%s]: ", target_statement))
        if (is_back_signal(inp)) {
          back_to_study_intent <- TRUE
          break
        }
        if (nzchar(trimws(inp))) target_statement <- inp
        set_dialogue_context("intent_split", "outcome", context = list(study_intent = studyIntent, target_statement = target_statement, outcome_statement = outcome_statement))
        inp <- readline_with_navigation(sprintf("Outcome cohort statement [%s]: ", outcome_statement))
        if (is_back_signal(inp)) next
        if (nzchar(trimws(inp))) outcome_statement <- inp
        break
      }
      if (isTRUE(back_to_study_intent)) next
    }
    if (!nzchar(trimws(target_statement))) stop("Missing target cohort statement.")
    if (!nzchar(trimws(outcome_statement))) stop("Missing outcome cohort statement.")
    break
  }

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

  repeat {
  do_target_recs <- !isTRUE(resume) || !has_checkpoint("target_advice")
  if (interactive && !do_target_recs) {
    cat("\n== Step 2: Target phenotype recommendations (resumed) ==\n")
  }
  if (do_target_recs) {
    if (interactive) {
      cat("\n== Step 2: Target phenotype recommendations ==\n")
    }
    set_dialogue_context("target_recommendation", "target", context = list(study_intent = studyIntent, role_statement = target_statement, target_statement = target_statement, outcome_statement = outcome_statement, top_k = topK, max_results = maxResults, candidate_limit = candidateLimit))
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
    cat(sprintf("%d. %s (ID %s)\n", i, rec$phenotype_name %||% "<unknown>", rec$phenotype_id %||% "?"))
    if (!is.null(rec$justification)) cat(sprintf("   %s\n", rec$justification))
  }

  if (interactive) {
    set_dialogue_context("target_recommendation", "target", context = list(study_intent = studyIntent, role_statement = target_statement, target_statement = target_statement, outcome_statement = outcome_statement, top_k = topK, max_results = maxResults, candidate_limit = candidateLimit))
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
          cat(sprintf("%d. %s (ID %s)\n", i, rec$phenotype_name %||% "<unknown>", rec$phenotype_id %||% "?"))
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
    set_dialogue_context("target_selection", "target", context = list(study_intent = studyIntent, role_statement = target_statement, target_statement = target_statement, outcome_statement = outcome_statement))
    if (!prompt_yesno("Continue to target cohort selection?", default = TRUE)) {
      return(invisible(list(output_dir = output_dir, recommendations = recs_target_path)))
    }
    gate <- readline_with_navigation("Press Enter to continue to target cohort selection, or type /back: ")
    if (is_back_signal(gate)) next
    cat("\n== Step 3: Select target cohorts ==\n")
  }

  selected_ids_target <- NULL
  selected_ids_outcome <- character(0)
  if (interactive) {
    labels <- vapply(seq_along(recommendations_target), function(i) {
      rec <- recommendations_target[[i]]
      sprintf("%s (ID %s)", rec$phenotype_name %||% "<unknown>", rec$phenotype_id %||% "?")
    }, character(1))
    picks <- utils::select.list(labels, multiple = FALSE, title = "Select target phenotype")
    if (nzchar(picks)) {
      idx <- which(labels == picks)[1]
      selected_ids_target <- recommendations_target[[idx]]$phenotype_id
    }
  } else {
    selected_ids_target <- recommendations_target[[1]]$phenotype_id
  }
  selected_ids_target <- as.character(selected_ids_target)
  if (length(selected_ids_target) == 0) stop("No target cohort selected.")

  use_mapping <- FALSE
  if (interactive) {
    set_dialogue_context("incidence_design_setup", context = list(study_intent = studyIntent, target_statement = target_statement, outcome_statement = outcome_statement, selected_target_ids = as.list(selected_ids_target %||% list()), selected_outcome_ids = as.list(selected_ids_outcome %||% list())))
    use_mapping <- prompt_yesno("Map cohort IDs to a new range (avoid collisions)?", default = TRUE)
  }
  cohort_id_base <- NA_integer_
  next_id <- NA_integer_
  if (use_mapping) {
    cohort_id_base <- sample(10000:50000, 1)
    if (interactive) {
      msg <- sprintf("Enter cohort ID base (10000-50000) or press Enter to use %s: ", cohort_id_base)
      set_dialogue_context("incidence_design_setup", context = list(study_intent = studyIntent, target_statement = target_statement, outcome_statement = outcome_statement, selected_target_ids = as.list(selected_ids_target %||% list()), selected_outcome_ids = as.list(selected_ids_outcome %||% list()), suggested_cohort_id_base = cohort_id_base))
      inp <- trimws(readline_with_dialogue(msg))
      if (nzchar(inp)) cohort_id_base <- as.integer(inp)
    }
    next_id <- cohort_id_base
  }

  map_ids <- function(ids) {
    if (!use_mapping) return(default_cohort_ids_from_sources(ids, role_label = "selected"))
    new <- seq(next_id, length.out = length(ids))
    next_id <<- max(new) + 1
    new
  }

  extract_phenotype_improvement_items <- function(resp, cohort_label) {
    core <- resp$full_result %||% resp
    if (!is.null(core$error) && nzchar(trimws(as.character(core$error)))) {
      stop(sprintf("ACP returned an error for %s phenotype improvements: %s", cohort_label, core$error))
    }
    core$phenotype_improvements %||% list()
  }

  stop_if_unsupported_selected(selected_ids_target, "target")

  new_ids_target <- map_ids(selected_ids_target)

  copy_cohort_json_multi(selected_ids_target, new_ids_target, c(selected_target_dir, selected_dir), index_def_dir)

  do_target_improvements <- TRUE
  if (interactive) {
    set_dialogue_context("target_improvements", "target", context = list(study_intent = studyIntent, role_statement = target_statement, target_statement = target_statement, selected_target_ids = as.list(selected_ids_target %||% list())))
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
        items <- extract_phenotype_improvement_items(resp, sprintf("target cohort %s", cid))
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
        set_dialogue_context("target_improvements", "target", context = list(study_intent = studyIntent, role_statement = target_statement, target_statement = target_statement, cohort_id = as.integer(cid), selected_target_ids = as.list(selected_ids_target %||% list())))
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
        items <- extract_phenotype_improvement_items(resp, sprintf("target cohort %s", cid))
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


    break
  }

  repeat {
  do_outcome_recs <- !isTRUE(resume) || !has_checkpoint("outcome_advice")
  if (interactive && !do_outcome_recs) {
    cat("\n== Step 5: Outcome phenotype recommendations (resumed) ==\n")
  }
  if (do_outcome_recs) {
    if (interactive) {
      cat("\n== Step 5: Outcome phenotype recommendations ==\n")
    }
    set_dialogue_context("outcome_recommendation", "outcome", context = list(study_intent = studyIntent, role_statement = outcome_statement, target_statement = target_statement, outcome_statement = outcome_statement, top_k = topK, max_results = maxResults, candidate_limit = candidateLimit))
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
    cat(sprintf("%d. %s (ID %s)\n", i, rec$phenotype_name %||% "<unknown>", rec$phenotype_id %||% "?"))
    if (!is.null(rec$justification)) cat(sprintf("   %s\n", rec$justification))
  }

  if (interactive) {
    set_dialogue_context("outcome_recommendation", "outcome", context = list(study_intent = studyIntent, role_statement = outcome_statement, target_statement = target_statement, outcome_statement = outcome_statement, top_k = topK, max_results = maxResults, candidate_limit = candidateLimit))
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
          cat(sprintf("%d. %s (ID %s)\n", i, rec$phenotype_name %||% "<unknown>", rec$phenotype_id %||% "?"))
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
    set_dialogue_context("outcome_selection", "outcome", context = list(study_intent = studyIntent, role_statement = outcome_statement, target_statement = target_statement, outcome_statement = outcome_statement))
    if (!prompt_yesno("Continue to outcome cohort selection?", default = TRUE)) {
      return(invisible(list(output_dir = output_dir, recommendations = recs_outcome_path)))
    }
    gate <- readline_with_navigation("Press Enter to continue to outcome cohort selection, or type /back: ")
    if (is_back_signal(gate)) next
    cat("\n== Step 6: Select outcome cohorts ==\n")
  }

  selected_ids_outcome <- NULL
  if (interactive) {
    labels <- vapply(seq_along(recommendations_outcome), function(i) {
      rec <- recommendations_outcome[[i]]
      sprintf("%s (ID %s)", rec$phenotype_name %||% "<unknown>", rec$phenotype_id %||% "?")
    }, character(1))
    picks <- utils::select.list(labels, multiple = TRUE, title = "Select outcome phenotypes")
    selected_ids_outcome <- vapply(picks, function(label) {
      idx <- which(labels == label)[1]
      recommendations_outcome[[idx]]$phenotype_id %||% NA_character_
    }, character(1))
  } else {
    if (length(recommendations_outcome) >= 2) {
      selected_ids_outcome <- vapply(recommendations_outcome[-1], function(r) r$phenotype_id %||% NA_character_, character(1))
    } else {
      selected_ids_outcome <- vapply(recommendations_outcome, function(r) r$phenotype_id %||% NA_character_, character(1))
    }
  }
  selected_ids_outcome <- as.character(selected_ids_outcome)
  if (length(selected_ids_outcome) == 0) stop("No outcome cohorts selected.")

  stop_if_unsupported_selected(selected_ids_outcome, "outcome")

  new_ids_outcome <- map_ids(selected_ids_outcome)

  for (i in seq_along(new_ids_outcome)) {
    copy_cohort_json_multi(selected_ids_outcome[[i]], new_ids_outcome[[i]], c(selected_outcome_dir, selected_dir), index_def_dir)
  }

  do_outcome_improvements <- TRUE
  if (interactive) {
    set_dialogue_context("outcome_improvements", "outcome", context = list(study_intent = studyIntent, role_statement = outcome_statement, target_statement = target_statement, outcome_statement = outcome_statement, selected_outcome_ids = as.list(selected_ids_outcome %||% list())))
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
        items <- extract_phenotype_improvement_items(resp, sprintf("outcome cohort %s", cid))
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
        set_dialogue_context("outcome_improvements", "outcome", context = list(study_intent = studyIntent, role_statement = outcome_statement, target_statement = target_statement, outcome_statement = outcome_statement, cohort_id = as.integer(cid), selected_outcome_ids = as.list(selected_ids_outcome %||% list())))
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
        items <- extract_phenotype_improvement_items(resp, sprintf("outcome cohort %s", cid))
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


    break
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
      rec <- recommendations_target[[which(vapply(recommendations_target, function(r) r$phenotype_id == cid, logical(1)))]]
      cohort_rows[[length(cohort_rows) + 1]] <- data.frame(
        atlas_id = cid,
        cohort_id = new_id,
        cohort_name = rec$phenotype_name %||% paste0("Cohort ", new_id),
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
      rec <- recommendations_outcome[[which(vapply(recommendations_outcome, function(r) r$phenotype_id == cid, logical(1)))]]
      cohort_rows[[length(cohort_rows) + 1]] <- data.frame(
        atlas_id = cid,
        cohort_id = new_id,
        cohort_name = rec$phenotype_name %||% paste0("Cohort ", new_id),
        logic_description = rec$justification %||% NA_character_,
        generate_stats = TRUE,
        stringsAsFactors = FALSE
      )
    }
  }
  cohort_df <- do.call(rbind, cohort_rows)
  write.csv(cohort_df, cohort_csv, row.names = FALSE)

  time_at_risk_settings_path <- file.path(analysis_settings_dir, "time_at_risk_settings.json")
  seed_time_at_risk_settings <- if (file.exists(time_at_risk_settings_path)) {
    tryCatch(read_json(time_at_risk_settings_path), error = function(e) default_time_at_risk_settings())
  } else {
    default_time_at_risk_settings()
  }
  repeat {
    incidence_time_at_risk <- collect_time_at_risk_settings(
      seed_settings = seed_time_at_risk_settings,
      study_intent = studyIntent,
      target_statement = target_statement,
      outcome_statement = outcome_statement,
      target_ids = target_ids,
      outcome_ids = outcome_ids
    )
    if (is_back_signal(incidence_time_at_risk)) next
    write_json(incidence_time_at_risk, time_at_risk_settings_path)
    break
  }

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
    time_at_risk_settings_path = time_at_risk_settings_path,
    incidence_time_at_risk = incidence_time_at_risk,
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

  seed_strategus_runtime_templates <- function(base_dir) {
    db_details_path <- file.path(base_dir, "strategus-db-details.json")
    execution_settings_path <- file.path(base_dir, "strategus-execution-settings.json")

    if (!file.exists(db_details_path)) {
      write_json(list(
        dbms = "postgresql",
        DB_SERVER = "",
        DB_PORT = "5432",
        DB_USER = "",
        DB_PASS = "",
        DB_DRIVER_PATH = "",
        extraSettings = "sslmode=disable"
      ), db_details_path)
    }

    if (!file.exists(execution_settings_path)) {
      write_json(list(
        cdmDatabaseSchema = "",
        workDatabaseSchema = "",
        resultsDatabaseSchema = "",
        vocabularyDatabaseSchema = "",
        cohortTable = "cohort",
        workFolder = file.path(base_dir, "work"),
        resultsFolder = file.path(base_dir, "results"),
        cohortIdFieldName = "cohort_definition_id",
        maxCores = 4
      ), execution_settings_path)
    }

    list(
      db_details_path = db_details_path,
      execution_settings_path = execution_settings_path
    )
  }

  runtime_template_paths <- seed_strategus_runtime_templates(base_dir)
  db_details_path <- runtime_template_paths$db_details_path
  execution_settings_path <- runtime_template_paths$execution_settings_path
  state$strategus_db_details_path <- db_details_path
  state$strategus_execution_settings_path <- execution_settings_path
  write_json(state, state_path)

  keeper_review_state_path <- file.path(output_dir, "keeper_review_state.json")
  keeper_review_roles <- character(0)
  keeper_acp_timeout_seconds <- as.numeric(Sys.getenv("ACP_TIMEOUT", "300"))
  keeper_candidate_limit <- 5L
  keeper_min_record_count <- NULL
  keeper_sample_size <- 5L
  keeper_review_row_limit <- 5L
  keeper_reuse_generated_artifacts <- TRUE
  keeper_overwrite_approved_concept_sets <- FALSE
  keeper_resume_reviews <- TRUE
  keeper_review_row_selection <- NULL
  keeper_review_ran <- FALSE
  keeper_review_result <- NULL

  if (isTRUE(interactive)) {
    repeat {
      run_keeper_review_now <- prompt_yesno_navigation(paste("Run Keeper review now? (first edit db/execution conf ", db_details_path, ",", execution_settings_path, ") [y/N]"), default = FALSE)
      if (is_back_signal(run_keeper_review_now)) {
        incidence_time_at_risk <- collect_time_at_risk_settings(
          seed_settings = incidence_time_at_risk,
          study_intent = studyIntent,
          target_statement = target_statement,
          outcome_statement = outcome_statement,
          target_ids = target_ids,
          outcome_ids = outcome_ids
        )
        if (!is_back_signal(incidence_time_at_risk)) {
          write_json(incidence_time_at_risk, time_at_risk_settings_path)
          state$incidence_time_at_risk <- incidence_time_at_risk
          write_json(state, state_path)
        }
        next
      }
      if (isTRUE(run_keeper_review_now)) {
        entered_roles <- trimws(readline_with_dialogue("Keeper review roles [outcome]: "))
        keeper_review_roles <- if (!nzchar(entered_roles)) "outcome" else trimws(strsplit(entered_roles, ",", fixed = TRUE)[[1]])
        keeper_review_roles <- keeper_review_roles[nzchar(keeper_review_roles)]
        keeper_review_roles <- intersect(keeper_review_roles, c("outcome", "target"))
        if (!length(keeper_review_roles)) keeper_review_roles <- "outcome"
        keeper_generated_dir <- file.path(base_dir, "keeper-case-review", "concept-sets-generated")
        keeper_approved_dir <- file.path(base_dir, "keeper-case-review", "concept-sets-approved")
        keeper_rows_dir <- file.path(base_dir, "keeper-case-review", "rows")
        keeper_reviews_dir <- file.path(base_dir, "keeper-case-review", "reviews")
        has_keeper_generated_artifacts <- dir.exists(keeper_generated_dir) &&
          length(list.files(keeper_generated_dir, pattern = "\\.json$", recursive = TRUE, full.names = TRUE)) > 0
        has_keeper_approved_artifacts <- dir.exists(keeper_approved_dir) &&
          length(list.files(keeper_approved_dir, pattern = "\\.json$", recursive = TRUE, full.names = TRUE)) > 0
        has_keeper_rows_artifacts <- dir.exists(keeper_rows_dir) &&
          length(list.files(keeper_rows_dir, pattern = "\\.json$", recursive = TRUE, full.names = TRUE)) > 0
        has_keeper_review_artifacts <- dir.exists(keeper_reviews_dir) &&
          length(list.files(keeper_reviews_dir, pattern = "\\.json$", recursive = TRUE, full.names = TRUE)) > 0
        if (has_keeper_generated_artifacts || has_keeper_rows_artifacts) {
          keeper_reuse_generated_artifacts <- prompt_yesno("Reuse existing Keeper generated artifacts?", default = TRUE)
        }
        if (has_keeper_generated_artifacts || has_keeper_approved_artifacts) {
          keeper_overwrite_approved_concept_sets <- prompt_yesno("Replace approved concept sets with current generated output?", default = FALSE)
        }
        if (has_keeper_review_artifacts) {
          keeper_resume_reviews <- prompt_yesno("Resume existing Keeper row reviews?", default = TRUE)
        }
        entered_row_selection <- trimws(readline_with_dialogue("Keeper row selection [default first N or e.g. 1-3,5]: "))
        keeper_review_row_selection <- if (!nzchar(entered_row_selection)) NULL else entered_row_selection

        stage_callback <- function(step, role = "", context = list()) {
          safe_context <- c(
            list(
              study_intent = studyIntent,
              target_statement = target_statement,
              outcome_statement = outcome_statement,
              selected_target_ids = as.list(target_ids),
              selected_outcome_ids = as.list(outcome_ids),
              keeper_review_state_path = keeper_review_state_path,
              acp_timeout_seconds = keeper_acp_timeout_seconds
            ),
            context
          )
          set_dialogue_context(step, role, context = safe_context)
        }

        prompt_keeper_positive_integer <- function(prompt, default) {
          current_default <- suppressWarnings(as.integer(default %||% 1L))
          repeat {
            entered <- trimws(readline_with_dialogue(sprintf("%s [%s]: ", prompt, current_default)))
            value <- if (!nzchar(entered)) current_default else suppressWarnings(as.integer(entered))
            if (!is.na(value) && value >= 1L) return(as.integer(value))
            cat("Please enter an integer >= 1.
")
          }
        }

        prompt_keeper_optional_integer <- function(prompt, default = NULL) {
          repeat {
            suffix <- if (is.null(default)) "optional" else as.character(default)
            entered <- trimws(readline_with_dialogue(sprintf("%s [%s]: ", prompt, suffix)))
            if (!nzchar(entered)) return(default)
            value <- suppressWarnings(as.integer(entered))
            if (!is.na(value) && value >= 1L) return(as.integer(value))
            cat("Please enter an integer >= 1, or press Enter to leave unset.
")
          }
        }

        parse_keeper_review_rows <- function(selection_text, total_rows) {
          total_rows <- suppressWarnings(as.integer(total_rows %||% 0L))
          if (is.na(total_rows) || total_rows <= 0L) return(integer(0))
          entered <- trimws(as.character(selection_text %||% ""))
          if (!nzchar(entered)) return(integer(0))
          parts <- trimws(strsplit(entered, ",", fixed = TRUE)[[1]])
          parsed <- integer(0)
          for (part in parts[nzchar(parts)]) {
            if (grepl("^[0-9]+-[0-9]+$", part)) {
              bounds <- suppressWarnings(as.integer(strsplit(part, "-", fixed = TRUE)[[1]]))
              if (length(bounds) == 2L && !anyNA(bounds)) parsed <- c(parsed, seq.int(min(bounds), max(bounds)))
            } else {
              parsed <- c(parsed, suppressWarnings(as.integer(part)))
            }
          }
          parsed <- parsed[!is.na(parsed)]
          parsed <- parsed[parsed >= 1L & parsed <= total_rows]
          unique(parsed)
        }

        inspect_keeper_review_rows <- function(review_path) {
          if (!file.exists(review_path)) {
            cat(sprintf("Keeper review artifact not found: %s
", review_path))
            return(invisible(NULL))
          }
          payload <- read_json(review_path)
          reviews <- payload$reviews %||% list()
          if (!length(reviews)) {
            cat("No Keeper review rows have been saved yet.
")
            return(invisible(NULL))
          }
          entered <- trimws(readline_with_dialogue("Review row numbers to inspect [Enter=all selected rows, e.g. 1,3 or 1-3]: "))
          indices <- parse_keeper_review_rows(entered, length(reviews))
          if (!length(indices)) indices <- seq_along(reviews)
          for (idx in indices) {
            rec <- reviews[[idx]]
            cat(sprintf("
[Keeper review row %s]
", rec$row_index %||% idx))
            cat(sprintf("Label: %s
", rec$label %||% "<none>"))
            rationale <- trimws(as.character(rec$rationale %||% ""))
            if (nzchar(rationale)) cat(sprintf("Rationale: %s
", rationale))
            err <- trimws(as.character(rec$error %||% ""))
            if (nzchar(err)) cat(sprintf("Error: %s
", err))
          }
          invisible(NULL)
        }

        keeper_stage_gate <- function(step, role = "", context = list()) {
          stage_callback(step, role = role, context = context)
          if (identical(step, "keeper_concept_set_generation_before")) {
            cat(sprintf("
Keeper domain gate: %s / %s
", role, context$domain_key %||% "domain"))
            repeat {
              entered <- tolower(trimws(readline_with_dialogue("Keeper domain options [Enter=continue, s=skip, e=edit settings]: ")))
              if (!nzchar(entered)) return(list(action = "continue"))
              if (entered %in% c("s", "skip")) return(list(action = "skip_domain"))
              if (entered %in% c("e", "edit")) {
                keeper_candidate_limit <<- prompt_keeper_positive_integer("Keeper concept candidate limit", keeper_candidate_limit)
                keeper_min_record_count <<- prompt_keeper_optional_integer("Keeper min record count", keeper_min_record_count)
                return(list(action = "continue", updates = list(candidate_limit = keeper_candidate_limit, min_record_count = keeper_min_record_count)))
              }
              cat("Choose Enter, s, or e.
")
            }
          }
          if (identical(step, "keeper_concept_set_generation_after")) {
            cat(sprintf("
Keeper domain complete: %s / %s
", role, context$domain_key %||% "domain"))
            cat(sprintf("Generated artifact: %s
", context$generated_concept_sets_path %||% "<missing>"))
            repeat {
              entered <- tolower(trimws(readline_with_dialogue("Keeper domain result options [Enter=keep, r=rerun, i=inspect/edit files]: ")))
              if (!nzchar(entered)) return(list(action = "continue"))
              if (entered %in% c("r", "rerun")) return(list(action = "rerun_domain"))
              if (entered %in% c("i", "inspect")) {
                cat(sprintf("Inspect or edit: %s
", context$generated_concept_sets_path %||% "<missing>"))
                readline_with_dialogue("Press Enter when you are ready to keep these domain results: ")
                return(list(action = "continue"))
              }
              cat("Choose Enter, r, or i.
")
            }
          }
          if (identical(step, "keeper_case_review_before")) {
            cat(sprintf("
Keeper case review gate: %s
", role))
            cat(sprintf("Rows available: %s
", context$row_count %||% 0L))
            repeat {
              entered <- tolower(trimws(readline_with_dialogue("Keeper review options [Enter=continue, e=edit review settings, i=inspect row artifacts]: ")))
              if (!nzchar(entered)) return(list(action = "continue"))
              if (entered %in% c("e", "edit")) {
                keeper_review_row_limit <<- prompt_keeper_positive_integer("Keeper review row limit", keeper_review_row_limit)
                updated_selection <- trimws(readline_with_dialogue(sprintf("Keeper row selection [%s]: ", keeper_review_row_selection %||% "default first N")))
                if (nzchar(updated_selection)) keeper_review_row_selection <<- updated_selection
                keeper_resume_reviews <<- prompt_yesno("Resume existing Keeper row reviews?", default = keeper_resume_reviews)
                return(list(action = "continue", updates = list(review_row_limit = keeper_review_row_limit, review_row_selection = keeper_review_row_selection, resume_reviews = keeper_resume_reviews)))
              }
              if (entered %in% c("i", "inspect")) {
                cat(sprintf("Inspect row artifacts:
  JSON: %s
  CSV: %s
", context$rows_path %||% "<missing>", context$rows_csv_path %||% "<missing>"))
                next
              }
              cat("Choose Enter, e, or i.
")
            }
          }
          if (identical(step, "keeper_case_review_after")) {
            cat(sprintf("
Keeper review saved: %s reviewed row(s)
", context$reviewed_row_count %||% 0L))
            repeat {
              entered <- tolower(trimws(readline_with_dialogue("Keeper post-review options [Enter=finish, i=inspect reviewed rows]: ")))
              if (!nzchar(entered)) return(list(action = "continue"))
              if (entered %in% c("i", "inspect")) {
                inspect_keeper_review_rows(context$reviews_path %||% "")
                next
              }
              cat("Choose Enter or i.
")
            }
          }
          list(action = "continue")
        }

        stage_callback(
          "keeper_concept_set_generation_before",
          role = keeper_review_roles[[1]],
          context = list(review_roles = as.list(keeper_review_roles), review_status = "starting")
        )

        keeper_review_result <- tryCatch(
          runKeeperReviewWorkflow(
            base_dir = base_dir,
            execution_settings_path = execution_settings_path,
            cohort_id_map_path = file.path(output_dir, "cohort_id_map.json"),
            cohort_roles_path = roles_path,
            intent_path = intent_split_path,
            acp_timeout_seconds = keeper_acp_timeout_seconds,
            review_roles = keeper_review_roles,
            candidate_limit = keeper_candidate_limit,
            min_record_count = keeper_min_record_count,
            sample_size = keeper_sample_size,
            review_row_limit = keeper_review_row_limit,
            overwrite_approved_concept_sets = keeper_overwrite_approved_concept_sets,
            reuse_generated_concept_sets = keeper_reuse_generated_artifacts,
            reuse_rows = keeper_reuse_generated_artifacts,
            resume_reviews = keeper_resume_reviews,
            review_row_selection = keeper_review_row_selection,
            stage_callback = stage_callback,
            stage_gate = keeper_stage_gate
          ),
          error = function(e) e
        )

        if (inherits(keeper_review_result, "error")) {
          cat(sprintf("Keeper review failed: %s
", conditionMessage(keeper_review_result)))
        } else if (identical(keeper_review_result$status %||% "ok", "error")) {
          error_count <- as.integer(keeper_review_result$error_count %||% 0L)
          cat(sprintf("Keeper review encountered %s ACP error(s).
", error_count))
          if (length(keeper_review_result$errors %||% list())) {
            first_error <- keeper_review_result$errors[[1]]
            cat(sprintf("First ACP error: %s
", first_error$message %||% "unknown ACP error"))
          }
          cat(sprintf("Keeper review state saved to: %s
", keeper_review_state_path))
        } else {
          keeper_review_ran <- TRUE
          cat(sprintf("Keeper review state saved to: %s
", keeper_review_state_path))
        }
        set_dialogue_context("workflow_summary", context = list(study_intent = studyIntent, keeper_review_state_path = keeper_review_state_path))
      }
      break
    }
  }

  state$keeper_review_state_path <- keeper_review_state_path
  state$keeper_review_roles <- as.list(keeper_review_roles)
  state$keeper_acp_timeout_seconds <- as.numeric(keeper_acp_timeout_seconds)
  state$keeper_candidate_limit <- as.integer(keeper_candidate_limit)
  state$keeper_min_record_count <- if (is.null(keeper_min_record_count)) NULL else as.integer(keeper_min_record_count)
  state$keeper_sample_size <- as.integer(keeper_sample_size)
  state$keeper_review_row_limit <- as.integer(keeper_review_row_limit)
  state$keeper_reuse_generated_artifacts <- isTRUE(keeper_reuse_generated_artifacts)
  state$keeper_overwrite_approved_concept_sets <- isTRUE(keeper_overwrite_approved_concept_sets)
  state$keeper_resume_reviews <- isTRUE(keeper_resume_reviews)
  state$keeper_review_row_selection <- keeper_review_row_selection
  state$keeper_review_ran <- isTRUE(keeper_review_ran)
  state$keeper_review_status <- if (inherits(keeper_review_result, "error")) "error" else as.character(keeper_review_result$status %||% if (isTRUE(keeper_review_ran)) "ok" else "not_run")
  state$keeper_review_error_count <- if (inherits(keeper_review_result, "error")) 1L else as.integer(keeper_review_result$error_count %||% 0L)
  write_json(state, state_path)

  # ---- Generate scripts ----
  if (interactive) {
    cat("\n== Step 9: Generate scripts ==\n")
  }
  write_lines <- function(path, lines) {
    writeLines(lines, con = path, useBytes = TRUE)
  }

  script_header <- c(
    "# Generated by the slashOhdsiStrategusAssistant incidence workflow shell",
    "# Edit values as needed and run in order.",
    if (improvements_applied) "# NOTE: improvements were already applied in the shell run; this script is a portable record."
    else "# NOTE: improvements not applied yet; see 02_apply_improvements.R.",
    ""
  )

  # 01 - select
  script_01 <- c(
    script_header,
    "`%||%` <- function(x, y) if (is.null(x)) y else x",
    "phenotype_definition_path <- function(phenotype_id, index_def_dir) {",
    "  file.path(index_def_dir, sprintf('%s.json', gsub(':', '__', phenotype_id, fixed = TRUE)))",
    "}",
    "stop_if_unsupported_selected <- function(phenotype_ids, role_label) {",
    "  unsupported <- phenotype_ids[!grepl('^ohdsi:', phenotype_ids %||% character(0))]",
    "  if (length(unsupported) > 0) stop(sprintf('Selected %s phenotype(s) include non-OHDSI ids (%s). This demo workflow does not yet support converting non-OHDSI phenotype definitions into computable OHDSI cohort definitions. Please re-run and choose an OHDSI phenotype.', role_label, paste(unique(unsupported), collapse = ', ')))",
    "}",
    "copy_cohort_json <- function(source_id, dest_id, dest_dirs, index_def_dir) {",
    "  src <- phenotype_definition_path(source_id, index_def_dir)",
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
    "labels_target <- vapply(seq_along(items_target), function(i) sprintf('%s (ID %s)', items_target[[i]]$phenotype_name %||% '<unknown>', items_target[[i]]$phenotype_id %||% '?'), character(1))",
    "labels_outcome <- vapply(seq_along(items_outcome), function(i) sprintf('%s (ID %s)', items_outcome[[i]]$phenotype_name %||% '<unknown>', items_outcome[[i]]$phenotype_id %||% '?'), character(1))",
    "target_pick <- utils::select.list(labels_target, multiple = FALSE, title = 'Select target phenotype')",
    "target_ids <- if (nzchar(target_pick)) (items_target[[which(labels_target == target_pick)[1]]]$phenotype_id %||% '') else character(0)",
    "outcome_picks <- utils::select.list(labels_outcome, multiple = TRUE, title = 'Select outcome phenotypes')",
    "outcome_ids <- vapply(outcome_picks, function(label) items_outcome[[which(labels_outcome == label)[1]]]$phenotype_id %||% NA_character_, character(1))",
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
    "default_cohort_id <- function(source_id) {",
    "  source_id <- as.character(source_id %||% '')",
    "  if (!nzchar(source_id)) return(NA_integer_)",
    "  if (grepl('^ohdsi:[0-9]+$', source_id)) {",
    "    return(suppressWarnings(as.integer(sub('^ohdsi:', '', source_id))))",
    "  }",
    "  suppressWarnings(as.integer(source_id))",
    "}",
    "default_cohort_ids <- function(ids, role_label = 'selected') {",
    "  ids <- as.character(ids %||% character(0))",
    "  if (length(ids) == 0) return(integer(0))",
    "  derived <- vapply(ids, default_cohort_id, integer(1))",
    "  if (any(is.na(derived))) {",
    "    bad <- ids[is.na(derived)]",
    "    stop(sprintf('Could not derive numeric cohort IDs for %s phenotype(s): %s', role_label, paste(unique(bad), collapse = ', ')))",
    "  }",
    "  as.integer(derived)",
    "}",
    "map_ids <- function(ids) {",
    "  if (!use_mapping) return(default_cohort_ids(ids, role_label = 'selected'))",
    "  new <- seq(next_id, length.out = length(ids))",
    "  next_id <<- max(new) + 1",
    "  new",
    "}",
    "stop_if_unsupported_selected(target_ids, 'target')",
    "new_ids_target <- map_ids(target_ids)",
    "stop_if_unsupported_selected(outcome_ids, 'outcome')",
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
    "  rec <- items_target[[which(vapply(items_target, function(r) r$phenotype_id == cid, logical(1)))[1]]]",
    "  cohort_rows[[length(cohort_rows) + 1]] <- data.frame(atlas_id = cid, cohort_id = new_id, cohort_name = rec$phenotype_name %||% paste0('Cohort ', new_id), logic_description = rec$justification %||% NA_character_, generate_stats = TRUE, stringsAsFactors = FALSE)",
    "}",
    "for (i in seq_along(new_ids_outcome)) {",
    "  cid <- outcome_ids[[i]]",
    "  new_id <- new_ids_outcome[[i]]",
    "  rec <- items_outcome[[which(vapply(items_outcome, function(r) r$phenotype_id == cid, logical(1)))[1]]]",
    "  cohort_rows[[length(cohort_rows) + 1]] <- data.frame(atlas_id = cid, cohort_id = new_id, cohort_name = rec$phenotype_name %||% paste0('Cohort ', new_id), logic_description = rec$justification %||% NA_character_, generate_stats = TRUE, stringsAsFactors = FALSE)",
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
    "    if (!is.null(core$error) && nzchar(trimws(as.character(core$error)))) {",
    "      stop(sprintf('ACP returned an error for phenotype improvements on cohort %s: %s', cid, core$error))",
    "    }",
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
    "# loads the Strategus workflow assistant package when working from the repo",
    "if (!requireNamespace('slashOhdsiStrategusAssistant', quietly = TRUE)) {",
    "  if (requireNamespace('devtools', quietly = TRUE)) {",
    "    devtools::load_all('OHDSI-Study-Agent/R/slashOhdsiStrategusAssistant')",
    "  } else {",
    "    stop('slashOhdsiStrategusAssistant is not installed and devtools::load_all is unavailable.')",
    "  }",
    "}",
    "library(slashOhdsiStrategusAssistant)",
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
    "db_details_path <- file.path(base_dir, 'strategus-db-details.json')",
    "execution_settings_path <- file.path(base_dir, 'strategus-execution-settings.json')",
    "connectionDetails <- slashOhdsiStrategusAssistant::createStrategusConnectionDetails(path = db_details_path)",
    "dbms <- connectionDetails$dbms %||% 'postgresql'",
    "exec <- slashOhdsiStrategusAssistant::createStrategusExecutionSettings(path = execution_settings_path)",
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
    "library(jsonlite)",
    "",
    "# loads the Strategus workflow assistant package when working from the repo",
    "if (!requireNamespace('slashOhdsiStrategusAssistant', quietly = TRUE)) {",
    "  if (requireNamespace('devtools', quietly = TRUE)) {",
    "    devtools::load_all('OHDSI-Study-Agent/R/slashOhdsiStrategusAssistant')",
    "  } else {",
    "    stop('slashOhdsiStrategusAssistant is not installed and devtools::load_all is unavailable.')",
    "  }",
    "}",
    "library(slashOhdsiStrategusAssistant)",
    "",
    sprintf("base_dir <- '%s'", base_dir),
    "output_dir <- file.path(base_dir, 'outputs')",
    "execution_settings_path <- file.path(base_dir, 'strategus-execution-settings.json')",
    "cohort_id_map_path <- file.path(output_dir, 'cohort_id_map.json')",
    "cohort_roles_path <- file.path(output_dir, 'cohort_roles.json')",
    "intent_path <- file.path(output_dir, 'intent_split.json')",
    "",
    "# Edit these defaults as needed before running the ACP-based Keeper workflow.",
    "review_roles <- c('outcome')",
    "domain_keys <- c(",
    "  'doi', 'drugs'", 
    ") # NOTE: you could also add 'alternativeDiagnosis', 'symptoms', 'diagnosticProcedures', 'measurements', 'treatmentProcedures', and 'complications' but need to increase the ACP_TIMOUT env variable 3-5 minutes per domain",
    "candidate_limit <- 5",
    "sample_size <- 5",
    "review_row_limit <- 5",
    "acp_timeout_seconds <- as.numeric(Sys.getenv('ACP_TIMEOUT', '600'))",
    "Sys.setenv(ACP_TIMEOUT = as.character(acp_timeout_seconds))",
    "reuse_generated_concept_sets <- TRUE",
    "overwrite_approved_concept_sets <- FALSE",
    "reuse_rows <- TRUE",
    "resume_reviews <- TRUE",
    "review_row_selection <- NULL  # e.g. '1-3,5'",
    "acp_url <- Sys.getenv('ACP_URL', 'http://127.0.0.1:8765')",
    "",
    "result <- slashOhdsiStrategusAssistant::runKeeperReviewWorkflow(",
    "  base_dir = base_dir,",
    "  execution_settings_path = execution_settings_path,",
    "  cohort_id_map_path = cohort_id_map_path,",
    "  cohort_roles_path = cohort_roles_path,",
    "  intent_path = intent_path,",
    "  acp_url = acp_url,",
    "  acp_timeout_seconds = acp_timeout_seconds,",
    "  review_roles = review_roles,",
    "  domain_keys = domain_keys,  # NOTE: full set of options are as follows but set the ACP_TIMOUT to be > 10 minutes before attempting all of them: doi, alternativeDiagnosis, symptoms, drugs, diagnosticProcedures, measurements, treatmentProcedures, complications",
    "  candidate_limit = candidate_limit,",
    "  sample_size = sample_size,",
    "  review_row_limit = review_row_limit,",
    "  overwrite_approved_concept_sets = overwrite_approved_concept_sets,",
    "  reuse_generated_concept_sets = reuse_generated_concept_sets,",
    "  reuse_rows = reuse_rows,",
    "  resume_reviews = resume_reviews,",
    "  review_row_selection = review_row_selection,",
    "  remove_pii = TRUE",
    ")",
    "keeper_state_path <- file.path(output_dir, 'keeper_review_state.json')",
    "if (identical(result$status %||% 'ok', 'error')) {",
    "  stop(sprintf('Keeper review encountered %s ACP error(s). See %s for details.', as.integer(result$error_count %||% 0L), keeper_state_path))",
    "}",
    "message('Keeper review state saved to: ', keeper_state_path)",
    "print(result)",
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
    "# loads the Strategus workflow assistant package when working from the repo",
    "if (!requireNamespace('slashOhdsiStrategusAssistant', quietly = TRUE)) {",
    "  if (requireNamespace('devtools', quietly = TRUE)) {",
    "    devtools::load_all('OHDSI-Study-Agent/R/slashOhdsiStrategusAssistant')",
    "  } else {",
    "    stop('slashOhdsiStrategusAssistant is not installed and devtools::load_all is unavailable.')",
    "  }",
    "}",
    "library(slashOhdsiStrategusAssistant)",
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
    "db_details_path <- file.path(base_dir, 'strategus-db-details.json')",
    "execution_settings_path <- file.path(base_dir, 'strategus-execution-settings.json')",
    "connectionDetails <- slashOhdsiStrategusAssistant::createStrategusConnectionDetails(path = db_details_path)",
    "exec <- slashOhdsiStrategusAssistant::createStrategusExecutionSettings(path = execution_settings_path)",
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
    "# loads the Strategus workflow assistant package when working from the repo",
    "if (!requireNamespace('slashOhdsiStrategusAssistant', quietly = TRUE)) {",
    "  if (requireNamespace('devtools', quietly = TRUE)) {",
    "    devtools::load_all('OHDSI-Study-Agent/R/slashOhdsiStrategusAssistant')",
    "  } else {",
    "    stop('slashOhdsiStrategusAssistant is not installed and devtools::load_all is unavailable.')",
    "  }",
    "}",
    "library(slashOhdsiStrategusAssistant)",
    "library(jsonlite)",
    "library(ParallelLogger)",
    "`%||%` <- function(x, y) if (is.null(x)) y else x",
    "",
    sprintf("base_dir <- '%s'", base_dir),
    "output_dir <- file.path(base_dir, 'outputs')",
    "analysis_settings_dir <- file.path(base_dir, 'analysis-settings')",
    "dir.create(analysis_settings_dir, recursive = TRUE, showWarnings = FALSE)",
    "time_at_risk_settings_path <- file.path(analysis_settings_dir, 'time_at_risk_settings.json')",
    "selected_dir <- file.path(base_dir, 'selected-cohorts')",
    "patched_dir <- file.path(base_dir, 'patched-cohorts')",
    "cohort_csv <- file.path(selected_dir, 'Cohorts.csv')",
    "cohort_json_dir <- if (length(list.files(patched_dir, pattern = '\\\\.(json)$')) > 0) patched_dir else selected_dir",
    "sql_dir <- file.path(selected_dir, 'sql')",
    "dir.create(sql_dir, recursive = TRUE, showWarnings = FALSE)",
    "",
    "db_details_path <- file.path(base_dir, 'strategus-db-details.json')",
    "execution_settings_path <- file.path(base_dir, 'strategus-execution-settings.json')",
    "connectionDetails <- slashOhdsiStrategusAssistant::createStrategusConnectionDetails(path = db_details_path)",
    "exec <- slashOhdsiStrategusAssistant::createStrategusExecutionSettings(path = execution_settings_path)",
    "executionSettings_incidence <- exec$executionSettings",
    "",
    "cohortDefinitionSet <- CohortGenerator::getCohortDefinitionSet(",
    "  settingsFileName = cohort_csv,",
    "  jsonFolder = cohort_json_dir,",
    "  sqlFolder = sql_dir",
    ")",
    "",
    "roles <- jsonlite::fromJSON(file.path(output_dir, 'cohort_roles.json'), simplifyVector = TRUE)",
    "target_ids <- suppressWarnings(as.integer(unlist(roles$targets %||% integer(0), use.names = FALSE)))",
    "outcome_ids <- suppressWarnings(as.integer(unlist(roles$outcomes %||% integer(0), use.names = FALSE)))",
    "target_ids <- target_ids[!is.na(target_ids)]",
    "outcome_ids <- outcome_ids[!is.na(outcome_ids)]",
    "if (length(target_ids) == 0) stop('No target cohorts defined in cohort_roles.json')",
    "if (length(outcome_ids) == 0) stop('No outcome cohorts defined in cohort_roles.json')",
    "cohortDefinitionSet$cohortId <- suppressWarnings(as.integer(cohortDefinitionSet$cohortId))",
    "cgModule <- CohortGeneratorModule$new()",
    "cohortDefinitionSharedResource <- cgModule$createCohortSharedResourceSpecifications(",
    "  cohortDefinitionSet = cohortDefinitionSet",
    ")",
    "targets <- lapply(target_ids, function(id) {",
    "  row <- cohortDefinitionSet[cohortDefinitionSet$cohortId == id, ]",
    "  if (nrow(row) == 0) stop('Target cohort id not found in Cohorts.csv: ', id)",
    "  CohortIncidence::createCohortRef(id = as.integer(id), name = row$cohortName[1])",
    "})",
    "outcomes <- lapply(outcome_ids, function(id) {",
    "  row <- cohortDefinitionSet[cohortDefinitionSet$cohortId == id, ]",
    "  if (nrow(row) == 0) stop('Outcome cohort id not found in Cohorts.csv: ', id)",
    "  CohortIncidence::createOutcomeDef(id = as.integer(id), name = row$cohortName[1])",
    "})",
    "tar_settings <- jsonlite::fromJSON(time_at_risk_settings_path, simplifyVector = FALSE)",
    "tar_defs <- tar_settings$time_at_risk_defs %||% list()",
    "if (length(tar_defs) == 0) stop('No time-at-risk definitions found in time_at_risk_settings.json')",
    "tars <- lapply(tar_defs, function(def) {",
    "  CohortIncidence::createTimeAtRiskDef(",
    "    id = as.numeric(def$id %||% NA),",
    "    startWith = as.character(def$startWith %||% 'start'),",
    "    startOffset = as.numeric(def$startOffset %||% 0),",
    "    endWith = as.character(def$endWith %||% 'end'),",
    "    endOffset = as.numeric(def$endOffset %||% 0)",
    "  )",
    "})",
    "analysis_tar_ids <- as.numeric(unlist(tar_settings$analysis_tar_ids %||% lapply(tar_defs, function(def) def$id), use.names = FALSE))",
    "analysis_tar_ids <- analysis_tar_ids[!is.na(analysis_tar_ids)]",
    "if (length(analysis_tar_ids) == 0) stop('No analysis TAR ids found in time_at_risk_settings.json')",
    "strata_args <- tar_settings$strata_settings %||% list()",
    "strata_args$byYear <- isTRUE(strata_args$byYear %||% TRUE)",
    "strata_args$byGender <- isTRUE(strata_args$byGender %||% TRUE)",
    "strata_args$byAge <- isTRUE(strata_args$byAge %||% FALSE)",
    "age_breaks <- suppressWarnings(as.numeric(unlist(strata_args$ageBreaks %||% numeric(0), use.names = FALSE)))",
    "age_breaks <- age_breaks[!is.na(age_breaks)]",
    "if (isTRUE(strata_args$byAge) && length(age_breaks) > 0) {",
    "  strata_args$ageBreaks <- age_breaks",
    "} else {",
    "  strata_args$ageBreaks <- NULL",
    "}",
    "strataSettings <- do.call(CohortIncidence::createStrataSettings, strata_args)",
    "analysis1 <- CohortIncidence::createIncidenceAnalysis(",
    "  targets = sapply(targets, function(x) x$id),",
    "  outcomes = sapply(outcomes, function(x) x$id),",
    "  tars = analysis_tar_ids",
    ")",
    "irDesign <- CohortIncidence::createIncidenceDesign(",
    "  targetDefs = targets,",
    "  outcomeDefs = outcomes,",
    "  tars = tars,",
    "  analysisList = list(analysis1),",
    "  strataSettings = strataSettings",
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
      rec <- recommendations_target[[which(vapply(recommendations_target, function(r) r$phenotype_id == selected_ids_target[[i]], logical(1)))]]
      cat(sprintf("  - %s (atlas %s -> cohort %s)\n", rec$phenotype_name %||% "<unknown>", selected_ids_target[[i]], new_ids_target[[i]]))
    }
    cat("Outcome cohorts:\n")
    for (i in seq_along(new_ids_outcome)) {
      rec <- recommendations_outcome[[which(vapply(recommendations_outcome, function(r) r$phenotype_id == selected_ids_outcome[[i]], logical(1)))]]
      cat(sprintf("  - %s (atlas %s -> cohort %s)\n", rec$phenotype_name %||% "<unknown>", selected_ids_outcome[[i]], new_ids_outcome[[i]]))
    }
    cat("JSON outputs:\n")
    cat(sprintf("  - Selected target cohorts: %s\n", selected_target_dir))
    cat(sprintf("  - Selected outcome cohorts: %s\n", selected_outcome_dir))
    cat(sprintf("  - Selected cohorts (combined): %s\n", selected_dir))
    cat(sprintf("  - Time-at-risk settings: %s\n", time_at_risk_settings_path))
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
