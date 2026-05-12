#' Apply LLM-proposed actions to a concept set via ACP
#' @param conceptSetRef path to local concept set JSON
#' @param actions list of action objects
#' @param preview logical; TRUE = dry run
#' @param overwrite logical; if FALSE, ACP may choose a versioned path
#' @param backup logical; if TRUE and overwrite=TRUE, create timestamped backup
#' @return list server response
#' @export
applyLLMActionsConceptSet <- function(conceptSetRef,
                                      actions,
                                      preview = TRUE,
                                      overwrite = FALSE,
                                      backup = TRUE) {
  client <- acp_get_default_client()
  if (is.null(client)) stop("ACP not connected; call acp_connect() first.")
  acp_execute_llm_actions_concept_set(
    client = client,
    concept_set_ref = conceptSetRef,
    actions = actions %||% list(),
    write = !isTRUE(preview),
    overwrite = isTRUE(overwrite),
    backup = isTRUE(backup)
  )
}

#' Propose includeDescendants patch for concept set
#' @param conceptSetRef path or URL to concept_set.json
#' @return list patch payload
#' @export
proposeIncludeDescendantsPatch <- function(conceptSetRef) {
  payload <- list(
    artifactRef = conceptSetRef,
    ops = list(list(
      op = "set_include_descendants",
      where = list(domainId = "Drug", conceptClassId = "Ingredient", includeDescendants = FALSE),
      value = TRUE
    )),
    write = FALSE
  )

  client <- acp_get_default_client()
  if (!is.null(client)) {
    res <- acp_concept_set_edit(
      client = client,
      artifact_ref = conceptSetRef,
      ops = payload$ops,
      write = FALSE
    )
    if (is.null(res$ops)) res$ops <- payload$ops
    res$artifactRef <- conceptSetRef
    return(res)
  }

  res <- local_apply_concept_set_action(payload, write = FALSE)
  res$ops <- payload$ops
  res$artifactRef <- conceptSetRef
  res
}

#' Preview concept set patch
#' @param conceptSetRef path or URL
#' @param patch patch object from proposeIncludeDescendantsPatch
#' @return preview result
#' @export
previewConceptSetPatch <- function(conceptSetRef, patch) {
  if (!is.null(patch$actions)) {
    prev <- applyLLMActionsConceptSet(conceptSetRef, patch$actions, preview = TRUE)
    cat(prev$plan %||% "LLM actions preview", "\n")
    if (length(prev$preview_changes %||% list()) == 0) {
      cat("No matching items found.\n")
      return(invisible(prev))
    }
    df <- do.call(rbind, lapply(prev$preview_changes, as.data.frame))
    print(df)
    return(invisible(prev))
  }

  if (is.null(patch$preview_changes)) {
    cat("No preview available.\n")
    return(invisible(NULL))
  }

  cat(patch$plan %||% "", "\n")
  if (length(patch$preview_changes) == 0) {
    cat("No matching items found.\n")
    return(invisible(NULL))
  }
  df <- do.call(rbind, lapply(patch$preview_changes, as.data.frame))
  print(df)
  invisible(df)
}

