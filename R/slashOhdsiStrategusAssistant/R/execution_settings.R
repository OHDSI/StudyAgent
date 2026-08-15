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
  incremental <- cfg$incremental %||% FALSE
  cdmDatabaseSchema <- cfg$cdmDatabaseSchema
  workDatabaseSchema <- cfg$workDatabaseSchema
  resultsDatabaseSchema <- cfg$resultsDatabaseSchema
  vocabularyDatabaseSchema <- cfg$vocabularyDatabaseSchema
  cohortTable <- cfg$cohortTable
  workFolder <- cfg$workFolder
  resultsFolder <- cfg$resultsFolder
  settings_base_dir <- dirname(normalizePath(path, winslash = "/", mustWork = FALSE))
  resolve_workspace_path <- function(value) {
    value <- trimws(as.character(value %||% ""))
    if (!nzchar(value)) return(value)
    if (grepl("^(?:/|~|[A-Za-z]:)", value)) return(normalizePath(value, winslash = "/", mustWork = FALSE))
    normalizePath(file.path(settings_base_dir, value), winslash = "/", mustWork = FALSE)
  }
  workFolder <- resolve_workspace_path(workFolder)
  resultsFolder <- resolve_workspace_path(resultsFolder)
  cohortIdFieldName <- cfg$cohortIdFieldName %||% "cohort_definition_id"
  maxCores <- cfg$maxCores %||% parallel::detectCores()
  maxCores <- suppressWarnings(as.integer(maxCores)[1])
  if (is.na(maxCores) || maxCores < 1L) maxCores <- 1L

  if (!nzchar(cdmDatabaseSchema)) stop("cdmDatabaseSchema must be provided in strategus-execution-settings.json")
  if (!nzchar(workDatabaseSchema)) stop("workDatabaseSchema must be provided in strategus-execution-settings.json")
  if (!nzchar(resultsDatabaseSchema)) stop("resultsDatabaseSchema must be provided in strategus-execution-settings.json")
  if (!nzchar(vocabularyDatabaseSchema)) stop("vocabularyDatabaseSchema must be provided in strategus-execution-settings.json")
  if (!nzchar(cohortTable)) stop("cohortTable must be provided in strategus-execution-settings.json")
  if (!nzchar(workFolder)) stop("workFolder must be provided in strategus-execution-settings.json")
  if (!nzchar(resultsFolder)) stop("resultsFolder must be provided in strategus-execution-settings.json")

  executionSettings <- Strategus::createCdmExecutionSettings(
    cdmDatabaseSchema = cdmDatabaseSchema,
    workDatabaseSchema = workDatabaseSchema,
    cohortTableNames = CohortGenerator::getCohortTableNames(cohortTable = cohortTable),
    workFolder = workFolder,
    resultsFolder = resultsFolder,
    maxCores = maxCores,
    incremental = incremental
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
    maxCores = maxCores,
    cohortIdFieldName = cohortIdFieldName,
    incremental=incremental
  )
}
