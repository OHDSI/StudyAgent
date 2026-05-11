#' Compatibility wrapper for the Strategus cohort-methods shell
#' @param ... forwarded to slashOhdsiStrategusAssistant::runStrategusCohortMethodsShell
#' @return invisible list with output paths
#' @export
runStrategusCohortMethodsShell <- function(...) {
  if (!requireNamespace("slashOhdsiStrategusAssistant", quietly = TRUE)) {
    stop("slashOhdsiStrategusAssistant must be installed or loaded to run the Strategus cohort-methods shell.")
  }
  slashOhdsiStrategusAssistant::runStrategusCohortMethodsShell(...)
}