#' Apply concept set patch
#' @param conceptSetRef path or URL
#' @param patch patch object
#' @param backup logical; if TRUE, create .bak before overwrite
#' @param outputPath optional output path
#' @param useActions optional override for action mode
#' @param overwrite logical; overwrite source path in action mode
#' @return result list
#' @export
applyConceptSetPatch <- function(conceptSetRef,
                                 patch,
                                 backup = TRUE,
                                 outputPath = NULL,
                                 useActions = NULL,
                                 overwrite = TRUE) {
  if (is.null(useActions)) useActions <- !is.null(patch$actions)
  if (isTRUE(useActions)) {
    res <- applyLLMActionsConceptSet(
      conceptSetRef,
      patch$actions %||% list(),
      preview = FALSE,
      overwrite = overwrite,
      backup = backup
    )
    return(invisible(res))
  }

  patch$write <- TRUE
  patch$artifactRef <- conceptSetRef
  patch$backup <- backup
  if (!is.null(outputPath)) patch$outputPath <- outputPath
  if (is.null(patch$ops)) {
    patch$ops <- list(list(
      op = "set_include_descendants",
      where = list(domainId = "Drug", conceptClassId = "Ingredient", includeDescendants = FALSE),
      value = TRUE
    ))
  }

  pre_hash <- tryCatch(tools::md5sum(conceptSetRef), error = function(e) NA_character_)
  client <- acp_get_default_client()
  res <- if (!is.null(client)) {
    acp_concept_set_edit(
      client = client,
      artifact_ref = conceptSetRef,
      ops = patch$ops,
      write = TRUE,
      backup = backup,
      output_path = outputPath
    )
  } else {
    local_apply_concept_set_action(patch, write = TRUE)
  }
  post_hash <- tryCatch(tools::md5sum(res$written_to %||% conceptSetRef), error = function(e) NA_character_)

  outdir <- file.path(dirname(conceptSetRef), "inst", "assistant")
  if (!dir.exists(outdir)) dir.create(outdir, recursive = TRUE)
  log_entry <- list(
    plan = res$plan,
    preview_changes = res$preview_changes,
    applied = res$applied,
    written_to = res$written_to %||% conceptSetRef,
    pre_hash = unname(pre_hash),
    post_hash = unname(post_hash),
    ts = format(Sys.time(), "%Y%m%dT%H%M%S")
  )
  jsonlite::write_json(
    log_entry,
    file.path(outdir, paste0("concept_set_edit_", log_entry$ts, ".json")),
    auto_unbox = TRUE,
    pretty = TRUE
  )
  if (isTRUE(res$applied)) {
    cat(sprintf("Applied concept set patch to %s\n", res$written_to %||% conceptSetRef))
    if (isTRUE(backup) && !is.null(res$backup_file)) {
      cat(sprintf("Backup created at %s\n", res$backup_file))
    }
  } else {
    cat("No changes applied.\n")
  }
  invisible(res)
}

#' Lint study design
#' @param studyProtocol path or URL to protocol.md
#' @param studyPackage path to local study folder
#' @param lintTasks character vector of tasks
#' @param apply logical; advisory placeholder
#' @param interactive logical; print plans and findings
#' @param streamThoughts logical; placeholder
#' @param handleActions logical; preview ACP action output when available
#' @param applyActions logical; apply ACP action output when available
#' @param overwriteActions logical; overwrite target file in ACP action mode
#' @param backupActions logical; backup target file in ACP action mode
#' @return invisible list of task results
#' @export
lintStudyDesign <- function(studyProtocol,
                            studyPackage = ".",
                            lintTasks = c("concept-sets-review", "cohort-critique-general-design"),
                            apply = FALSE,
                            interactive = TRUE,
                            streamThoughts = TRUE,
                            handleActions = FALSE,
                            applyActions = FALSE,
                            overwriteActions = FALSE,
                            backupActions = TRUE) {
  conceptSetRef <- file.path(studyPackage, "concept_set.json")
  cohortRef <- file.path(studyPackage, "cohort_definition.json")
  study_intent <- paste(readLines(studyProtocol, warn = FALSE), collapse = " ")

  results <- list()
  client <- acp_get_default_client()

  if ("concept-sets-review" %in% lintTasks) {
    res <- if (!is.null(client)) {
      acp_lint_concept_sets(client, concept_set_path = conceptSetRef, study_intent = study_intent)
    } else {
      local_concept_sets_review(conceptSetRef, studyIntent = study_intent)
    }
    res$artifact <- conceptSetRef
    core <- res$full_result %||% res
    if (handleActions && !is.null(client) && length(core$actions %||% list())) {
      prev <- applyLLMActionsConceptSet(conceptSetRef, core$actions, preview = TRUE)
      res$action_preview <- prev
      if (applyActions) {
        res$action_apply <- applyLLMActionsConceptSet(
          conceptSetRef,
          core$actions,
          preview = FALSE,
          overwrite = overwriteActions,
          backup = backupActions
        )
      }
    }
    if (interactive) {
      cat("\n== Concept Sets Review ==\n")
      cat(sprintf("File: %s\n", conceptSetRef))
      cat(core$plan %||% "", "\n")
      print_findings(core$findings)
      if (handleActions && !is.null(res$action_preview)) {
        cat(sprintf(
          "Action preview: %s changes, %s ignored\n",
          res$action_preview$counts$changed %||% 0,
          res$action_preview$counts$ignored %||% 0
        ))
      }
      if (applyActions && !is.null(res$action_apply) && isTRUE(res$action_apply$applied)) {
        cat(sprintf("Actions applied. Written to: %s\n", res$action_apply$written_to %||% conceptSetRef))
      }
    }
    results$`concept-sets-review` <- res
  }

  if ("cohort-critique-general-design" %in% lintTasks) {
    res <- if (!is.null(client)) {
      acp_lint_cohort_general_design(client, cohort_path = cohortRef)
    } else {
      local_cohort_critique_general(cohortRef)
    }
    res$artifact <- cohortRef
    core <- res$full_result %||% res
    if (interactive) {
      cat("\n== Cohort Critique: General Design ==\n")
      cat(sprintf("File: %s\n", cohortRef))
      cat(core$plan %||% "", "\n")
      print_findings(core$findings)
    }
    results$`cohort-critique-general-design` <- res
  }

  outdir <- file.path(studyPackage, "inst", "assistant")
  if (!dir.exists(outdir)) dir.create(outdir, recursive = TRUE)
  ts <- format(Sys.time(), "%Y%m%dT%H%M%S")
  jsonlite::write_json(
    results,
    file.path(outdir, paste0("advice_", ts, ".json")),
    auto_unbox = TRUE,
    pretty = TRUE
  )

  invisible(results)
}

