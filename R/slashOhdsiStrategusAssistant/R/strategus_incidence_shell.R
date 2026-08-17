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
#' @param showBanner when FALSE, suppress the startup ASCII banner
#' @param studyAgentBaseDir base directory to resolve relative paths (outputDir, indexDir, bannerPath)
#' @param reset when TRUE, delete outputDir before running
#' @param allowCache reuse cached artifacts when present
#' @param promptOnCache prompt before using cached artifacts
#' @param autoApplyImprovements when TRUE, apply improvements without prompting (defaults to TRUE for non-interactive)
#' @param resume when TRUE, resume from last checkpoint if present
#' @param executionTableDisplay execution-menu table display preference: `console`, `viewer`, or `auto`
#' @param aiSupport ACP/AI mode: `disabled` (default), `enabled`, or `auto`
#' @param checkRuntime when TRUE (default), require the release-tested HADES runtime before starting
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
                                      showBanner = TRUE,
                                      studyAgentBaseDir = Sys.getenv("STUDY_AGENT_BASE_DIR", ""),
                                      reset = FALSE,
                                      allowCache = TRUE,
                                      promptOnCache = TRUE,
                                      autoApplyImprovements = NA,
                                      resume = FALSE,
                                      executionTableDisplay = c("console", "viewer", "auto"),
                                      aiSupport = c("disabled", "enabled", "auto"),
                                      checkRuntime = TRUE) {
  `%||%` <- function(x, y) if (is.null(x)) y else x
  execution_table_display <- .studyAgentSlashNormalizeExecutionTableDisplay(executionTableDisplay)
  ai_support <- .studyAgentSlashResolveAiSupport(aiSupport)
  ai_enabled <- .studyAgentSlashAiSupportAllowsAcp(ai_support)
  if (isTRUE(checkRuntime)) checkStrategusRuntime()

  ensure_dir <- function(path) {
    if (!dir.exists(path)) dir.create(path, recursive = TRUE)
  }

  normalize_dialogue_step <- .studyAgentSlashNormalizeIncidenceDialogueStep

  dialogue_step_label <- .studyAgentSlashIncidenceDialogueStepLabel
  compact_dialogue_context <- .studyAgentSlashCompactWorkflowDialogueContext

  dialogue_acp_client <- new.env(parent = emptyenv())
  dialogue_acp_client$client <- NULL
  current_study_intent <- function() {
    intent <- trimws(as.character(studyIntent %||% ""))
    if (nzchar(intent)) return(intent)
    if (exists("project_state_path") && file.exists(project_state_path)) {
      project_state <- tryCatch(.studyAgentSlashReadProjectState(base_dir), error = function(e) NULL)
      intent <- trimws(as.character((project_state$study_context %||% list())$study_intent %||% ""))
      if (nzchar(intent)) return(intent)
    }
    ""
  }
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
    if (!isTRUE(ai_enabled)) return(FALSE)
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
    if (!isTRUE(ai_enabled)) stop(.studyAgentSlashAiSupportDisabledMessage(ai_support, "ACP flow"))
    if (!acp_client_is_ready(dialogue_acp_client$client)) {
      if (!ensure_workflow_dialogue_client(url)) stop("ACP bridge unavailable.")
    }
    .studyAgentSlashCallAcpFlow(dialogue_acp_client$client, flow_name = flow_name, body = body)
  }

  dialogue_session <- .studyAgentSlashNewWorkflowDialogueSession(
    interactive = interactive,
    study_intent_getter = current_study_intent,
    build_stage_context = build_workflow_stage_context,
    call_dialogue = function(stage_context, message) {
      if (!isTRUE(ai_enabled)) stop(.studyAgentSlashAiSupportDisabledMessage(ai_support, "/ohdsi guidance"))
      if (!ensure_workflow_dialogue_client(acpUrl)) {
        stop("ACP bridge unavailable. Connect ACP before using /ohdsi.")
      }
      message("Calling ACP flow: workflow_context_dialogue")
      .studyAgentSlashWorkflowContextDialogue(dialogue_acp_client$client, stage_context, message)
    },
    empty_question_message = "Enter a question after /ohdsi. Example: /ohdsi why are these candidates weak here?",
    disabled_command_message = if (!isTRUE(ai_enabled)) "The /ohdsi command is disabled for this no-AI workflow. Use h or help for local guidance." else NULL
  )
  dialogue_state <- dialogue_session$state
  set_dialogue_context <- dialogue_session$set_context
  raw_readline_with_dialogue <- dialogue_session$readline
  is_back_signal <- function(value) inherits(value, "workflow_navigation_signal") && identical(value$action %||% "", "back")
  build_help_mode <- new.env(parent = emptyenv())
  build_help_mode$enabled <- isTRUE(interactive)

  print_current_build_help <- function() {
    help_lines <- .studyAgentSlashWorkflowBuildHelpLines(
      workflow_type = "strategus_incidence",
      step = dialogue_state$current_step %||% "",
      role = dialogue_state$current_role %||% "",
      context = dialogue_state$current_context %||% list()
    )
    cat("\nBuild help\n")
    for (line in help_lines) cat(sprintf("%s\n", line))
    cat("\n")
    invisible(NULL)
  }

  readline_with_dialogue <- function(prompt, allow_back = FALSE) {
    repeat {
      entered <- raw_readline_with_dialogue(prompt, allow_back = allow_back)
      if (is_back_signal(entered) || !isTRUE(build_help_mode$enabled)) return(entered)
      lowered <- tolower(trimws(as.character(entered %||% "")))
      if (lowered %in% c("h", "help")) {
        print_current_build_help()
        next
      }
      return(entered)
    }
  }
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

  cache_policy <- new.env(parent = emptyenv())
  cache_policy$allowCache <- isTRUE(allowCache)
  cache_policy$promptOnCache <- isTRUE(promptOnCache)

  maybe_use_cache <- function(path, label) {
    if (!isTRUE(cache_policy$allowCache) || !file.exists(path)) return(FALSE)
    if (!isTRUE(cache_policy$promptOnCache)) return(TRUE)
    prompt_yesno(sprintf("Use cached %s at %s?", label, path), default = TRUE)
  }

  configure_revision_mode <- function(scope) {
    cat("\nRevision cache posture\n")
    cat(sprintf("  - allowCache: %s\n", if (isTRUE(cache_policy$allowCache)) "TRUE" else "FALSE"))
    cat(sprintf("  - promptOnCache: %s\n", if (isTRUE(cache_policy$promptOnCache)) "TRUE" else "FALSE"))
    if (isTRUE(cache_policy$allowCache) && !isTRUE(cache_policy$promptOnCache)) {
      cat("Current settings will silently reuse cached decisions when available.\n")
    }
    if (isTRUE(interactive) && (!isTRUE(cache_policy$allowCache) || !isTRUE(cache_policy$promptOnCache))) {
      switch_mode <- prompt_yesno(
        "Switch to temporary revision cache mode for this pass? (allowCache=TRUE, promptOnCache=TRUE)",
        default = TRUE
      )
      if (isTRUE(switch_mode)) {
        cache_policy$allowCache <- TRUE
        cache_policy$promptOnCache <- TRUE
        cat("Revision cache mode enabled for this pass. Cached artifacts may still be reused, but the shell will prompt before doing so.\n")
      }
    }
    invisible(NULL)
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
        entered <- readline_with_navigation(sprintf("%s [%s]: ", prompt, current))
        if (is_back_signal(entered)) return(entered)
        entered <- trimws(as.character(entered %||% ""))
        if (!nzchar(entered)) return(as.integer(current))
        parsed <- suppressWarnings(as.integer(entered))
        if (!is.na(parsed) && (is.null(min_value) || parsed >= min_value)) return(as.integer(parsed))
        cat("Please enter a valid integer.\n")
      }
    }

    prompt_choice_value <- function(prompt, current, choices) {
      repeat {
        entered <- readline_with_navigation(sprintf("%s [%s]: ", prompt, current))
        if (is_back_signal(entered)) return(entered)
        entered <- tolower(trimws(as.character(entered %||% "")))
        if (!nzchar(entered)) return(current)
        if (entered %in% choices) return(entered)
        cat(sprintf("Please enter one of: %s\n", paste(choices, collapse = ", ")))
      }
    }

    prompt_text_value <- function(prompt, current) {
      entered <- readline_with_navigation(sprintf("%s [%s]: ", prompt, current))
      if (is_back_signal(entered)) return(entered)
      if (!nzchar(trimws(entered))) current else trimws(entered)
    }

    tar_count <- prompt_integer_value("Number of time-at-risk definitions", length(settings$time_at_risk_defs), min_value = 1L)
    if (is_back_signal(tar_count)) return(tar_count)
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
      tar_id <- prompt_integer_value("  TAR id", current$id, min_value = 1L)
      if (is_back_signal(tar_id)) return(tar_id)
      tar_name <- prompt_text_value("  TAR label", current$name %||% sprintf("TAR %s", i))
      if (is_back_signal(tar_name)) return(tar_name)
      start_with <- prompt_choice_value("  startWith (start/end)", current$startWith %||% "start", c("start", "end"))
      if (is_back_signal(start_with)) return(start_with)
      start_offset <- prompt_integer_value("  startOffset (days)", current$startOffset %||% 0L)
      if (is_back_signal(start_offset)) return(start_offset)
      end_with <- prompt_choice_value("  endWith (start/end)", current$endWith %||% "end", c("start", "end"))
      if (is_back_signal(end_with)) return(end_with)
      end_offset <- prompt_integer_value("  endOffset (days)", current$endOffset %||% 0L)
      if (is_back_signal(end_offset)) return(end_offset)
      defs[[i]] <- list(
        id = tar_id,
        name = tar_name,
        startWith = start_with,
        startOffset = start_offset,
        endWith = end_with,
        endOffset = end_offset
      )
    }

    default_analysis_ids <- paste(vapply(defs, function(item) as.integer(item$id), integer(1)), collapse = ",")
    analysis_ids_text <- readline_with_navigation(sprintf("Analysis TAR ids (comma-separated) [%s]: ", default_analysis_ids))
    if (is_back_signal(analysis_ids_text)) return(analysis_ids_text)
    analysis_ids_text <- trimws(as.character(analysis_ids_text %||% ""))
    analysis_ids <- if (!nzchar(analysis_ids_text)) {
      suppressWarnings(as.integer(strsplit(default_analysis_ids, ",", fixed = TRUE)[[1]]))
    } else {
      suppressWarnings(as.integer(trimws(strsplit(analysis_ids_text, ",", fixed = TRUE)[[1]])))
    }

    strata_settings <- settings$strata_settings
    by_year <- prompt_yesno_navigation("Stratify incidence by calendar year?", default = isTRUE(strata_settings$byYear))
    if (is_back_signal(by_year)) return(by_year)
    by_gender <- prompt_yesno_navigation("Stratify incidence by gender?", default = isTRUE(strata_settings$byGender))
    if (is_back_signal(by_gender)) return(by_gender)
    by_age <- prompt_yesno_navigation("Stratify incidence by age?", default = isTRUE(strata_settings$byAge))
    if (is_back_signal(by_age)) return(by_age)
    age_breaks_default <- paste(strata_settings$ageBreaks %||% c(18L, 45L, 65L), collapse = ",")
    age_breaks <- strata_settings$ageBreaks %||% c(18L, 45L, 65L)
    if (isTRUE(by_age)) {
      age_breaks_text <- readline_with_navigation(sprintf("Age breaks (comma-separated integers) [%s]: ", age_breaks_default))
      if (is_back_signal(age_breaks_text)) return(age_breaks_text)
      age_breaks_text <- trimws(as.character(age_breaks_text %||% ""))
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

  phenotype_definition_path <- function(phenotype_id, index_def_dir, imported_def_dir = NULL) {
    phenotype_id <- as.character(phenotype_id %||% "")
    if (grepl("^(db:[A-Za-z][A-Za-z0-9_]*:[0-9]+|file:[0-9]+:[A-Za-z0-9_.-]+|dir:[0-9]+:[A-Za-z0-9_.-]+)$", phenotype_id)) {
      return(.studyAgentSlashImportedCohortDefinitionPath(phenotype_id, imported_def_dir))
    }
    file.path(index_def_dir, sprintf("%s.json", gsub(":", "__", phenotype_id, fixed = TRUE)))
  }

  stop_if_unsupported_selected <- function(phenotype_ids, role_label) {
    .studyAgentSlashStopIfUnsupportedSelected(phenotype_ids, role_label)
  }

  default_cohort_id_from_source <- function(source_id) {
    source_id <- as.character(source_id %||% "")
    if (!nzchar(source_id)) return(NA_integer_)
    if (grepl("^ohdsi:[0-9]+$", source_id)) {
      return(suppressWarnings(as.integer(sub("^ohdsi:", "", source_id))))
    }
    if (grepl("^db:[A-Za-z][A-Za-z0-9_]*:[0-9]+$", source_id)) {
      return(suppressWarnings(as.integer(sub("^db:[A-Za-z][A-Za-z0-9_]*:([0-9]+)$", "\\1", source_id))))
    }
    if (grepl("^(file|dir):[0-9]+:[A-Za-z0-9_.-]+$", source_id)) {
      return(suppressWarnings(as.integer(sub("^(file|dir):([0-9]+):[A-Za-z0-9_.-]+$", "\\2", source_id))))
    }
    suppressWarnings(as.integer(source_id))
  }

  default_cohort_ids_from_sources <- function(source_ids, role_label = "selected") {
    .studyAgentSlashDefaultCohortIdsFromSources(source_ids, role_label = role_label)
  }

  copy_cohort_json_multi <- function(source_id, dest_id, dest_dirs, index_def_dir, imported_def_dir = NULL) {
    .studyAgentSlashCopyCohortJsonMulti(source_id, dest_id, dest_dirs, index_def_dir, imported_def_dir = imported_def_dir, ensure_dir = ensure_dir)
  }

  selection_record_from_recommendation <- function(rec) {
    .studyAgentSlashSelectionRecordFromRecommendation(rec)
  }

  selection_record_from_import <- function(imported) {
    .studyAgentSlashSelectionRecordFromImport(imported)
  }

  seed_db_details_template <- function(path) {
    .studyAgentSlashSeedDbDetailsTemplate(path, write_json = write_json)
  }

  choose_selection_source_mode <- function(role_label, allow_index = TRUE) {
    .studyAgentSlashChooseSelectionSourceMode(
      role_label = role_label,
      allow_index = allow_index,
      interactive = interactive,
      readline_with_navigation = readline_with_navigation,
      is_back_signal = is_back_signal
    )
  }

  default_direct_statement <- function(role_label, study_intent) {
    intent <- trimws(as.character(study_intent %||% ""))
    if (nzchar(intent)) {
      sprintf("%s cohort provided directly for study intent: %s", role_label, intent)
    } else {
      sprintf("%s cohort provided directly by user", role_label)
    }
  }

  default_direct_study_intent <- function(target_statement, outcome_statement) {
    sprintf(
      "Summarize the incidence of the outcome %s in patients from the target cohort %s.",
      trimws(as.character(outcome_statement %||% "")),
      trimws(as.character(target_statement %||% ""))
    )
  }

  ensure_study_intent_from_role_statements <- function(study_intent, target_statement, outcome_statement) {
    resolved <- trimws(as.character(study_intent %||% ""))
    if (nzchar(resolved)) return(resolved)
    template_intent <- default_direct_study_intent(target_statement, outcome_statement)
    if (!isTRUE(interactive)) return(template_intent)
    set_dialogue_context("study_intent", context = list(
      default_intent = template_intent,
      target_statement = target_statement,
      outcome_statement = outcome_statement,
      generated_from_role_statements = TRUE
    ))
    entered <- readline_with_navigation(sprintf("Study intent derived from cohort statements [%s]: ", template_intent))
    if (is_back_signal(entered)) return(entered)
    entered <- trimws(as.character(entered %||% ""))
    if (nzchar(entered)) entered else template_intent
  }

  cohort_source_db_details_need_configuration <- function(path) {
    .studyAgentSlashCohortSourceDbDetailsNeedConfiguration(path, readStrategusDbDetails = readStrategusDbDetails)
  }

  prompt_database_cohort_imports <- function(role_label, allow_multiple = FALSE) {
    .studyAgentSlashPromptDatabaseCohortImports(
      role_label = role_label,
      allow_multiple = allow_multiple,
      base_dir = base_dir,
      imported_definition_dir = imported_definition_dir,
      interactive = interactive,
      readline_with_navigation = readline_with_navigation,
      readline_with_dialogue = readline_with_dialogue,
      is_back_signal = is_back_signal,
      write_json = write_json,
      readStrategusDbDetails = readStrategusDbDetails,
      normalizeStrategusDbConfig = normalizeStrategusDbConfig,
      createStrategusConnectionDetails = createStrategusConnectionDetails
    )
  }

  prompt_file_cohort_imports <- function(role_label, allow_multiple = FALSE) {
    .studyAgentSlashPromptFileCohortImports(
      role_label = role_label,
      allow_multiple = allow_multiple,
      imported_definition_dir = imported_definition_dir,
      readline_with_navigation = readline_with_navigation,
      is_back_signal = is_back_signal
    )
  }

  prompt_directory_cohort_imports <- function(role_label, allow_multiple = FALSE) {
    .studyAgentSlashPromptDirectoryCohortImports(
      role_label = role_label,
      allow_multiple = allow_multiple,
      imported_definition_dir = imported_definition_dir,
      interactive = interactive,
      readline_with_navigation = readline_with_navigation,
      readline_with_dialogue = readline_with_dialogue,
      is_back_signal = is_back_signal
    )
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

  imported_definition_dir <- file.path(base_dir, "imported-cohort-definitions")
  ensure_dir(imported_definition_dir)


  project_state_path <- .studyAgentSlashProjectStatePath(base_dir)
  runtime_state_path <- .studyAgentSlashRuntimeStatePath(base_dir)

  confirm_resume_execution_roots <- function() {
    if (!file.exists(project_state_path)) return(invisible(NULL))
    project_state <- .studyAgentSlashReadProjectState(base_dir)
    roots <- .studyAgentSlashConfiguredExecutionRoots(base_dir, project_state = project_state, prefer_confirmed = TRUE)
    results_root <- as.character(roots$results_root %||% "")
    work_root <- as.character(roots$work_root %||% "")
    warnings <- as.character(unlist(roots$warnings %||% character(0), use.names = FALSE))

    cat("\nExecution roots for resume\n")
    cat(sprintf("  - results: %s\n", if (nzchar(results_root)) results_root else "<not set>"))
    cat(sprintf("  - work: %s\n", if (nzchar(work_root)) work_root else "<not set>"))
    if (length(warnings) > 0) {
      cat("Warnings\n")
      for (warning in warnings) cat(sprintf("  - %s\n", warning))
      cat("Use full paths here if the configured roots are ambiguous.\n")
    }

    use_current <- TRUE
    if (isTRUE(interactive)) {
      use_current <- prompt_yesno("Use these execution roots for resumed artifact discovery?", default = length(warnings) == 0)
    }
    if (!isTRUE(use_current) && isTRUE(interactive)) {
      entered_results <- trimws(readline_with_dialogue(sprintf("Results root [%s]: ", results_root)))
      entered_work <- trimws(readline_with_dialogue(sprintf("Work root [%s]: ", work_root)))
      if (!nzchar(entered_results)) entered_results <- results_root
      if (!nzchar(entered_work)) entered_work <- work_root
      manual_warnings <- character(0)
      if (.studyAgentSlashPathLooksLikeNestedProjectRelative(entered_results, base_dir)) {
        manual_warnings <- c(manual_warnings, sprintf("results root still looks nested under the project directory name: %s", entered_results))
      }
      if (.studyAgentSlashPathLooksLikeNestedProjectRelative(entered_work, base_dir)) {
        manual_warnings <- c(manual_warnings, sprintf("work root still looks nested under the project directory name: %s", entered_work))
      }
      .studyAgentSlashPersistExecutionRoots(
        base_dir = base_dir,
        project_state = project_state,
        results_root = entered_results,
        work_root = entered_work,
        source = "resume_prompt",
        warnings = manual_warnings,
        write = TRUE
      )
      return(invisible(NULL))
    }

    .studyAgentSlashPersistExecutionRoots(
      base_dir = base_dir,
      project_state = project_state,
      results_root = results_root,
      work_root = work_root,
      source = "resume_confirmed",
      write = TRUE
    )
    invisible(NULL)
  }

  print_execution_status <- function() {
    if (!file.exists(project_state_path)) {
      cat("No study-agent project manifest found.\n")
      return(invisible(NULL))
    }
    cat("\nExecution status\n")
    for (line in .studyAgentSlashSummarizeWorkflowStatus(base_dir)) {
      cat(sprintf("  - %s\n", line))
    }
    artifact_roots <- .studyAgentSlashExecutionArtifactPaths(base_dir)
    if (length(artifact_roots) > 0) {
      cat("Artifact roots
")
      for (root in artifact_roots) {
        cat(sprintf("  - %s\n", .studyAgentSlashResolveArtifactPath(root, base_dir)))
      }
    }
    invisible(NULL)
  }

  refresh_execution_dialogue_context <- function(step_id = NULL) {
    if (!file.exists(project_state_path)) return(invisible(NULL))
    project_state <- .studyAgentSlashReconcileProjectState(base_dir, write = TRUE)$project_state
    if (is.null(step_id) || !nzchar(trimws(as.character(step_id)))) {
      step_id <- project_state$resume$current_step_id %||% NULL
    }
    step <- if (!is.null(step_id)) .studyAgentSlashFindPlanStep(project_state, step_id) else NULL
    current_step <- step$stage_context_step %||% "workflow_summary"
    set_dialogue_context(
      current_step,
      context = .studyAgentSlashBuildExecutionDialogueContext(
        project_state = project_state,
        base_dir = base_dir,
        step = step,
        runtime_state = .studyAgentSlashReadRuntimeState(base_dir)
      )
    )
    invisible(NULL)
  }

  inspect_execution_outputs <- function(step_id, viewer = FALSE) {
    outputs <- .studyAgentSlashInspectWorkflowStepOutputs(base_dir, step_id)
    if (length(outputs) == 0) {
      cat("No registered outputs for that step.
")
      return(invisible(NULL))
    }
    output_table <- do.call(rbind, lapply(names(outputs), function(name) {
      item <- outputs[[name]]
      absolute_path <- as.character(item$absolute_path %||% item$path %||% "<missing>")
      relative_path <- as.character(item$path %||% absolute_path)
      data.frame(
        output_id = name,
        exists = isTRUE(item$exists),
        relative_path = relative_path,
        path = absolute_path,
        stringsAsFactors = FALSE
      )
    }))
    viewer_table <- .studyAgentSlashPrepareViewerTable(
      output_table,
      preferred_order = c("output_id", "exists", "relative_path", "path")
    )
    display <- if (isTRUE(viewer)) NULL else execution_table_display
    display <- if (isTRUE(viewer)) NULL else execution_table_display
    render_mode <- .studyAgentSlashResolveExecutionTableDisplay(display = display, viewer = viewer)
    cat(sprintf("
Outputs for %s
", step_id))
    if (isTRUE(render_mode$show_console)) {
      print(output_table)
    }
    if (isTRUE(render_mode$open_viewer)) {
      .studyAgentSlashOpenTableViewer(viewer_table, title = sprintf("Outputs for %s", step_id))
    } else if ((isTRUE(viewer) || !is.null(display)) && !isTRUE(render_mode$supports_viewer)) {
      cat("Viewer mode is not available in this R session; showing the compact console table instead.
")
    }
    invisible(output_table)
  }

  current_execution_step_id <- function() {
    if (!file.exists(project_state_path)) return(NULL)
    project_state <- .studyAgentSlashReconcileProjectState(base_dir, write = TRUE)$project_state
    step_id <- as.character(project_state$resume$current_step_id %||% "")
    if (!nzchar(step_id)) return(NULL)
    step_id
  }

  available_exploration_commands <- function() {
    if (!file.exists(project_state_path)) return(list())
    project_state <- .studyAgentSlashReconcileProjectState(base_dir, write = TRUE)$project_state
    .studyAgentSlashListExplorationCommands(
      base_dir = base_dir,
      workflow_type = project_state$workflow_type %||% "",
      step_id = project_state$resume$current_step_id %||% NULL
    )
  }

  print_execution_step_choices <- function() {
    cat("Valid step values are:\n")
    for (line in .studyAgentSlashFormatWorkflowStepChoices(base_dir)) {
      cat(sprintf("  - %s\n", line))
    }
    invisible(NULL)
  }

  print_execution_help <- function() {
    table_mode_label <- switch(
      execution_table_display,
      console = "console preview",
      viewer = "viewer-first",
      auto = "auto (viewer when available)",
      execution_table_display
    )
    cat("
Execution commands
")
    cat("  - Enter: finish this execution menu")
    if (!isTRUE(.studyAgentSlashWorkflowIsComplete(base_dir))) {
      cat(" (confirmation required)")
    }
    cat("
")
    cat("  - h or help: show this help
")
    cat("  - s or status: show execution status (derived from step state and artifacts)
")
    cat("  - art or artifacts: list current known artifacts\n")
    cat("  - v or viewer: launch the local read-only artifact browser (ends when the Shiny app stops)\n")
    cat("  - b or backup: create a workflow state snapshot\n")
    cat("  - bk or backups: list available workflow state snapshots\n")
    cat("  - x or explore[_v]: list available approved exploration commands
")
    cat("  - x <command-id> or explore <command-id>: run an approved exploration command
")
    cat("  - x_v <command-id> or explore_v <command-id>: run an approved exploration command and try to open tabular output in a viewer
")
    cat("  - number: run the numbered exploration command shown by x
")
    cat("  - n or run next: run the next runnable step
")
    cat("  - a or run all: keep running until blocked, failed, or complete
")
    cat("  - i or inspect[_v] <step>: inspect outputs for a step
  - reset <step>: reset a step and downstream workflow state
  - skip <step>: mark an optional step skipped and advance resume state
  - restore <snapshot-id>: restore a saved workflow state snapshot
")
    cat("  - run <step>: run a specific step by number or step id
")
    cat("  - rev or revise [build|intent|target|outcome]: return to build mode for intentional revision
")
    if (isTRUE(ai_enabled)) cat("  - /ohdsi <question>: ask a contextualized OHDSI workflow question\n")
    cat("  - q or quit: leave the execution menu
")
    cat(sprintf("  - default table display for art/x/inspect: %s
", table_mode_label))
    cat("
Valid step values
")
    print_execution_step_choices()
    print_explore_help()
    invisible(NULL)
  }

  print_artifact_help <- function() {
    cat("\nArtifacts\n")
    cat("  - art or artifacts: list artifacts known to the current workflow project\n")
    cat("  - These include manifest artifacts plus inferred cohort-generation outputs when available\n")
    invisible(NULL)
  }

  print_explore_help <- function() {
    commands <- available_exploration_commands()
    table <- .studyAgentSlashExplorationCommandTable(commands)
    cat("\nExploration commands\n")
    cat("  - x or explore[_v]: list available approved exploration commands\n")
    cat("  - x <command-id> or explore <command-id>: run one approved exploration command\n")
    cat("  - x_v <command-id> or explore_v <command-id>: run one approved exploration command and try to open tabular output in a viewer\n")
    if (nrow(table) == 0) {
      cat("  - No exploration commands are currently available for this workflow state\n")
      return(invisible(NULL))
    }
    for (row in seq_len(nrow(table))) {
      cat(sprintf("  - %s: %s\n", table$command_id[[row]], table$purpose[[row]]))
    }
    invisible(NULL)
  }

  print_artifact_inventory <- function(viewer = FALSE) {
    registry <- .studyAgentSlashBuildArtifactRegistry(base_dir)
    table <- .studyAgentSlashArtifactRegistryTable(registry)
    if (nrow(table) == 0) {
      cat("No artifacts are available for the current workflow project.
")
      return(invisible(NULL))
    }
    display <- if (isTRUE(viewer)) NULL else execution_table_display
    render_mode <- .studyAgentSlashResolveExecutionTableDisplay(display = display, viewer = viewer)
    viewer_table <- .studyAgentSlashArtifactRegistryTable(registry, viewer = TRUE)
    cat("
Artifact inventory
")
    if (isTRUE(render_mode$show_console)) {
      print(.studyAgentSlashCompactPreviewTable(table, max_rows = 40L, max_cols = 5L))
    }
    if (isTRUE(render_mode$open_viewer)) {
      .studyAgentSlashOpenTableViewer(viewer_table, title = "Artifact inventory")
    } else if ((isTRUE(viewer) || !is.null(display)) && !isTRUE(render_mode$supports_viewer)) {
      cat("Viewer mode is not available in this R session; showing the compact console table instead.
")
    }
    cat("
")
    invisible(NULL)
  }

  print_exploration_commands <- function(viewer = FALSE) {
    commands <- available_exploration_commands()
    table <- .studyAgentSlashExplorationCommandTable(commands)
    if (nrow(table) == 0) {
      cat("No approved exploration commands are available for the current workflow state.
")
      return(invisible(NULL))
    }
    display <- if (isTRUE(viewer)) NULL else execution_table_display
    render_mode <- .studyAgentSlashResolveExecutionTableDisplay(display = display, viewer = viewer)
    viewer_table <- .studyAgentSlashPrepareViewerTable(table, preferred_order = c("command_id", "label", "purpose"))
    cat("
Available exploration commands
")
    if (isTRUE(render_mode$show_console)) {
      print(table)
    }
    if (isTRUE(render_mode$open_viewer)) {
      .studyAgentSlashOpenTableViewer(viewer_table, title = "Available exploration commands")
    } else if ((isTRUE(viewer) || !is.null(display)) && !isTRUE(render_mode$supports_viewer)) {
      cat("Viewer mode is not available in this R session; showing the compact console table instead.
")
    }
    cat("
")
    invisible(NULL)
  }

  resolve_execution_step_id <- function(step_ref) {
    resolved <- .studyAgentSlashResolveWorkflowStepId(base_dir, step_ref)
    if (!is.null(resolved) && nzchar(trimws(resolved))) return(resolved)
    cat(sprintf("Unknown step '%s'.\n", trimws(as.character(step_ref %||% ""))))
    print_execution_step_choices()
    NULL
  }

  resolve_exploration_command_id <- function(command_ref) {
    command_ref <- trimws(as.character(command_ref %||% ""))
    commands <- available_exploration_commands()
    command_ids <- vapply(commands, function(cmd) as.character(cmd$command_id %||% ""), character(1))
    if (grepl("^[0-9]+$", command_ref) && length(commands) > 0) {
      idx <- suppressWarnings(as.integer(command_ref))
      if (!is.na(idx) && idx >= 1L && idx <= length(commands)) {
        return(command_ids[[idx]])
      }
    }
    if (nzchar(command_ref) && command_ref %in% command_ids) return(command_ref)
    cat(sprintf("Unknown exploration command '%s'.\n", command_ref))
    print_explore_help()
    NULL
  }

  confirm_execution_menu_exit <- function() {
    if (isTRUE(.studyAgentSlashWorkflowIsComplete(base_dir))) return(TRUE)
    prompt_yesno("Exit execution menu and return to the R prompt?", default = FALSE)
  }

  prompt_for_inspect_step <- function(viewer = FALSE) {
    prompt <- if (isTRUE(viewer)) {
      "Step number or step id to inspect in viewer (? for choices): "
    } else {
      "Step number or step id to inspect (? for choices): "
    }
    repeat {
      step_ref <- trimws(readline_with_dialogue(prompt))
      lowered <- tolower(step_ref)
      if (lowered %in% c("h", "help", "?")) {
        print_execution_step_choices()
        next
      }
      return(step_ref)
    }
  }

  run_exploration_command <- function(command_ref, viewer = FALSE) {
    command_id <- resolve_exploration_command_id(command_ref)
    if (is.null(command_id)) return(invisible(FALSE))
    display <- if (isTRUE(viewer)) NULL else execution_table_display
    result <- .studyAgentSlashRunExplorationCommand(base_dir, command_id = command_id)
    .studyAgentSlashRenderExplorationResult(result, viewer = viewer, display = display)
    invisible(TRUE)
  }

  run_execution_menu <- function(prompt_first = TRUE) {
    if (!isTRUE(interactive)) return(invisible(list(action = "exit")))
    if (!file.exists(project_state_path) || !file.exists(runtime_state_path)) return(invisible(list(action = "exit")))
    prior_build_help_mode <- isTRUE(build_help_mode$enabled)
    build_help_mode$enabled <- FALSE
    on.exit({
      build_help_mode$enabled <- prior_build_help_mode
    }, add = TRUE)
    valid_revise_scopes <- c("build", "intent", "target", "outcome")
    normalize_revise_scope <- function(command_text) {
      if (command_text %in% c("rev", "revise")) return("build")
      scope <- trimws(sub("^rev(?:ise)?\\s+", "", command_text))
      if (identical(scope, command_text)) scope <- trimws(sub("^rev\\s+", "", command_text))
      if (!nzchar(scope)) return("build")
      if (scope %in% valid_revise_scopes) return(scope)
      NULL
    }
    if (isTRUE(prompt_first) && !prompt_yesno("Start running generated workflow steps in this shell now?", default = FALSE)) {
      return(invisible(list(action = "exit")))
    }
    repeat {
      .studyAgentSlashReconcileProjectState(base_dir, write = TRUE)
      refresh_execution_dialogue_context()
      execution_prompt <- if (isTRUE(ai_enabled)) {
        "Execution command [h=help/show commands, Enter=finish, x=explore[_v], s=status, /ohdsi=AI assistance]: "
      } else {
        "Execution command [h=help/show commands, Enter=finish, x=explore[_v], s=status]: "
      }
      entered <- trimws(readline_with_dialogue(execution_prompt))
      if (!nzchar(entered)) {
        if (isTRUE(confirm_execution_menu_exit())) return(invisible(list(action = "exit")))
        next
      }
      lowered <- tolower(entered)
      if (lowered %in% c("h", "help", "?")) {
        print_execution_help()
        next
      }
      if (identical(lowered, "help artifacts")) {
        print_artifact_help()
        next
      }
      if (identical(lowered, "help explore")) {
        print_explore_help()
        next
      }
      if (lowered %in% c("v", "viewer")) {
        cat("Launching the local artifact browser. Stop the Shiny app to return to this execution menu.\n")
        launch_result <- tryCatch({
          launchStrategusArtifactBrowser(base_dir)
          NULL
        }, error = function(e) e)
        if (inherits(launch_result, "error")) cat(sprintf("Artifact browser could not be launched: %s\n", conditionMessage(launch_result)))
        next
      }
      if (lowered %in% c("art", "artifact", "artifacts")) {
        print_artifact_inventory()
        next
      }
      if (lowered %in% c("art_v", "artifact_v", "artifacts_v")) {
        print_artifact_inventory(viewer = TRUE)
        next
      }
      if (lowered %in% c("x", "explore")) {
        print_exploration_commands()
        next
      }
      if (lowered %in% c("x_v", "explore_v")) {
        print_exploration_commands(viewer = TRUE)
        next
      }
      if (grepl("^[0-9]+$", lowered)) {
        run_exploration_command(lowered)
        next
      }
      if (startsWith(lowered, "x_v ") || startsWith(lowered, "explore_v ")) {
        command_ref <- sub("^(?:x_v|explore_v)\\s+", "", lowered)
        run_exploration_command(command_ref, viewer = TRUE)
        next
      }
      if (startsWith(lowered, "x ") || startsWith(lowered, "explore ")) {
        command_ref <- sub("^(?:x|explore)\\s+", "", lowered)
        run_exploration_command(command_ref)
        next
      }
      if (lowered %in% c("b", "backup")) {
        backup_info <- .studyAgentSlashBackupWorkflowState(base_dir, label = "manual")
        cat(sprintf("Workflow state snapshot saved: %s\n", backup_info$snapshot_id %||% backup_info$snapshot_dir %||% "<unknown>"))
        next
      }
      if (lowered %in% c("bk", "backups", "snapshot", "snapshots")) {
        snapshot_ids <- rev(.studyAgentSlashListWorkflowBackups(base_dir))
        if (length(snapshot_ids) == 0) {
          cat("No workflow snapshots are available for this project.\n")
        } else {
          cat("\nWorkflow snapshots\n")
          for (snapshot_id in snapshot_ids) cat(sprintf("  - %s\n", snapshot_id))
        }
        next
      }
      if (startsWith(lowered, "restore ")) {
        snapshot_id <- trimws(sub("^restore\\s+", "", entered))
        if (!nzchar(snapshot_id)) {
          cat("Choose restore <snapshot-id>. Use backups to list available snapshots.\n")
          next
        }
        if (!isTRUE(prompt_yesno(sprintf("Restore workflow state snapshot %s?", snapshot_id), default = FALSE))) {
          next
        }
        result <- tryCatch(
          .studyAgentSlashRestoreWorkflowState(base_dir, snapshot_id = snapshot_id, restore_artifacts = TRUE, backup_current = TRUE),
          error = function(e) e
        )
        if (inherits(result, "error")) {
          cat(sprintf("Restore failed: %s\n", conditionMessage(result)))
        } else {
          cat(sprintf("Workflow state restored from snapshot: %s\n", snapshot_id))
        }
        next
      }
      if (startsWith(lowered, "reset ")) {
        step_id <- resolve_execution_step_id(sub("^reset\\s+", "", lowered))
        if (is.null(step_id)) next
        if (!isTRUE(prompt_yesno(sprintf("Reset step %s and downstream workflow state?", step_id), default = FALSE))) {
          next
        }
        result <- tryCatch(
          .studyAgentSlashResetWorkflowStepState(base_dir, step_id = step_id, cascade = TRUE, backup = TRUE, delete_outputs = TRUE),
          error = function(e) e
        )
        if (inherits(result, "error")) {
          cat(sprintf("Reset failed: %s\n", conditionMessage(result)))
        } else {
          affected <- as.character(unlist(result$affected_steps %||% list(), use.names = FALSE))
          cat(sprintf("Reset workflow state for: %s\n", paste(affected, collapse = ", ")))
          if (!is.null(result$snapshot_id) && nzchar(as.character(result$snapshot_id))) {
            cat(sprintf("Backup snapshot saved: %s\n", as.character(result$snapshot_id)))
          }
        }
        next
      }
      if (startsWith(lowered, "skip ")) {
        step_id <- resolve_execution_step_id(sub("^skip\\s+", "", lowered))
        if (is.null(step_id)) next
        if (!isTRUE(prompt_yesno(sprintf("Mark step %s as skipped?", step_id), default = FALSE))) {
          next
        }
        result <- tryCatch(
          .studyAgentSlashSkipWorkflowStep(base_dir, step_id = step_id, reason = "user_skipped"),
          error = function(e) list(status = "error", error = conditionMessage(e))
        )
        if (identical(result$status %||% "", "skipped")) {
          cat(sprintf("Step %s marked skipped.\n", step_id))
        } else {
          cat(sprintf("Step %s could not be skipped: %s\n", step_id, result$error %||% result$message %||% "unknown error"))
        }
        next
      }
      if (lowered %in% c("rev", "revise") || startsWith(lowered, "rev ") || startsWith(lowered, "revise ")) {
        revise_scope <- normalize_revise_scope(lowered)
        if (is.null(revise_scope)) {
          cat("Choose revise build, revise intent, revise target, or revise outcome.\n")
          next
        }
        revise_label <- if (identical(revise_scope, "build")) {
          "the build workflow"
        } else {
          sprintf("the %s selection", revise_scope)
        }
        if (isTRUE(prompt_yesno(sprintf("Leave execution mode and return to build mode to revise %s?", revise_label), default = FALSE))) {
          return(invisible(list(action = "revise", scope = revise_scope)))
        }
        next
      }
      if (lowered %in% c("q", "quit", "exit")) {
        if (isTRUE(confirm_execution_menu_exit())) return(invisible(list(action = "exit")))
        next
      }
      if (lowered %in% c("s", "status")) {
        print_execution_status()
        next
      }
      if (lowered %in% c("n", "next", "r", "resume", "run next")) {
        result <- .studyAgentSlashRunNextWorkflowPlanStep(base_dir)
        if (identical(result$status %||% "", "failed")) {
          cat(sprintf("Step %s failed: %s\n", result$step_id %||% "<unknown>", result$error %||% "unknown error"))
        } else if (!is.null(result$step_id)) {
          cat(sprintf("Step %s completed.\n", result$step_id))
        } else {
          cat(sprintf("%s\n", result$message %||% "No remaining runnable workflow steps."))
        }
        next
      }
      if (lowered %in% c("a", "all", "run all")) {
        repeat {
          result <- .studyAgentSlashRunNextWorkflowPlanStep(base_dir)
          if (identical(result$status %||% "", "failed")) {
            cat(sprintf("Step %s failed: %s\n", result$step_id %||% "<unknown>", result$error %||% "unknown error"))
            break
          }
          if (is.null(result$step_id)) {
            cat(sprintf("%s\n", result$message %||% "No remaining runnable workflow steps."))
            break
          }
          cat(sprintf("Step %s completed.\n", result$step_id))
        }
        next
      }
      if (startsWith(lowered, "run ")) {
        step_id <- resolve_execution_step_id(sub("^run\\s+", "", lowered))
        if (is.null(step_id)) next
        result <- tryCatch(
          .studyAgentSlashRunWorkflowPlanStep(base_dir, step_id = step_id),
          error = function(e) list(status = "error", error = conditionMessage(e))
        )
        if (identical(result$status %||% "", "completed")) {
          cat(sprintf("Step %s completed.\n", step_id))
        } else {
          cat(sprintf("Step %s could not be run: %s\n", step_id, result$error %||% "unknown error"))
        }
        next
      }
      if (lowered %in% c("i", "inspect", "i_v", "inspect_v") || startsWith(lowered, "inspect ") || startsWith(lowered, "inspect_v ") || startsWith(lowered, "i_v ")) {
        viewer <- lowered %in% c("i_v", "inspect_v") || startsWith(lowered, "inspect_v ") || startsWith(lowered, "i_v ")
        step_ref <- if (startsWith(lowered, "inspect_v ")) {
          sub("^inspect_v\\s+", "", lowered)
        } else if (startsWith(lowered, "inspect ")) {
          sub("^inspect\\s+", "", lowered)
        } else if (startsWith(lowered, "i_v ")) {
          sub("^i_v\\s+", "", lowered)
        } else {
          prompt_for_inspect_step(viewer = viewer)
        }
        step_id <- resolve_execution_step_id(step_ref)
        if (is.null(step_id)) next
        inspect_execution_outputs(step_id, viewer = viewer)
        next
      }
      cat(if (isTRUE(ai_enabled)) "Choose h, s, art, x[_v], b, bk, reset <step>, skip <step>, restore <snapshot-id>, rev, n, a, i[_v], run <step>, /ohdsi <question>, q, or Enter. Type h for valid steps and explore for approved commands.\n" else "Choose h, s, art, x[_v], b, bk, reset <step>, skip <step>, restore <snapshot-id>, rev, n, a, i[_v], run <step>, q, or Enter. Type h for valid steps and explore for approved commands.\n")
    }
  }

  if (interactive) {
    banner_path <- resolve_path(bannerPath, study_base_dir)
    banner_path <- normalizePath(banner_path, winslash = "/", mustWork = FALSE)
    if (!file.exists(banner_path) && !is_absolute_path(bannerPath) && !nzchar(studyAgentBaseDir)) {
      alt <- file.path(getwd(), "OHDSI-Study-Agent", bannerPath)
      if (file.exists(alt)) banner_path <- normalizePath(alt, winslash = "/", mustWork = FALSE)
    }
    if (isTRUE(showBanner) && file.exists(banner_path)) {
      cat(paste(readLines(banner_path, warn = FALSE), collapse = "\n"), "\n")
    }
    cat("\nStudy Agent: Strategus CohortIncidence shell\n")
    if (isTRUE(ai_enabled)) {
      cat("Use /ohdsi for contextual guidance. Type /back at supported stage boundaries to return to the previous step.\n")
    } else {
      cat("Type /back at supported stage boundaries to return to the previous step.\n")
    }
  }

  if (isTRUE(resume) && file.exists(project_state_path) && file.exists(runtime_state_path)) {
    cat("\nExisting study-agent project detected.\n")
    confirm_resume_execution_roots()
    print_execution_status()
    if (isTRUE(interactive) && prompt_yesno("Resume existing generated workflow execution in this shell?", default = TRUE)) {
      menu_result <- run_execution_menu(prompt_first = FALSE)
      if (!identical(as.character(menu_result$action %||% "exit"), "revise")) {
        return(invisible(list(
          output_dir = output_dir,
          scripts_dir = scripts_dir,
          state = file.path(output_dir, "study_agent_state.json"),
          project_state = project_state_path,
          runtime_state = runtime_state_path
        )))
      }
      revise_scope <- as.character(menu_result$scope %||% "build")
      revise_label <- if (identical(revise_scope, "build")) {
        "the workflow"
      } else {
        sprintf("the %s selection", revise_scope)
      }
      configure_revision_mode(revise_scope)
      cat(sprintf("\nRe-entering build mode to revise %s. Saved answers will be reused as defaults where available.\n", revise_label))
      studyIntent <- current_study_intent() %||% studyIntent
      resume <- FALSE
    }
  }

  default_intent <- studyIntent %||% ""
  skip_intent_split_and_recommendation <- FALSE
  skip_phenotype_improvements <- FALSE
  direct_acquisition_mode <- FALSE
  skip_reason <- NULL
  skip_prompt_source <- "not_prompted"
  repeat {
    blank_study_intent_direct <- FALSE
    if (interactive) {
      set_dialogue_context("study_intent", context = list(default_intent = default_intent))
      entered <- readline_with_navigation(sprintf(
        "Study intent [Enter to acquire cohorts directly]: "
      ))
      if (is_back_signal(entered)) {
        cat("Already at the first step\n")
        next
      }
      if (nzchar(trimws(entered))) {
        studyIntent <- entered
      } else {
        studyIntent <- ""
        blank_study_intent_direct <- TRUE
      }
    } else {
      if (is.null(studyIntent) || !nzchar(trimws(studyIntent))) studyIntent <- default_intent
    }

    direct_acquisition_mode <- FALSE
    skip_intent_split_and_recommendation <- FALSE
    skip_phenotype_improvements <- FALSE
    skip_reason <- NULL
    skip_prompt_source <- if (isTRUE(interactive)) "interactive_user_choice" else "not_prompted"
    if (!isTRUE(ai_enabled)) {
      direct_acquisition_mode <- TRUE
      skip_intent_split_and_recommendation <- TRUE
      skip_phenotype_improvements <- TRUE
      skip_reason <- ai_support$reason
      skip_prompt_source <- "ai_support_policy"
    } else if (isTRUE(blank_study_intent_direct)) {
      direct_acquisition_mode <- TRUE
      skip_intent_split_and_recommendation <- TRUE
      skip_reason <- "blank_study_intent_direct_acquisition"
      skip_prompt_source <- "blank_study_intent"
    } else if (isTRUE(interactive)) {
      direct_acquisition_mode <- prompt_yesno(
        "Skip ACP intent split and enter cohort role statements directly?",
        default = FALSE
      )
      skip_intent_split_and_recommendation <- isTRUE(direct_acquisition_mode)
      if (isTRUE(direct_acquisition_mode)) {
        skip_reason <- "interactive_direct_acquisition"
      }
    }

    intent_split_path <- file.path(output_dir, "intent_split.json")
    intent_response <- NULL
    target_statement <- if (isTRUE(ai_enabled)) default_direct_statement("Target", studyIntent) else ""
    outcome_statement <- if (isTRUE(ai_enabled)) default_direct_statement("Outcome", studyIntent) else ""

    if (isTRUE(direct_acquisition_mode)) {
      if (interactive) {
        cat("\n== Step 1: Direct cohort acquisition ==\n")
        back_to_study_intent <- FALSE
        repeat {
          set_dialogue_context("intent_split", "target", context = list(study_intent = studyIntent, target_statement = target_statement, outcome_statement = outcome_statement, direct_acquisition_mode = TRUE))
          inp <- readline_with_navigation(sprintf("Target cohort statement [%s]: ", target_statement))
          if (is_back_signal(inp)) {
            back_to_study_intent <- TRUE
            break
          }
          if (nzchar(trimws(inp))) target_statement <- inp
          set_dialogue_context("intent_split", "outcome", context = list(study_intent = studyIntent, target_statement = target_statement, outcome_statement = outcome_statement, direct_acquisition_mode = TRUE))
          inp <- readline_with_navigation(sprintf("Outcome cohort statement [%s]: ", outcome_statement))
          if (is_back_signal(inp)) next
          if (nzchar(trimws(inp))) outcome_statement <- inp
          derived_study_intent <- ensure_study_intent_from_role_statements(studyIntent, target_statement, outcome_statement)
          if (is_back_signal(derived_study_intent)) next
          studyIntent <- derived_study_intent
          break
        }
        if (isTRUE(back_to_study_intent)) next
      }
    } else {
      if (interactive) {
        cat("\nConnecting to ACP...\n")
      }
      acp_connect(acpUrl)

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
    }
    if (!nzchar(trimws(target_statement))) stop("Missing target cohort statement.")
    if (!nzchar(trimws(outcome_statement))) stop("Missing outcome cohort statement.")
    studyIntent <- ensure_study_intent_from_role_statements(studyIntent, target_statement, outcome_statement)
    if (is_back_signal(studyIntent)) next
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

  selected_target_records <- list()
  selected_outcome_records <- list()
  selection_manifest_path <- file.path(output_dir, "selected_cohort_sources.json")

  repeat {
    target_source_mode <- choose_selection_source_mode("target", allow_index = isTRUE(ai_enabled) && (!isTRUE(skip_intent_split_and_recommendation) || isTRUE(direct_acquisition_mode)))
    if (is_back_signal(target_source_mode)) next

    imported_target_selection <- .studyAgentSlashAcquireImportedRoleSelection(
      source_mode = target_source_mode,
      role_label = "target",
      allow_multiple = FALSE,
      interactive = interactive,
      step_messages = list(
        database = "Step 2: Target cohort import from database",
        file = "Step 2: Target cohort import from file",
        directory = "Step 2: Target cohort import from directory"
      ),
      prompt_database_imports = prompt_database_cohort_imports,
      prompt_file_imports = prompt_file_cohort_imports,
      prompt_directory_imports = prompt_directory_cohort_imports,
      selection_record_from_import = selection_record_from_import
    )
    if (is_back_signal(imported_target_selection)) next

    if (!is.null(imported_target_selection)) {
      if (!identical(imported_target_selection$action %||% "", "handled")) next
      imported_target <- imported_target_selection$imported[[1]]
      selected_ids_target <- as.character(imported_target_selection$selected_source_ids)
      selected_target_records <- imported_target_selection$records
      cat(sprintf(
        "Imported target cohort %s from %s as source id %s.
",
        imported_target$metadata$cohort_name %||% "<unknown>",
        imported_target$metadata$source_schema %||% imported_target$metadata$source_path %||% "<unknown>",
        imported_target$source_id %||% "<unknown>"
      ))
    } else {
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
          selected_target_records <- list(selection_record_from_recommendation(recommendations_target[[idx]]))
        }
      } else {
        selected_ids_target <- recommendations_target[[1]]$phenotype_id
        selected_target_records <- list(selection_record_from_recommendation(recommendations_target[[1]]))
      }
    }

    selected_ids_target <- as.character(selected_ids_target)
    if (length(selected_ids_target) == 0) stop("No target cohort selected.")
    if (length(selected_outcome_records) == 0) selected_ids_outcome <- character(0)

    use_mapping <- FALSE
    if (interactive) {
      set_dialogue_context("incidence_design_setup", context = list(study_intent = studyIntent, target_statement = target_statement, outcome_statement = outcome_statement, selected_target_ids = as.list(selected_ids_target %||% list()), selected_outcome_ids = as.list(selected_ids_outcome %||% list())))
      use_mapping <- prompt_yesno_navigation("Map cohort IDs to a new range (avoid collisions)?", default = TRUE)
      if (is_back_signal(use_mapping)) next
    }
    cohort_id_base <- NA_integer_
    next_id <- NA_integer_
    if (use_mapping) {
      cohort_id_base <- sample(10000:50000, 1)
      if (interactive) {
        msg <- sprintf("Enter cohort ID base (10000-50000) or press Enter to use %s: ", cohort_id_base)
        set_dialogue_context("incidence_design_setup", context = list(study_intent = studyIntent, target_statement = target_statement, outcome_statement = outcome_statement, selected_target_ids = as.list(selected_ids_target %||% list()), selected_outcome_ids = as.list(selected_ids_outcome %||% list()), suggested_cohort_id_base = cohort_id_base))
        inp <- readline_with_navigation(msg)
        if (is_back_signal(inp)) next
        inp <- trimws(as.character(inp %||% ""))
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

    stop_if_unsupported_selected(selected_ids_target, "target")
    new_ids_target <- map_ids(selected_ids_target)
    copy_cohort_json_multi(selected_ids_target, new_ids_target, c(selected_target_dir, selected_dir), index_def_dir, imported_def_dir = imported_definition_dir)
    break
  }

  extract_phenotype_improvement_items <- function(resp, cohort_label) {
    core <- resp$full_result %||% resp
    if (!is.null(core$error) && nzchar(trimws(as.character(core$error)))) {
      stop(sprintf("ACP returned an error for %s phenotype improvements: %s", cohort_label, core$error))
    }
    core$phenotype_improvements %||% list()
  }

  do_target_improvements <- !isTRUE(skip_phenotype_improvements)
  if (interactive && isTRUE(do_target_improvements)) {
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


  repeat {
    outcome_source_mode <- choose_selection_source_mode("outcome", allow_index = isTRUE(ai_enabled) && (!isTRUE(skip_intent_split_and_recommendation) || isTRUE(direct_acquisition_mode)))
    if (is_back_signal(outcome_source_mode)) next

    imported_outcome_selection <- .studyAgentSlashAcquireImportedRoleSelection(
      source_mode = outcome_source_mode,
      role_label = "outcome",
      allow_multiple = TRUE,
      interactive = interactive,
      step_messages = list(
        database = "Step 5: Outcome cohort import from database",
        file = "Step 5: Outcome cohort import from file",
        directory = "Step 5: Outcome cohort import from directory"
      ),
      prompt_database_imports = prompt_database_cohort_imports,
      prompt_file_imports = prompt_file_cohort_imports,
      prompt_directory_imports = prompt_directory_cohort_imports,
      selection_record_from_import = selection_record_from_import
    )
    if (is_back_signal(imported_outcome_selection)) next

    if (!is.null(imported_outcome_selection)) {
      if (!identical(imported_outcome_selection$action %||% "", "handled")) next
      selected_outcome_records <- imported_outcome_selection$records
      selected_ids_outcome <- as.character(imported_outcome_selection$selected_source_ids)
      cat(sprintf(
        "Imported %s outcome cohort definition(s) from %s.
",
        length(selected_ids_outcome),
        outcome_source_mode
      ))
    } else {
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
        selected_outcome_records <- lapply(picks, function(label) {
          idx <- which(labels == label)[1]
          selection_record_from_recommendation(recommendations_outcome[[idx]])
        })
      } else {
        if (length(recommendations_outcome) >= 2) {
          selected_ids_outcome <- vapply(recommendations_outcome[-1], function(r) r$phenotype_id %||% NA_character_, character(1))
          selected_outcome_records <- lapply(recommendations_outcome[-1], selection_record_from_recommendation)
        } else {
          selected_ids_outcome <- vapply(recommendations_outcome, function(r) r$phenotype_id %||% NA_character_, character(1))
          selected_outcome_records <- lapply(recommendations_outcome, selection_record_from_recommendation)
        }
      }
    }

    selected_ids_outcome <- as.character(selected_ids_outcome)
    if (length(selected_ids_outcome) == 0) stop("No outcome cohorts selected.")
    stop_if_unsupported_selected(selected_ids_outcome, "outcome")
    new_ids_outcome <- map_ids(selected_ids_outcome)
    for (i in seq_along(new_ids_outcome)) {
      copy_cohort_json_multi(selected_ids_outcome[[i]], new_ids_outcome[[i]], c(selected_outcome_dir, selected_dir), index_def_dir, imported_def_dir = imported_definition_dir)
    }

    do_outcome_improvements <- !isTRUE(skip_phenotype_improvements)
    if (interactive && isTRUE(do_outcome_improvements)) {
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

  selection_manifest <- list(
    targets = selected_target_records,
    outcomes = selected_outcome_records,
    target_ids = as.list(target_ids),
    outcome_ids = as.list(outcome_ids),
    use_mapping = use_mapping,
    cohort_id_base = if (is.na(cohort_id_base)) NULL else as.integer(cohort_id_base)
  )
  write_json(selection_manifest, selection_manifest_path)

  cohort_csv <- file.path(selected_dir, "Cohorts.csv")
  cohort_rows <- list()
  if (length(new_ids_target) > 0) {
    for (i in seq_along(new_ids_target)) {
      cid <- selected_ids_target[[i]]
      new_id <- new_ids_target[[i]]
      rec <- selected_target_records[[i]] %||% list()
      cohort_rows[[length(cohort_rows) + 1]] <- data.frame(
        atlas_id = cid,
        cohort_id = new_id,
        cohort_name = rec$cohort_name %||% paste0("Cohort ", new_id),
        logic_description = rec$logic_description %||% NA_character_,
        generate_stats = TRUE,
        stringsAsFactors = FALSE
      )
    }
  }
  if (length(new_ids_outcome) > 0) {
    for (i in seq_along(new_ids_outcome)) {
      cid <- selected_ids_outcome[[i]]
      new_id <- new_ids_outcome[[i]]
      rec <- selected_outcome_records[[i]] %||% list()
      cohort_rows[[length(cohort_rows) + 1]] <- data.frame(
        atlas_id = cid,
        cohort_id = new_id,
        cohort_name = rec$cohort_name %||% paste0("Cohort ", new_id),
        logic_description = rec$logic_description %||% NA_character_,
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
    ai_support_mode = ai_support$mode,
    ai_support_reason = ai_support$reason,
    acp_capability_status = if (isTRUE(ai_enabled)) "enabled" else "disabled_by_user",
    skip_intent_split_and_recommendation = isTRUE(skip_intent_split_and_recommendation),
    skip_phenotype_improvements = isTRUE(skip_phenotype_improvements),
    direct_acquisition_mode = isTRUE(direct_acquisition_mode),
    skip_reason = skip_reason,
    skip_prompt_source = skip_prompt_source,
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
    imported_definition_dir = imported_definition_dir,
    intent_split_path = intent_split_path,
    recommendations_target_path = recs_target_path,
    recommendations_outcome_path = recs_outcome_path,
    improvements_target_path = improvements_target_path,
    improvements_outcome_path = improvements_outcome_path,
    cohort_csv = cohort_csv,
    cohort_id_map = id_map,
    cohort_id_base = cohort_id_base,
    cohort_roles_path = roles_path,
    selection_manifest_path = selection_manifest_path,
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

  runtime_template_paths <- .studyAgentSlashSeedRuntimeTemplates(base_dir, write_json = write_json)
  db_details_path <- runtime_template_paths$db_details_path
  cohort_source_db_details_path <- runtime_template_paths$cohort_source_db_details_path
  execution_settings_path <- runtime_template_paths$execution_settings_path
  state$strategus_db_details_path <- db_details_path
  state$strategus_cohort_source_db_details_path <- cohort_source_db_details_path
  state$strategus_execution_settings_path <- execution_settings_path
  write_json(state, state_path)

  keeper_concept_set_state_path <- file.path(output_dir, "keeper_concept_set_state.json")
  keeper_case_review_state_path <- file.path(output_dir, "keeper_case_review_state.json")
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
  keeper_concept_set_ran <- FALSE
  keeper_case_review_ran <- FALSE
  keeper_concept_set_result <- NULL
  keeper_case_review_result <- NULL

  if (isTRUE(interactive) && isTRUE(ai_enabled)) {
    repeat {
      cat("
Keeper review uses the local DB and execution settings files:
")
      cat(sprintf("  - DB details: %s
", db_details_path))
      cat(sprintf("  - Execution settings: %s
", execution_settings_path))
      run_keeper_review_now <- prompt_yesno_navigation("Run Keeper review now after reviewing those files?", default = FALSE)
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
        keeper_config_confirmed <- FALSE
        repeat {
          entered_roles <- readline_with_navigation("Keeper review roles [outcome]: ")
          if (is_back_signal(entered_roles)) next
          entered_roles <- trimws(as.character(entered_roles %||% ""))
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
            keeper_reuse_generated_artifacts <- prompt_yesno_navigation("Reuse existing Keeper generated artifacts?", default = TRUE)
            if (is_back_signal(keeper_reuse_generated_artifacts)) next
          }
          if (has_keeper_generated_artifacts || has_keeper_approved_artifacts) {
            keeper_overwrite_approved_concept_sets <- prompt_yesno_navigation("Replace approved concept sets with current generated output?", default = FALSE)
            if (is_back_signal(keeper_overwrite_approved_concept_sets)) next
          }
          if (has_keeper_review_artifacts) {
            keeper_resume_reviews <- prompt_yesno_navigation("Resume existing Keeper row reviews?", default = TRUE)
            if (is_back_signal(keeper_resume_reviews)) next
          }
          entered_row_selection <- readline_with_navigation("Keeper row selection [default first N or e.g. 1-3,5]: ")
          if (is_back_signal(entered_row_selection)) next
          entered_row_selection <- trimws(as.character(entered_row_selection %||% ""))
          keeper_review_row_selection <- if (!nzchar(entered_row_selection)) NULL else entered_row_selection
          keeper_config_confirmed <- TRUE
          break
        }

        if (!isTRUE(keeper_config_confirmed)) next

        stage_callback <- function(step, role = "", context = list()) {
          safe_context <- c(
            list(
              study_intent = studyIntent,
              target_statement = target_statement,
              outcome_statement = outcome_statement,
              selected_target_ids = as.list(target_ids),
              selected_outcome_ids = as.list(outcome_ids),
              keeper_concept_set_state_path = keeper_concept_set_state_path,
              keeper_case_review_state_path = keeper_case_review_state_path,
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

        keeper_concept_set_result <- tryCatch(
          runKeeperConceptSetWorkflow(
            base_dir = base_dir,
            execution_settings_path = execution_settings_path,
            cohort_id_map_path = file.path(output_dir, "cohort_id_map.json"),
            cohort_roles_path = roles_path,
            intent_path = intent_split_path,
            acp_timeout_seconds = keeper_acp_timeout_seconds,
            review_roles = keeper_review_roles,
            candidate_limit = keeper_candidate_limit,
            min_record_count = keeper_min_record_count,
            overwrite_approved_concept_sets = keeper_overwrite_approved_concept_sets,
            reuse_generated_concept_sets = keeper_reuse_generated_artifacts,
            stage_callback = stage_callback,
            stage_gate = keeper_stage_gate
          ),
          error = function(e) e
        )

        if (inherits(keeper_concept_set_result, "error")) {
          cat(sprintf("Keeper concept-set workflow failed: %s
", conditionMessage(keeper_concept_set_result)))
        } else if (identical(keeper_concept_set_result$status %||% "ok", "error")) {
          error_count <- as.integer(keeper_concept_set_result$error_count %||% 0L)
          cat(sprintf("Keeper concept-set workflow encountered %s ACP error(s).
", error_count))
          if (length(keeper_concept_set_result$errors %||% list())) {
            first_error <- keeper_concept_set_result$errors[[1]]
            cat(sprintf("First ACP error: %s
", first_error$message %||% "unknown ACP error"))
          }
          cat(sprintf("Keeper concept-set state saved to: %s
", keeper_concept_set_state_path))
        } else {
          keeper_concept_set_ran <- TRUE
          cat(sprintf("Keeper concept-set state saved to: %s
", keeper_concept_set_state_path))
          proceed_case_review <- prompt_yesno("Proceed to Keeper case review now?", default = TRUE)
          if (isTRUE(proceed_case_review)) {
            keeper_case_review_result <- tryCatch(
              runKeeperCaseReviewWorkflow(
                base_dir = base_dir,
                execution_settings_path = execution_settings_path,
                cohort_id_map_path = file.path(output_dir, "cohort_id_map.json"),
                cohort_roles_path = roles_path,
                intent_path = intent_split_path,
                acp_timeout_seconds = keeper_acp_timeout_seconds,
                review_roles = keeper_review_roles,
                sample_size = keeper_sample_size,
                review_row_limit = keeper_review_row_limit,
                reuse_rows = keeper_reuse_generated_artifacts,
                resume_reviews = keeper_resume_reviews,
                review_row_selection = keeper_review_row_selection,
                remove_pii = TRUE,
                stage_callback = stage_callback,
                stage_gate = keeper_stage_gate
              ),
              error = function(e) e
            )
            if (inherits(keeper_case_review_result, "error")) {
              cat(sprintf("Keeper case review failed: %s
", conditionMessage(keeper_case_review_result)))
            } else if (identical(keeper_case_review_result$status %||% "ok", "error")) {
              error_count <- as.integer(keeper_case_review_result$error_count %||% 0L)
              cat(sprintf("Keeper case review encountered %s ACP error(s).
", error_count))
              if (length(keeper_case_review_result$errors %||% list())) {
                first_error <- keeper_case_review_result$errors[[1]]
                cat(sprintf("First ACP error: %s
", first_error$message %||% "unknown ACP error"))
              }
              cat(sprintf("Keeper case-review state saved to: %s
", keeper_case_review_state_path))
            } else {
              keeper_case_review_ran <- TRUE
              cat(sprintf("Keeper case-review state saved to: %s
", keeper_case_review_state_path))
            }
          }
        }
        set_dialogue_context("workflow_summary", context = list(
          study_intent = studyIntent,
          keeper_concept_set_state_path = keeper_concept_set_state_path,
          keeper_case_review_state_path = keeper_case_review_state_path
        ))
      }
      break
    }
  }

  state$keeper_concept_set_state_path <- keeper_concept_set_state_path
  state$keeper_case_review_state_path <- keeper_case_review_state_path
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
  state$keeper_concept_set_ran <- isTRUE(keeper_concept_set_ran)
  state$keeper_case_review_ran <- isTRUE(keeper_case_review_ran)
  state$keeper_concept_set_status <- if (inherits(keeper_concept_set_result, "error")) "error" else as.character(keeper_concept_set_result$status %||% if (isTRUE(keeper_concept_set_ran)) "ok" else "not_run")
  state$keeper_case_review_status <- if (inherits(keeper_case_review_result, "error")) "error" else as.character(keeper_case_review_result$status %||% if (isTRUE(keeper_case_review_ran)) "ok" else "not_run")
  state$keeper_concept_set_error_count <- if (inherits(keeper_concept_set_result, "error")) 1L else as.integer(keeper_concept_set_result$error_count %||% 0L)
  state$keeper_case_review_error_count <- if (inherits(keeper_case_review_result, "error")) 1L else as.integer(keeper_case_review_result$error_count %||% 0L)
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
    "phenotype_definition_path <- function(phenotype_id, index_def_dir, imported_def_dir = NULL) {",
    "  phenotype_id <- as.character(phenotype_id %||% '')",
    "  if (grepl('^db:[A-Za-z][A-Za-z0-9_]*:[0-9]+$', phenotype_id)) {",
    "    if (is.null(imported_def_dir) || !nzchar(imported_def_dir)) stop('Missing imported cohort definition cache directory.')",
    "    return(file.path(imported_def_dir, sprintf('%s.json', gsub(':', '__', phenotype_id, fixed = TRUE))))",
    "  }",
    "  file.path(index_def_dir, sprintf('%s.json', gsub(':', '__', phenotype_id, fixed = TRUE)))",
    "}",
    "stop_if_unsupported_selected <- function(phenotype_ids, role_label) {",
    "  supported <- grepl('^ohdsi:[0-9]+$', phenotype_ids %||% character(0)) | grepl('^db:[A-Za-z][A-Za-z0-9_]*:[0-9]+$', phenotype_ids %||% character(0))",
    "  unsupported <- phenotype_ids[!supported]",
    "  if (length(unsupported) > 0) stop(sprintf('Selected %s cohort source ids include unsupported values (%s).', role_label, paste(unique(unsupported), collapse = ', ')))",
    "}",
    "copy_cohort_json <- function(source_id, dest_id, dest_dirs, index_def_dir, imported_def_dir = NULL) {",
    "  src <- phenotype_definition_path(source_id, index_def_dir, imported_def_dir = imported_def_dir)",
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
    "imported_def_dir <- file.path(base_dir, 'imported-cohort-definitions')",
    "selected_dir <- file.path(base_dir, 'selected-cohorts')",
    "selected_target_dir <- file.path(base_dir, 'selected-target-cohorts')",
    "selected_outcome_dir <- file.path(base_dir, 'selected-outcome-cohorts')",
    "selection_manifest_path <- file.path(output_dir, 'selected_cohort_sources.json')",
    "dir.create(selected_dir, recursive = TRUE, showWarnings = FALSE)",
    "dir.create(selected_target_dir, recursive = TRUE, showWarnings = FALSE)",
    "dir.create(selected_outcome_dir, recursive = TRUE, showWarnings = FALSE)",
    "if (!file.exists(selection_manifest_path)) stop('Missing selection manifest: ', selection_manifest_path)",
    "selection_manifest <- jsonlite::fromJSON(selection_manifest_path, simplifyVector = FALSE)",
    "target_records <- selection_manifest$targets %||% list()",
    "outcome_records <- selection_manifest$outcomes %||% list()",
    "target_ids <- vapply(target_records, function(item) as.character(item$source_id %||% ''), character(1))",
    "outcome_ids <- vapply(outcome_records, function(item) as.character(item$source_id %||% ''), character(1))",
    "new_ids_target <- suppressWarnings(as.integer(unlist(selection_manifest$target_ids %||% integer(0), use.names = FALSE)))",
    "new_ids_outcome <- suppressWarnings(as.integer(unlist(selection_manifest$outcome_ids %||% integer(0), use.names = FALSE)))",
    "if (length(target_ids) == 0) stop('No target cohort selected.')",
    "if (length(outcome_ids) == 0) stop('No outcome cohorts selected.')",
    "if (length(target_ids) != length(new_ids_target)) stop('Selection manifest target_ids are inconsistent.')",
    "if (length(outcome_ids) != length(new_ids_outcome)) stop('Selection manifest outcome_ids are inconsistent.')",
    "stop_if_unsupported_selected(target_ids, 'target')",
    "stop_if_unsupported_selected(outcome_ids, 'outcome')",
    "for (i in seq_along(target_ids)) copy_cohort_json(target_ids[[i]], new_ids_target[[i]], c(selected_target_dir, selected_dir), index_def_dir, imported_def_dir = imported_def_dir)",
    "for (i in seq_along(outcome_ids)) copy_cohort_json(outcome_ids[[i]], new_ids_outcome[[i]], c(selected_outcome_dir, selected_dir), index_def_dir, imported_def_dir = imported_def_dir)",
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
    "  rec <- target_records[[i]] %||% list()",
    "  cohort_rows[[length(cohort_rows) + 1]] <- data.frame(atlas_id = cid, cohort_id = new_id, cohort_name = rec$cohort_name %||% paste0('Cohort ', new_id), logic_description = rec$logic_description %||% NA_character_, generate_stats = TRUE, stringsAsFactors = FALSE)",
    "}",
    "for (i in seq_along(new_ids_outcome)) {",
    "  cid <- outcome_ids[[i]]",
    "  new_id <- new_ids_outcome[[i]]",
    "  rec <- outcome_records[[i]] %||% list()",
    "  cohort_rows[[length(cohort_rows) + 1]] <- data.frame(atlas_id = cid, cohort_id = new_id, cohort_name = rec$cohort_name %||% paste0('Cohort ', new_id), logic_description = rec$logic_description %||% NA_character_, generate_stats = TRUE, stringsAsFactors = FALSE)",
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

  # 04 - Keeper concept sets
  script_04 <- c(
    script_header,
    "library(jsonlite)",
    "`%||%` <- function(x, y) if (is.null(x)) y else x",
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
    "# Edit these defaults as needed before running the ACP-based Keeper concept-set workflow.",
    "review_roles <- c('outcome')",
    "domain_keys <- c(",
    "  'doi', 'drugs'",
    ") # NOTE: you could also add 'alternativeDiagnosis', 'symptoms', 'diagnosticProcedures', 'measurements', 'treatmentProcedures', and 'complications' but need to increase the ACP_TIMEOUT env variable 3-5 minutes per domain",
    "candidate_limit <- 5",
    "acp_timeout_seconds <- as.numeric(Sys.getenv('ACP_TIMEOUT', '300'))",
    "Sys.setenv(ACP_TIMEOUT = as.character(acp_timeout_seconds))",
    "reuse_generated_concept_sets <- TRUE",
    "overwrite_approved_concept_sets <- FALSE",
    "acp_url <- Sys.getenv('ACP_URL', 'http://127.0.0.1:8765')",
    "",
    "result <- slashOhdsiStrategusAssistant::runKeeperConceptSetWorkflow(",
    "  base_dir = base_dir,",
    "  execution_settings_path = execution_settings_path,",
    "  cohort_id_map_path = cohort_id_map_path,",
    "  cohort_roles_path = cohort_roles_path,",
    "  intent_path = intent_path,",
    "  acp_url = acp_url,",
    "  acp_timeout_seconds = acp_timeout_seconds,",
    "  review_roles = review_roles,",
    "  domain_keys = domain_keys,  # NOTE: full set of options are as follows but set the ACP_TIMEOUT to be > 10 minutes before attempting all of them: doi, alternativeDiagnosis, symptoms, drugs, diagnosticProcedures, measurements, treatmentProcedures, complications",
    "  candidate_limit = candidate_limit,",
    "  overwrite_approved_concept_sets = overwrite_approved_concept_sets,",
    "  reuse_generated_concept_sets = reuse_generated_concept_sets",
    ")",
    "keeper_state_path <- file.path(output_dir, 'keeper_concept_set_state.json')",
    "if (identical(result$status %||% 'ok', 'error')) {",
    "  stop(sprintf('Keeper concept-set workflow encountered %s ACP error(s). See %s for details.', as.integer(result$error_count %||% 0L), keeper_state_path))",
    "}",
    "message('Keeper concept-set state saved to: ', keeper_state_path)",
    "print(result)",
    ""
  )
  if (isTRUE(ai_enabled)) write_lines(file.path(scripts_dir, "04_keeper_concept_sets.R"), script_04)

  # 05 - Keeper case review
  script_05 <- c(
    script_header,
    "library(jsonlite)",
    "`%||%` <- function(x, y) if (is.null(x)) y else x",
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
    "review_roles <- c('outcome')",
    "sample_size <- 5",
    "review_row_limit <- 5",
    "acp_timeout_seconds <- as.numeric(Sys.getenv('ACP_TIMEOUT', '300'))",
    "Sys.setenv(ACP_TIMEOUT = as.character(acp_timeout_seconds))",
    "reuse_rows <- FALSE",
    "resume_reviews <- TRUE",
    "review_row_selection <- NULL  # e.g. '1-3,5'",
    "acp_url <- Sys.getenv('ACP_URL', 'http://127.0.0.1:8765')",
    "",
    "result <- slashOhdsiStrategusAssistant::runKeeperCaseReviewWorkflow(",
    "  base_dir = base_dir,",
    "  execution_settings_path = execution_settings_path,",
    "  cohort_id_map_path = cohort_id_map_path,",
    "  cohort_roles_path = cohort_roles_path,",
    "  intent_path = intent_path,",
    "  acp_url = acp_url,",
    "  acp_timeout_seconds = acp_timeout_seconds,",
    "  review_roles = review_roles,",
    "  sample_size = sample_size,",
    "  review_row_limit = review_row_limit,",
    "  reuse_rows = reuse_rows,",
    "  resume_reviews = resume_reviews,",
    "  review_row_selection = review_row_selection,",
    "  remove_pii = TRUE",
    ")",
    "keeper_state_path <- file.path(output_dir, 'keeper_case_review_state.json')",
    "if (identical(result$status %||% 'ok', 'error')) {",
    "  stop(sprintf('Keeper case-review workflow encountered %s ACP error(s). See %s for details.', as.integer(result$error_count %||% 0L), keeper_state_path))",
    "}",
    "message('Keeper case-review state saved to: ', keeper_state_path)",
    "print(result)",
    ""
  )
  if (isTRUE(ai_enabled)) write_lines(file.path(scripts_dir, "05_keeper_case_review.R"), script_05)

  # 06 - diagnostics
  script_06 <- c(
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
  write_lines(file.path(scripts_dir, "06_diagnostics.R"), script_06)

  # 07 - incidence spec
  script_07 <- c(
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
    "runtime_report <- slashOhdsiStrategusAssistant::checkStrategusRuntime()",
    "jsonlite::write_json(runtime_report, file.path(analysis_settings_dir, 'hades-runtime.json'), pretty = TRUE, auto_unbox = TRUE, null = 'null')",
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
    "resolve_path <- function(path) {",
    "  path <- trimws(as.character(path %||% \"\"))",
    "  if (!nzchar(path)) stop(\"Configured execution root must not be empty.\")",
    "  if (grepl('^(?:/|~|[A-Za-z]:)', path)) return(normalizePath(path, winslash = '/', mustWork = FALSE))",
    "  normalizePath(file.path(base_dir, path), winslash = \"/\", mustWork = FALSE)",
    "}",
    "validate_execution_root <- function(label, root_path) {",
    "  normalized_root <- normalizePath(resolve_path(as.character(root_path %||% '')), winslash = '/', mustWork = FALSE)",
    "  normalized_base <- normalizePath(base_dir, winslash = '/', mustWork = FALSE)",
    "  if (startsWith(normalized_root, paste0(normalized_base, '/')) || identical(normalized_root, normalized_base)) {",
    "    return(normalized_root)",
    "  }",
    "  parent_dir <- dirname(normalized_root)",
    "  marker_path <- file.path(parent_dir, 'study-agent-project.json')",
    "  if (file.exists(marker_path) && !identical(normalizePath(parent_dir, winslash = '/', mustWork = FALSE), normalized_base)) {",
    "    stop(sprintf('Configured %s points to another Study Agent project: %s (current project: %s)', label, normalized_root, normalized_base))",
    "  }",
    "  warning(sprintf('Configured %s is outside the current project root: %s', label, normalized_root), call. = FALSE)",
    "  normalized_root",
    "}",
    "summarize_execute_result <- function(result) {",
    "  modules <- if (is.list(result)) lapply(result, function(item) {",
    "    status <- as.character(item$status %||% '')",
    "    module_name <- as.character(item$moduleName %||% '')",
    "    error_message <- trimws(as.character(item$errorMessage %||% ''))",
    "    if (identical(status, 'FAILED') && !nzchar(error_message)) {",
    "      error_message <- sprintf('%s failed with empty errorMessage; inspect work/results roots and exported tables.', if (nzchar(module_name)) module_name else 'Strategus module')",
    "    }",
    "    list(module_name = module_name, status = status, execution_time = as.character(item$executionTime %||% ''), error_message = error_message)",
    "  }) else list()",
    "  statuses <- vapply(modules, function(item) as.character(item$status %||% ''), character(1))",
    "  overall_status <- if (length(statuses) == 0) {",
    "    'unknown'",
    "  } else if (any(statuses %in% c('FAILED', 'ERROR'))) {",
    "    'partial_failure'",
    "  } else if (all(statuses %in% c('SUCCESS', 'COMPLETED'))) {",
    "    'success'",
    "  } else {",
    "    'mixed'",
    "  }",
    "  list(overall_status = overall_status, results_root = resolved_results_root, work_root = resolved_work_root, modules = modules)",
    "}",
    "resolved_results_root <- validate_execution_root('resultsFolder', exec$resultsFolder %||% '')",
    "resolved_work_root <- validate_execution_root('workFolder', exec$workFolder %||% '')",
    "message('Strategus execution roots:')",
    "message('  resultsFolder: ', resolved_results_root)",
    "message('  workFolder: ', resolved_work_root)",
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
    "result <- execute(",
    "  analysisSpecifications = analysisSpecifications,",
    "  executionSettings = executionSettings_incidence,",
    "  connectionDetails = connectionDetails",
    ")",
    "result_path <- file.path(analysis_settings_dir, 'strategus_execute_result.rds')",
    "saveRDS(result, result_path)",
    "summary_path <- file.path(analysis_settings_dir, 'strategus_execute_summary.json')",
    "jsonlite::write_json(summarize_execute_result(result), summary_path, pretty = TRUE, auto_unbox = TRUE, null = 'null')",
    "message('Strategus execution result saved to: ', result_path)",
    "message('Strategus execution summary saved to: ', summary_path)",
    ""
  )
  write_lines(file.path(scripts_dir, "07_incidence_spec.R"), script_07)

  script_08 <- c(
    script_header,
    "library(jsonlite)",
    "`%||%` <- function(x, y) if (is.null(x)) y else x",
    "",
    "if (!requireNamespace('CohortDiagnostics', quietly = TRUE)) {",
    "  stop('CohortDiagnostics is required to launch the diagnostics explorer.')",
    "}",
    "",
    sprintf("base_dir <- '%s'", base_dir),
    "execution_settings_path <- file.path(base_dir, 'strategus-execution-settings.json')",
    "resolve_path <- function(path) {",
    "  path <- trimws(as.character(path %||% \"\"))",
    "  if (!nzchar(path)) stop(\"Configured execution root must not be empty.\")",
    "  if (grepl('^(?:/|~|[A-Za-z]:)', path)) return(normalizePath(path, winslash = '/', mustWork = FALSE))",
    "  normalizePath(file.path(base_dir, path), winslash = \"/\", mustWork = FALSE)",
    "}",
    "exec_cfg <- jsonlite::fromJSON(execution_settings_path, simplifyVector = FALSE)",
    "results_root <- normalizePath(resolve_path(as.character(exec_cfg$resultsFolder %||% '')), winslash = '/', mustWork = FALSE)",
    "diagnostics_dir <- file.path(results_root, 'CohortDiagnosticsModule')",
    "if (!dir.exists(diagnostics_dir)) {",
    "  stop('Diagnostics results directory not found: ', diagnostics_dir, '. Run 06_diagnostics.R first.')",
    "}",
    "sqlite_db_path <- file.path(diagnostics_dir, 'MergedCohortDiagnosticsData.sqlite')",
    "if (!file.exists(sqlite_db_path)) {",
    "  if (!'createMergedResultsFile' %in% getNamespaceExports('CohortDiagnostics')) {",
    "    stop('Merged diagnostics SQLite is missing and CohortDiagnostics::createMergedResultsFile is not available in this installation.')",
    "  }",
    "  message('Creating merged diagnostics SQLite at: ', sqlite_db_path)",
    "  CohortDiagnostics::createMergedResultsFile(",
    "    dataFolder = diagnostics_dir,",
    "    sqliteDbPath = sqlite_db_path,",
    "    overwrite = FALSE",
    "  )",
    "}",
    "if (!file.exists(sqlite_db_path)) {",
    "  stop('Merged diagnostics SQLite was not created: ', sqlite_db_path)",
    "}",
    "launch_fun <- getExportedValue('CohortDiagnostics', 'launchDiagnosticsExplorer')",
    "call_with_supported_args <- function(fn, args) {",
    "  formal_names <- names(formals(fn)) %||% character(0)",
    "  if (!('...' %in% formal_names)) {",
    "    args <- args[names(args) %in% formal_names]",
    "  }",
    "  do.call(fn, args)",
    "}",
    "launch_args <- list(sqliteDbPath = sqlite_db_path, launch.browser = interactive())",
    "launched <- FALSE",
    "last_error <- NULL",
    "tryCatch({",
    "  call_with_supported_args(launch_fun, launch_args)",
    "  launched <- TRUE",
    "}, error = function(e) {",
    "  last_error <<- conditionMessage(e)",
    "})",
    "if (!launched) {",
    "  stop('Unable to launch Diagnostics Explorer for ', diagnostics_dir, if (!is.null(last_error)) paste0(': ', last_error) else '', '. Run this script in a second R session if you want to keep the workflow shell and /ohdsi available.')",
    "}",
    "message('Diagnostics Explorer launched for: ', diagnostics_dir)",
    "message('Merged SQLite: ', sqlite_db_path)",
    "message('Run this script in a second R session if you want to keep the workflow shell and /ohdsi available.')",
    ""
  )
  write_lines(file.path(scripts_dir, "08_launch_diagnostics_explorer.R"), script_08)
  script_09 <- c(script_header, sprintf("slashOhdsiStrategusAssistant::launchStrategusArtifactBrowser('%s')", base_dir))
  write_lines(file.path(scripts_dir, "09_launch_artifact_browser.R"), script_09)

  project_init <- .studyAgentSlashInitializeProjectFiles(
    workflow_type = "strategus_incidence",
    base_dir = base_dir,
    output_dir = output_dir,
    scripts_dir = scripts_dir,
    execution_plan = .studyAgentSlashBuildIncidenceExecutionPlan(),
    study_context = list(
      study_intent = studyIntent,
      ai_support_mode = ai_support$mode,
      target_statement = target_statement,
      outcome_statement = outcome_statement,
      selected_target_ids = as.list(new_ids_target),
      selected_outcome_ids = as.list(new_ids_outcome),
      time_at_risk_settings_path = time_at_risk_settings_path,
      improvements_applied = improvements_applied
    ),
    dialogue_context = list(
      current_step = "workflow_summary",
      study_intent = studyIntent,
      target_statement = target_statement,
      outcome_statement = outcome_statement
    ),
    artifact_specs = list(
      list(id = "legacy_state", path = state_path, type = "legacy_state", status = "written"),
      list(id = "db_details", path = db_details_path, type = "config", status = "written"),
      list(id = "execution_settings", path = execution_settings_path, type = "config", status = "written"),
      list(id = "cohort_roles", path = roles_path, type = "metadata", status = "written"),
      list(id = "time_at_risk_settings", path = time_at_risk_settings_path, type = "analysis_settings", status = "written")
    ),
    shell_session_metadata = list(shell = "runStrategusIncidenceShell", interactive = interactive)
  )
  build_completed_steps <- c("recommend_and_select")
  build_skipped_steps <- character(0)
  build_failed_steps <- character(0)
  if (isTRUE(improvements_applied)) {
    build_completed_steps <- c(build_completed_steps, "apply_improvements")
  } else {
    build_skipped_steps <- c(build_skipped_steps, "apply_improvements")
  }
  if (identical(state$keeper_concept_set_status %||% "not_run", "ok")) {
    build_completed_steps <- c(build_completed_steps, "keeper_concept_sets")
  } else if (identical(state$keeper_concept_set_status %||% "not_run", "error")) {
    build_failed_steps <- c(build_failed_steps, "keeper_concept_sets")
  } else if (!isTRUE(ai_enabled)) {
    build_skipped_steps <- c(build_skipped_steps, "keeper_concept_sets")
  }
  if (identical(state$keeper_case_review_status %||% "not_run", "ok")) {
    build_completed_steps <- c(build_completed_steps, "keeper_case_review")
  } else if (identical(state$keeper_case_review_status %||% "not_run", "error")) {
    build_failed_steps <- c(build_failed_steps, "keeper_case_review")
  } else if (!isTRUE(ai_enabled)) {
    build_skipped_steps <- c(build_skipped_steps, "keeper_case_review")
  }
  project_init <- .studyAgentSlashFinalizeBuildProjectState(
    base_dir = base_dir,
    completed_steps = build_completed_steps,
    skipped_steps = build_skipped_steps,
    failed_steps = build_failed_steps
  )
  project_init$project_state <- .studyAgentSlashPersistExecutionRoots(
    base_dir = base_dir,
    project_state = project_init$project_state %||% NULL,
    source = "project_init",
    write = TRUE
  )
  state$project_state_path <- project_state_path
  state$runtime_state_path <- runtime_state_path
  write_json(state, state_path)

  if (interactive) {
    cat("\n== Session Summary ==\n")
    cat("Target cohort statement:\n")
    cat(sprintf("  %s\n", target_statement))
    cat("Outcome cohort statement:\n")
    cat(sprintf("  %s\n", outcome_statement))
    cat("Target cohorts:\n")
    for (i in seq_along(new_ids_target)) {
      rec <- selected_target_records[[i]] %||% list()
      cat(sprintf("  - %s (source %s -> cohort %s)\n", rec$cohort_name %||% "<unknown>", selected_ids_target[[i]], new_ids_target[[i]]))
    }
    cat("Outcome cohorts:\n")
    for (i in seq_along(new_ids_outcome)) {
      rec <- selected_outcome_records[[i]] %||% list()
      cat(sprintf("  - %s (source %s -> cohort %s)\n", rec$cohort_name %||% "<unknown>", selected_ids_outcome[[i]], new_ids_outcome[[i]]))
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
    cat("  2) Rscript scripts/04_keeper_concept_sets.R\n")
    cat("  3) Rscript scripts/05_keeper_case_review.R\n")
    cat("  4) Rscript scripts/06_diagnostics.R\n")
    cat("  5) Rscript scripts/07_incidence_spec.R\n")
    cat("Artifact browser (optional, run in second R session):\n")
    cat("  - Rscript scripts/09_launch_artifact_browser.R\n")
    cat("Optional diagnostics viewer (run in a second R session):\n")
    cat("  - Rscript scripts/08_launch_diagnostics_explorer.R\n")
    cat("Notes:\n")
    if (improvements_applied) {
      cat("  - Improvements were already applied in this session; scripts are a portable record.\n")
    } else {
      cat("  - Improvements were not applied; see scripts/02_apply_improvements.R if desired.\n")
    }
    cat(sprintf("Session state saved to %s\n", state_path))
    cat(sprintf("Project manifest saved to %s\n", project_state_path))
    cat(sprintf("Runtime state saved to %s\n", runtime_state_path))
  }
  run_execution_menu(prompt_first = interactive)
  message("Study agent shell complete. Scripts written to: ", scripts_dir)
  invisible(list(
    output_dir = output_dir,
    scripts_dir = scripts_dir,
    intent_split = intent_split_path,
    recommendations_target = recs_target_path,
    recommendations_outcome = recs_outcome_path,
    improvements_target = improvements_target_path,
    improvements_outcome = improvements_outcome_path,
    cohort_csv = cohort_csv,
    project_state = project_state_path,
    runtime_state = runtime_state_path
  ))
}
