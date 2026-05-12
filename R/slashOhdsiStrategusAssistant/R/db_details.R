#' Read Strategus database details from JSON
#' @param path path to strategus-db-details.json
#' @return list of db settings
#' @export
readStrategusDbDetails <- function(path = file.path(getwd(), "strategus-db-details.json")) {
  if (!file.exists(path)) {
    stop("Database details file not found: ", path)
  }
  jsonlite::read_json(path, simplifyVector = TRUE)
}

#' Create DatabaseConnector connectionDetails from strategus-db-details.json
#' @param path path to strategus-db-details.json
#' @param dbDetails optional list of db settings (if already loaded)
#' @return DatabaseConnector connectionDetails object
#' @export
createStrategusConnectionDetails <- function(path = file.path(getwd(), "strategus-db-details.json"),
                                             dbDetails = NULL) {
  `%||%` <- function(x, y) if (is.null(x)) y else x
  dbConfig <- dbDetails %||% readStrategusDbDetails(path)
  dbms <- dbConfig$dbms %||% "postgresql"
  server <- dbConfig$DB_SERVER %||% dbConfig$server
  if (is.null(server) || !nzchar(server)) {
    stop("Database server must be provided in strategus-db-details.json (DB_SERVER or server).")
  }
  port <- dbConfig$DB_PORT %||% dbConfig$port %||% "5432"
  user <- dbConfig$DB_USER %||% dbConfig$user
  password <- dbConfig$DB_PASS %||% dbConfig$password
  if (is.null(user) || is.null(password)) {
    stop("Database credentials must be provided in strategus-db-details.json (DB_USER/DB_PASS or user/password).")
  }
  pathToDriver <- dbConfig$DB_DRIVER_PATH %||% dbConfig$pathToDriver
  extraSettings <- dbConfig$extraSettings %||% "sslmode=disable"
  DatabaseConnector::createConnectionDetails(
    dbms = dbms,
    server = server,
    user = user,
    password = password,
    port = port,
    pathToDriver = pathToDriver,
    extraSettings = extraSettings
  )
}
