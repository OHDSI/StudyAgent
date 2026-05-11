#' Read Strategus database details from JSON (compatibility wrapper)
#' @inheritParams slashOhdsiStrategusAssistant::readStrategusDbDetails
#' @return list of db settings
#' @export
readStrategusDbDetails <- function(path = file.path(getwd(), "strategus-db-details.json")) {
  if (!requireNamespace("slashOhdsiStrategusAssistant", quietly = TRUE)) {
    stop("slashOhdsiStrategusAssistant must be installed or loaded to use readStrategusDbDetails().")
  }
  slashOhdsiStrategusAssistant::readStrategusDbDetails(path = path)
}

#' Create DatabaseConnector connectionDetails from strategus-db-details.json (compatibility wrapper)
#' @inheritParams slashOhdsiStrategusAssistant::createStrategusConnectionDetails
#' @return DatabaseConnector connectionDetails object
#' @export
createStrategusConnectionDetails <- function(path = file.path(getwd(), "strategus-db-details.json"),
                                             dbDetails = NULL) {
  if (!requireNamespace("slashOhdsiStrategusAssistant", quietly = TRUE)) {
    stop("slashOhdsiStrategusAssistant must be installed or loaded to use createStrategusConnectionDetails().")
  }
  slashOhdsiStrategusAssistant::createStrategusConnectionDetails(path = path, dbDetails = dbDetails)
}
