#' Read Strategus execution settings from JSON
#' @param path path to strategus-execution-settings.json
#' @return list of execution settings
#' @export
readStrategusExecutionSettings <- function(path = file.path(getwd(), "strategus-execution-settings.json")) {
  if (!file.exists(path)) {
    stop("Execution settings file not found: ", path)
  }
  jsonlite::read_json(path, simplifyVector = TRUE)
}

#' Create Strategus execution settings from JSON
#' @param path path to strategus-execution-settings.json
#' @param settings optional list of settings (if already loaded)
#' @return list with executionSettings and resolved values
#' @export
createStrategusExecutionSettings <- function(path = file.path(getwd(), "strategus-execution-settings.json"),
                                             settings = NULL) {
  `%||%` <- function(x, y) if (is.null(x)) y else x
  cfg <- settings %||% readStrategusExecutionSettings(path)
  cdmDatabaseSchema <- cfg$cdmDatabaseSchema
  workDatabaseSchema <- cfg$workDatabaseSchema
  resultsDatabaseSchema <- cfg$resultsDatabaseSchema
  vocabularyDatabaseSchema <- cfg$vocabularyDatabaseSchema
  cohortTable <- cfg$cohortTable
  workFolder <- cfg$workFolder
  resultsFolder <- cfg$resultsFolder
  cohortIdFieldName <- cfg$cohortIdFieldName %||% "cohort_definition_id"

  if (!nzchar(cdmDatabaseSchema)) stop("cdmDatabaseSchema must be provided in strategus-execution-settings.json")
  if (!nzchar(workDatabaseSchema)) stop("workDatabaseSchema must be provided in strategus-execution-settings.json")
  if (!nzchar(resultsDatabaseSchema)) stop("resultsDatabaseSchema must be provided in strategus-execution-settings.json")
  if (!nzchar(vocabularyDatabaseSchema)) stop("vocabularyDatabaseSchema must be provided in strategus-execution-settings.json")
  if (!nzchar(cohortTable)) stop("cohortTable must be provided in strategus-execution-settings.json")
  if (!nzchar(workFolder)) stop("workFolder must be provided in strategus-execution-settings.json")
  if (!nzchar(resultsFolder)) stop("resultsFolder must be provided in strategus-execution-settings.json")

  executionSettings <- createCdmExecutionSettings(
    cdmDatabaseSchema = cdmDatabaseSchema,
    workDatabaseSchema = workDatabaseSchema,
    workFolder = workFolder,
    resultsFolder = resultsFolder
  )

  list(
    executionSettings = executionSettings,
    cdmDatabaseSchema = cdmDatabaseSchema,
    workDatabaseSchema = workDatabaseSchema,
    resultsDatabaseSchema = resultsDatabaseSchema,
    vocabularyDatabaseSchema = vocabularyDatabaseSchema,
    cohortTable = cohortTable,
    workFolder = workFolder,
    resultsFolder = resultsFolder,
    cohortIdFieldName = cohortIdFieldName
  )
}
