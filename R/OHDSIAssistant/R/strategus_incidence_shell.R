#' Compatibility wrapper for the Strategus incidence shell
#' @param ... forwarded to slashOhdsiStrategusAssistant::runStrategusIncidenceShell
#' @return invisible list with output paths
#' @export
runStrategusIncidenceShell <- function(...) {
  if (!requireNamespace("slashOhdsiStrategusAssistant", quietly = TRUE)) {
    stop("slashOhdsiStrategusAssistant must be installed or loaded to run the Strategus incidence shell.")
  }
  slashOhdsiStrategusAssistant::runStrategusIncidenceShell(...)
}
