### This expects to run from a folder two levels up that has a working renv project

project_folder="/ai-agent/HadesProject/"

library(DatabaseConnector)
library(CohortGenerator)
library(CirceR)
library(SqlRender)
library(jsonlite)
library(PhenotypeLibrary)
message("Required libraries loaded successfully")

`%||%` <- function(x, y) {
  if (is.null(x) || (is.character(x) && length(x) == 1 && x == "")) y else x
}

outputFolder <- paste(project_folder,"AgenticStudyAssistant/scripts/output-cohort-diagn",sep="")

read_db_details <- function(path = paste(project_folder,"db-details.json",sep="")) {
  if (!file.exists(path)) {
    stop("Database details file not found: ", path)
  }
  jsonlite::read_json(path, simplifyVector = TRUE)
}
dbConfig <- read_db_details()

dbms <- dbConfig$dbms
server <- dbConfig$PG_SERVER
if (is.null(server)) {
    stop("Database server must be provided in db-details.json (PG_SERVER or server).")
}
port <- dbConfig$PG_PORT %||% dbConfig$port
user <- dbConfig$PG_USER %||% dbConfig$user
password <- dbConfig$PG_PASS %||% dbConfig$password
if (is.null(user) || is.null(password)) {
    stop("Database credentials must be provided in db-details.json (PG_USER/PG_PASS or user/password).")
}

pathToDriver <- dbConfig$PG_DRIVER_PATH 
extraSettings <- dbConfig$extraSettings

connectionDetails <- DatabaseConnector::createConnectionDetails(
    dbms = "postgresql",
    server = server,
    user = user,
    password = password,
    port = port,
    pathToDriver = pathToDriver,
    extraSettings = extraSettings
  )

cdmDatabaseSchema <- dbConfig$cdmDatabaseSchema %||% "staging_synthea"
cohortDatabaseSchema <- dbConfig$cohortDatabaseSchema %||% "scratch_rdb20"
vocabularyDatabaseSchema <- dbConfig$vocabularyDatabaseSchema %||% "vocabulary"
cohortTable <- dbConfig$cohortTable %||% "cohort"
tempEmulationSchema <- dbConfig$tempEmulationSchema %||% NULL

cohortDefinitionSet <- PhenotypeLibrary::getPlCohortDefinitionSet(cohortIds = c(33,1197)) # dementia and acute GI bleeding
cohortTables <- CohortGenerator::getCohortTableNames()
CohortGenerator::generateCohortSet(
  connectionDetails = connectionDetails,
  cdmDatabaseSchema = cdmDatabaseSchema,
  cohortDatabaseSchema = cohortDatabaseSchema,
  cohortTableNames = cohortTables,
  cohortDefinitionSet = cohortDefinitionSet
  )

## Run diagnostics on the generated cohorts
databaseId <- "synthea-truven"
databaseName <-
  "Truven-like Synthea-generated data"
databaseDescription <-
  "A synthetic dataset generated with Synthea following similar distributions to Truven "  
CohortDiagnostics::executeDiagnostics(
  cohortDefinitionSet = cohortDefinitionSet,
  exportFolder = outputFolder,
  databaseId = databaseId,
  databaseName = databaseName,
  databaseDescription = databaseDescription,
  cohortDatabaseSchema = cohortDatabaseSchema,
  cdmDatabaseSchema = cdmDatabaseSchema,
  connectionDetails = connectionDetails,
  cohortTableNames = cohortTables
)