local_apply_concept_set_action <- function(payload, write = FALSE) {
  ref <- payload$artifactRef
  cs <- read_json_ref(ref)
  ops <- payload$ops %||% list()
  all_preview <- list()

  for (op in ops) {
    if (identical(op$op, "set_include_descendants")) {
      where <- op$where %||% list()
      value <- op$value %||% TRUE
      res <- local_set_include_descendants(cs, where, value)
      cs <- res$cs
      all_preview <- c(all_preview, res$preview)
    }
  }

  written_to <- NULL
  applied <- FALSE
  backup_file <- NULL
  if (isTRUE(write)) {
    target <- payload$outputPath %||% ref
    if (isTRUE(payload$backup) && file.exists(target)) {
      ts <- format(Sys.time(), "%Y%m%dT%H%M%S")
      backup_file <- paste0(target, ".bak_", ts)
      file.copy(target, backup_file, overwrite = TRUE)
    }
    jsonlite::write_json(cs, target, auto_unbox = TRUE, pretty = TRUE)
    written_to <- target
    applied <- TRUE
  }

  list(
    plan = "Set includeDescendants=true for Drug/Ingredient entries that lack it.",
    preview_changes = all_preview,
    applied = applied,
    written_to = written_to,
    backup_file = backup_file
  )
}

local_set_include_descendants <- function(cs, where, value = TRUE) {
  items <- if (!is.null(cs$items)) cs$items else cs
  preview <- list()
  for (i in seq_along(items)) {
    it <- items[[i]]
    concept <- it$concept %||% list()
    cid <- concept$conceptId %||% concept$CONCEPT_ID %||% NA_integer_
    dom <- concept$domainId %||% concept$DOMAIN_ID %||% NA_character_
    cls <- concept$conceptClassId %||% concept$CONCEPT_CLASS_ID %||% NA_character_
    inc <- it$includeDescendants %||% FALSE
    if (!is.na(where$domainId %||% NA_character_) && !identical(dom, where$domainId)) next
    if (!is.na(where$conceptClassId %||% NA_character_) && !identical(cls, where$conceptClassId)) next
    if (!is.null(where$includeDescendants) && !identical(isTRUE(inc), isTRUE(where$includeDescendants))) next
    preview <- c(preview, list(list(
      conceptId = cid,
      from = list(includeDescendants = inc),
      to = list(includeDescendants = value)
    )))
    it$includeDescendants <- isTRUE(value)
    items[[i]] <- it
  }
  if (!is.null(cs$items)) {
    cs$items <- items
  } else {
    cs <- items
  }
  list(cs = cs, preview = preview)
}

