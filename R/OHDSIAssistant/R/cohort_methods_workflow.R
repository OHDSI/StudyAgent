#' Suggest cohort method study specifications from a free-text description.
#'
#' Calls the ACP flow `/flows/cohort_methods_specifications_recommendation`
#' and returns the cohort-methods recommendation, full analysis spec for
#' traceability, and per-section rationales. Falls back to a local stub
#' when `acp_state$url` is NULL.
#'
#' @param studyIntent protocol context string
#' @param analyticSettingsDescription free-text description of the study design
#' @param interactive when TRUE, prints a section summary (default: TRUE)
#' @return list response from ACP flow or local stub
#' @export
suggestCohortMethodSpecs <- function(studyIntent,
                                     analyticSettingsDescription,
                                     interactive = TRUE) {
  if (is.null(studyIntent) || !nzchar(trimws(studyIntent))) {
    stop("Provide a non-empty studyIntent.")
  }
  if (is.null(analyticSettingsDescription) || !nzchar(trimws(analyticSettingsDescription))) {
    stop("Provide a non-empty analyticSettingsDescription.")
  }

  body <- list(
    study_intent = trimws(as.character(studyIntent)),
    study_description = trimws(as.character(analyticSettingsDescription)),
    analytic_settings_description = trimws(as.character(analyticSettingsDescription))
  )

  res <- if (!is.null(acp_state$url)) {
    .acp_post("/flows/cohort_methods_specifications_recommendation", body)
  } else {
    local_cohort_method_specs(body)
  }

  if (isTRUE(interactive)) {
    cat("\n== Cohort Method Specifications ==\n")
    cat("Status:", res$status %||% "(missing)", "\n")
    rec <- res$recommendation %||% list()
    if (length(rec) > 0) {
      cat("Profile:", rec$profile_name %||% "(none)", "\n")
      cat("Recommendation status:", rec$status %||% "(none)", "\n")
    }
    rats <- res$section_rationales %||% list()
    if (length(rats) > 0) {
      for (section in names(rats)) {
        entry <- rats[[section]]
        cat(sprintf("  - %s: confidence=%s  %s\n",
                    section,
                    entry$confidence %||% "?",
                    entry$rationale %||% ""))
      }
    }
    failed <- res$diagnostics$failed_sections %||% list()
    if (length(failed) > 0) {
      cat("Backfilled sections:", paste(unlist(failed), collapse = ", "), "\n")
    }
    .studyAgentPrintCohortMethodSpecsSummary(rec)
  }
  invisible(res)
}

.studyAgentCmSpecIsPresent <- function(value) {
  if (is.null(value) || length(value) == 0) return(FALSE)
  if (length(value) == 1 && is.atomic(value) && is.na(value)) return(FALSE)
  TRUE
}

.studyAgentCmSpecValue <- function(value, path = NULL) {
  `%||%` <- function(x, y) if (is.null(x)) y else x
  if (!.studyAgentCmSpecIsPresent(value)) return("<not set>")
  if (is.character(value) && length(value) == 1 && !nzchar(trimws(value))) return("<blank>")
  if (is.logical(value) && length(value) == 1) return(if (isTRUE(value)) "Yes" else "No")
  if (is.character(value) && length(value) == 1) {
    mapped <- switch(
      path %||% "",
      "startAnchor" = c("cohort start" = "cohort start date", "cohort end" = "cohort end date")[[value]],
      "endAnchor" = c("cohort start" = "cohort start date", "cohort end" = "cohort end date")[[value]],
      "ps_strategy" = c("match_on_ps" = "Match on propensity score", "stratify_by_ps" = "Stratify on propensity score", "none" = "None")[[value]],
      "caliperScale" = c("propensity score" = "Propensity score", "standardized" = "Standardized", "standardized logit" = "Standardized logit")[[value]],
      "modelType" = c("cox" = "Cox proportional hazards", "poisson" = "Poisson regression", "logistic" = "Logistic regression")[[value]],
      "removeDuplicateSubjects" = c(
        "keep all" = "Keep All",
        "keep first" = "Keep First",
        "remove all" = "Remove All",
        "keep first, truncate to second" = "Keep First, Truncate to Second"
      )[[value]],
      NULL
    )
    if (!is.null(mapped) && length(mapped) == 1 && !is.na(mapped)) return(mapped)
    return(value)
  }
  if (is.numeric(value) && length(value) == 1) {
    return(trimws(formatC(as.numeric(value), format = "fg", digits = 10)))
  }
  paste(as.character(value), collapse = ", ")
}

.studyAgentCmSpecRegularized <- function(args) {
  if (!is.list(args)) return(FALSE)
  .studyAgentCmSpecIsPresent(args$prior)
}

.studyAgentCmSpecPsStrategy <- function(ps) {
  if (!is.list(ps)) return("none")
  if (.studyAgentCmSpecIsPresent(ps$matchOnPsArgs)) return("match_on_ps")
  if (.studyAgentCmSpecIsPresent(ps$stratifyByPsArgs)) return("stratify_by_ps")
  "none"
}

.studyAgentCmSpecTrimming <- function(trim_args) {
  if (!is.list(trim_args) || length(trim_args) == 0) return("None")
  if (.studyAgentCmSpecIsPresent(trim_args$equipoiseBounds)) return("By equipoise")
  if (.studyAgentCmSpecIsPresent(trim_args$trimFraction)) {
    fraction <- suppressWarnings(as.numeric(trim_args$trimFraction))
    if (length(fraction) == 1 && !is.na(fraction) && fraction > 0) {
      return(sprintf("By percent (%s%%)", trimws(formatC(fraction * 100, format = "fg", digits = 6))))
    }
  }
  "None"
}

