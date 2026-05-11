#' Suggest cohort method study specifications from a free-text description (compatibility wrapper)
#' @inheritParams slashOhdsiStrategusAssistant::suggestCohortMethodSpecs
#' @return list response from ACP flow or local stub
#' @export
suggestCohortMethodSpecs <- function(studyIntent,
                                     analyticSettingsDescription,
                                     interactive = TRUE) {
  if (!requireNamespace("slashOhdsiStrategusAssistant", quietly = TRUE)) {
    stop("slashOhdsiStrategusAssistant must be installed or loaded to use suggestCohortMethodSpecs().")
  }
  slashOhdsiStrategusAssistant::suggestCohortMethodSpecs(
    studyIntent = studyIntent,
    analyticSettingsDescription = analyticSettingsDescription,
    interactive = interactive
  )
}
