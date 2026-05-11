#' Read Strategus execution settings from JSON (compatibility wrapper)
#' @inheritParams slashOhdsiStrategusAssistant::readStrategusExecutionSettings
#' @return list of execution settings
#' @export
readStrategusExecutionSettings <- function(path = file.path(getwd(), "strategus-execution-settings.json")) {
  if (!requireNamespace("slashOhdsiStrategusAssistant", quietly = TRUE)) {
    stop("slashOhdsiStrategusAssistant must be installed or loaded to use readStrategusExecutionSettings().")
  }
  slashOhdsiStrategusAssistant::readStrategusExecutionSettings(path = path)
}

#' Create Strategus execution settings from JSON (compatibility wrapper)
#' @inheritParams slashOhdsiStrategusAssistant::createStrategusExecutionSettings
#' @return list with executionSettings and resolved values
#' @export
createStrategusExecutionSettings <- function(path = file.path(getwd(), "strategus-execution-settings.json"),
                                             settings = NULL) {
  if (!requireNamespace("slashOhdsiStrategusAssistant", quietly = TRUE)) {
    stop("slashOhdsiStrategusAssistant must be installed or loaded to use createStrategusExecutionSettings().")
  }
  slashOhdsiStrategusAssistant::createStrategusExecutionSettings(path = path, settings = settings)
}
