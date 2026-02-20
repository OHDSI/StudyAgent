#' Lint study design (prototype)
#' @param studyProtocol path or URL to protocol.md
#' @param studyPackage path to local study folder ('.' ok)
#' @param lintTasks character vector of tasks
#' @param apply logical; not used in prototype (advisory only)
#' @param interactive logical; print plans and findings
#' @param streamThoughts logical; placeholder
#' @return list of results by task
lintStudyDesign <- function(
  studyProtocol,
  studyPackage = ".",
  lintTasks = c("concept-sets-review","cohort-critique-general-design"),
  apply = FALSE,
  interactive = TRUE,
  streamThoughts = TRUE,
  handleActions = FALSE,
  applyActions = FALSE,
  overwriteActions = FALSE,
  backupActions = TRUE
) {
  conceptSetRef <- file.path(studyPackage, "concept_set.json")
  cohortRef     <- file.path(studyPackage, "cohort_definition.json")

  results <- list()
  use_acp <- !is.null(acp_state$url)

  if ("concept-sets-review" %in% lintTasks) {
    res <- if (use_acp) {
      .acp_post("/tools/propose_concept_set_diff", list(
        conceptSetRef = conceptSetRef,
        studyIntent   = paste(readLines(studyProtocol, warn = FALSE), collapse=" ")
      ))
    } else {
      local_concept_sets_review(conceptSetRef, studyIntent = paste(readLines(studyProtocol, warn = FALSE), collapse=" "))
    }
    res$artifact <- conceptSetRef
    # optional actions handling
    if (handleActions && use_acp && length(res$actions %||% list())) {
      prev <- applyLLMActionsConceptSet(conceptSetRef, res$actions, preview = TRUE)
      res$action_preview <- prev
      if (applyActions) {
        res$action_apply <- applyLLMActionsConceptSet(
          conceptSetRef,
          res$actions,
          preview = FALSE,
          overwrite = overwriteActions,
          backup = backupActions
        )
      }
    }
    if (interactive) {
      cat("\n== Concept Sets Review ==\n")
      cat(sprintf("File: %s\n", conceptSetRef))
      cat(res$plan, "\n")
      print_findings(res$findings)
      if (handleActions && !is.null(res$action_preview)) {
        cat(sprintf("Action preview: %s changes, %s ignored\n",
                    res$action_preview$counts$changed %||% 0,
                    res$action_preview$counts$ignored %||% 0))
      }
      if (applyActions && !is.null(res$action_apply) && isTRUE(res$action_apply$applied)) {
        cat(sprintf("Actions applied. Written to: %s\n", res$action_apply$written_to %||% conceptSetRef))
      }
    }
    results$`concept-sets-review` <- res
  }

  if ("cohort-critique-general-design" %in% lintTasks) {
    res <- if (use_acp) {
      .acp_post("/tools/cohort_lint", list(cohortRef = cohortRef))
    } else {
      local_cohort_critique_general(cohortRef)
    }
    res$artifact <- cohortRef
    if (interactive) {
      cat("\n== Cohort Critique: General Design ==\n")
      cat(sprintf("File: %s\n", cohortRef))
      cat(res$plan, "\n")
      print_findings(res$findings)
    }
    results$`cohort-critique-general-design` <- res
  }

  outdir <- file.path(studyPackage, "inst", "assistant")
  if (!dir.exists(outdir)) dir.create(outdir, recursive = TRUE)
  ts <- format(Sys.time(), "%Y%m%dT%H%M%S")
  jsonlite::write_json(results, file.path(outdir, paste0("advice_", ts, ".json")), auto_unbox = TRUE, pretty = TRUE)

  invisible(results)
}