.studyAgentCmSpecPrintSection <- function(title, rows) {
  cat(sprintf("[%s]\n", title))
  for (row in rows) {
    cat(sprintf("  - %s: %s\n", row[[1]], row[[2]]))
  }
}

.studyAgentPrintCohortMethodSpecsSummary <- function(recommendation) {
  if (!is.list(recommendation)) return(invisible(NULL))
  study_population <- recommendation$study_population %||% list()
  time_at_risk <- recommendation$time_at_risk %||% list()
  ps <- recommendation$propensity_score_adjustment %||% list()
  outcome <- recommendation$outcome_model %||% list()
  cohort_method_data <- study_population$cohortMethodDataArgs %||% list()
  if (length(study_population) == 0 && length(time_at_risk) == 0 && length(ps) == 0 && length(outcome) == 0) {
    return(invisible(NULL))
  }

  cat("\n")
  .studyAgentCmSpecPrintSection("Study Population", list(
    list("Study start date", .studyAgentCmSpecValue(cohort_method_data$studyStartDate)),
    list("Study end date", .studyAgentCmSpecValue(cohort_method_data$studyEndDate)),
    list("Restrict to common period", .studyAgentCmSpecValue(cohort_method_data$restrictToCommonPeriod)),
    list("First exposure only", .studyAgentCmSpecValue(cohort_method_data$firstExposureOnly)),
    list("Washout period", .studyAgentCmSpecValue(cohort_method_data$washoutPeriod)),
    list("Remove duplicate subjects", .studyAgentCmSpecValue(cohort_method_data$removeDuplicateSubjects, "removeDuplicateSubjects")),
    list("Censor at new risk window", .studyAgentCmSpecValue(study_population$censorAtNewRiskWindow)),
    list("Remove prior outcomes", .studyAgentCmSpecValue(study_population$removeSubjectsWithPriorOutcome)),
    list("Prior outcome lookback", .studyAgentCmSpecValue(study_population$priorOutcomeLookback)),
    list("Maximum cohort size", .studyAgentCmSpecValue(cohort_method_data$maxCohortSize))
  ))
  .studyAgentCmSpecPrintSection("Time At Risk", list(
    list("Minimum days at risk", .studyAgentCmSpecValue(study_population$minDaysAtRisk)),
    list("Risk window start", .studyAgentCmSpecValue(time_at_risk$riskWindowStart)),
    list("Risk window start anchor", .studyAgentCmSpecValue(time_at_risk$startAnchor, "startAnchor")),
    list("Risk window end", .studyAgentCmSpecValue(time_at_risk$riskWindowEnd)),
    list("Risk window end anchor", .studyAgentCmSpecValue(time_at_risk$endAnchor, "endAnchor"))
  ))
  .studyAgentCmSpecPrintSection("Propensity Score Adjustment", list(
    list("PS trimming", .studyAgentCmSpecTrimming(ps$trimByPsArgs)),
    list("PS adjustment strategy", .studyAgentCmSpecValue(.studyAgentCmSpecPsStrategy(ps), "ps_strategy")),
    list("Max cohort size for PS fitting", .studyAgentCmSpecValue(ps$createPsArgs$maxCohortSizeForFitting)),
    list("Test covariate correlation", .studyAgentCmSpecValue(ps$createPsArgs$errorOnHighCorrelation)),
    list("Use regularization", .studyAgentCmSpecValue(.studyAgentCmSpecRegularized(ps$createPsArgs))),
    list("Maximum match ratio", .studyAgentCmSpecValue(ps$matchOnPsArgs$maxRatio)),
    list("Matching caliper", .studyAgentCmSpecValue(ps$matchOnPsArgs$caliper)),
    list("Caliper scale", .studyAgentCmSpecValue(ps$matchOnPsArgs$caliperScale, "caliperScale"))
  ))
  .studyAgentCmSpecPrintSection("Outcome Model", list(
    list("Outcome model", .studyAgentCmSpecValue(outcome$modelType, "modelType")),
    list("Condition on strata", .studyAgentCmSpecValue(outcome$stratified)),
    list("Use covariates in outcome model", .studyAgentCmSpecValue(outcome$useCovariates)),
    list("Use IPTW", .studyAgentCmSpecValue(outcome$inversePtWeighting)),
    list("Use regularization", .studyAgentCmSpecValue(.studyAgentCmSpecRegularized(outcome)))
  ))
  invisible(NULL)
}

local_cohort_method_specs <- function(body) {
  list(
    source = "stub_no_acp",
    status = "stub",
    recommendation = list(
      mode = "free_text",
      input_method = "typed_text",
      source = "local_stub_no_acp",
      status = "stub",
      profile_name = "Recommended from free-text description (stub)",
      raw_description = body$analytic_settings_description %||% "",
      study_population = list(),
      time_at_risk = list(),
      propensity_score_adjustment = list(),
      outcome_model = list(),
      deferred_inputs = list(
        function_argument_description = "implemented",
        description_file_path = "implemented",
        interactive_typed_description = "implemented"
      ),
      defaults_snapshot = list()
    ),
    cohort_methods_specifications = list(),
    section_rationales = list(),
    diagnostics = list(
      source = "local_stub_no_acp",
      reason = "acp_state$url is NULL; call acp_connect(url) first."
    ),
    request = body
  )
}