local_concept_sets_review <- function(conceptSetRef, studyIntent = "") {
  cs <- read_json_ref(conceptSetRef)
  items <- if (!is.null(cs$items)) cs$items else cs

  get_item <- function(it) {
    concept <- it$concept %||% it
    list(
      conceptId = concept$conceptId %||% concept$CONCEPT_ID %||% concept$id %||% NA_integer_,
      domainId = concept$domainId %||% concept$DOMAIN_ID %||% NA_character_
    )
  }
  lst <- lapply(items, get_item)

  plan <- sprintf("Local concept set review for %s", conceptSetRef)
  findings <- list()
  patches <- list()
  risk_notes <- list()

  ids <- vapply(lst, function(x) x$conceptId, integer(1))
  ids <- ids[!is.na(ids)]
  if (length(lst) == 0) {
    findings <- c(findings, list(list(
      id = "empty_concept_set",
      severity = "high",
      impact = "design",
      message = "Concept set is empty."
    )))
  }
  if (length(ids)) {
    dups <- ids[duplicated(ids)]
    if (length(dups)) {
      findings <- c(findings, list(list(
        id = "duplicate_concepts",
        severity = "medium",
        impact = "design",
        message = paste("Duplicate conceptIds:", paste(unique(dups), collapse = ", "))
      )))
      patches <- c(patches, list(list(
        artifact = conceptSetRef,
        type = "jsonpatch",
        ops = list(list(op = "note", path = "/items", value = list(removeDuplicatesOf = unique(dups))))
      )))
    }
  }
  domains <- unique(vapply(lst, function(x) x$domainId %||% NA_character_, character(1)))
  domains <- domains[!is.na(domains)]
  if (length(domains) > 1) {
    findings <- c(findings, list(list(
      id = "mixed_domains",
      severity = "low",
      impact = "portability",
      message = paste("Multiple domains:", paste(domains, collapse = ", "))
    )))
  }

  list(plan = plan, findings = findings, patches = patches, risk_notes = risk_notes)
}

local_cohort_critique_general <- function(cohortRef) {
  cdef <- read_json_ref(cohortRef)
  plan <- sprintf("Local general cohort design lint for %s", cohortRef)
  findings <- list()
  patches <- list()
  risk_notes <- list()

  pc <- cdef$PrimaryCriteria %||% list()
  wash <- pc$ObservationWindow %||% list()
  if (is.null(wash$PriorDays) || identical(wash$PriorDays, 0L)) {
    findings <- c(findings, list(list(
      id = "missing_washout",
      severity = "medium",
      impact = "validity",
      message = "No or zero-day washout; consider >=365 days."
    )))
    patches <- c(patches, list(list(
      artifact = cohortRef,
      type = "jsonpatch",
      ops = list(list(
        op = "note",
        path = "/PrimaryCriteria/ObservationWindow",
        value = list(ProposedPriorDays = 365)
      ))
    )))
  }

  irules <- cdef$InclusionRules %||% list()
  for (i in seq_along(irules)) {
    window <- irules[[i]]$window %||% NULL
    if (!is.null(window) && !is.null(window$start) && !is.null(window$end) && window$start > window$end) {
      findings <- c(findings, list(list(
        id = paste0("inverted_window_", i),
        severity = "high",
        impact = "validity",
        message = sprintf("InclusionRules[%d] has inverted window.", i)
      )))
    }
  }
  list(plan = plan, findings = findings, patches = patches, risk_notes = risk_notes)
}

read_json_ref <- function(ref) {
  if (grepl("^https?://", ref)) {
    txt <- readLines(ref, warn = FALSE)
    return(jsonlite::fromJSON(paste(txt, collapse = "\n"), simplifyVector = FALSE))
  }
  jsonlite::fromJSON(ref, simplifyVector = FALSE)
}

print_findings <- function(findings) {
  if (length(findings %||% list()) == 0) {
    cat("  [OK] No findings.\n")
    return(invisible(NULL))
  }
  for (finding in findings) {
    cat(sprintf(
      "  - [%s][%s] %s\n",
      toupper(finding$severity %||% "INFO"),
      finding$impact %||% "",
      finding$message %||% jsonlite::toJSON(finding, auto_unbox = TRUE)
    ))
  }
}
