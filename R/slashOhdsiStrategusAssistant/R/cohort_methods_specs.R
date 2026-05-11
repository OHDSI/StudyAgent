#' Suggest cohort method study specifications from a free-text description
#' @param studyIntent protocol context string
#' @param analyticSettingsDescription free-text analytic-settings description
#' @param interactive when TRUE, prints a section summary
#' @return list response from ACP flow or local stub
#' @export
suggestCohortMethodSpecs <- function(studyIntent,
                                     analyticSettingsDescription,
                                     interactive = TRUE) {
  if (is.null(studyIntent) || !nzchar(trimws(studyIntent))) stop("Provide a non-empty studyIntent.")
  if (is.null(analyticSettingsDescription) || !nzchar(trimws(analyticSettingsDescription))) {
    stop("Provide a non-empty analyticSettingsDescription.")
  }
  body <- list(
    study_intent = trimws(as.character(studyIntent)),
    study_description = trimws(as.character(analyticSettingsDescription)),
    analytic_settings_description = trimws(as.character(analyticSettingsDescription))
  )

  client <- slashOhdsiAcpClient::acp_get_default_client()
  res <- if (!is.null(client)) {
    slashOhdsiAcpClient::acp_suggest_cohort_method_specs(
      client = client,
      study_intent = studyIntent,
      analytic_settings_description = analyticSettingsDescription
    )
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
  }
  invisible(res)
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
      reason = "No default ACP client is connected; call slashOhdsiAcpClient::acp_connect(url) first."
    ),
    request = body
  )
}
