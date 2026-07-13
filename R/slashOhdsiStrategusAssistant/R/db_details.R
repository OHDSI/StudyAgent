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

  authType <- tolower(trimws(as.character(
    dbConfig$authType %||%
      dbConfig$authenticationType %||%
      if (isTRUE(dbConfig$useWindowsAuth %||% FALSE)) "windows" else "username_password"
  )))
  if (!nzchar(authType)) authType <- "username_password"
  if (!(authType %in% c("username_password", "windows", "integrated", "integrated_windows"))) {
    stop("Unsupported authType in strategus-db-details.json. Use one of: username_password, windows, integrated, integrated_windows.")
  }
  useIntegratedAuth <- authType %in% c("windows", "integrated", "integrated_windows")

  port <- dbConfig$DB_PORT %||% dbConfig$port %||% if (identical(dbms, "sql server")) "1433" else "5432"
  user <- dbConfig$DB_USER %||% dbConfig$user
  password <- dbConfig$DB_PASS %||% dbConfig$password
  if (!isTRUE(useIntegratedAuth) && (is.null(user) || is.null(password) || !nzchar(as.character(user)) || !nzchar(as.character(password)))) {
    stop("Database credentials must be provided in strategus-db-details.json (DB_USER/DB_PASS or user/password) unless authType requests integrated Windows authentication.")
  }

  pathToDriver <- dbConfig$DB_DRIVER_PATH %||% dbConfig$pathToDriver
  jarFolder <- dbConfig$DATABASECONNECTOR_JAR_FOLDER %||% dbConfig$databaseConnectorJarFolder %||% dbConfig$jarFolder
  if (!is.null(jarFolder) && nzchar(trimws(as.character(jarFolder)))) {
    Sys.setenv(DATABASECONNECTOR_JAR_FOLDER = as.character(jarFolder))
  }

  extraSettings <- dbConfig$extraSettings
  if (is.null(extraSettings)) {
    extraSettings <- if (identical(dbms, "postgresql")) "sslmode=disable" else ""
  }

  args <- Filter(Negate(is.null), list(
    dbms = dbms,
    server = server,
    port = port,
    pathToDriver = pathToDriver,
    extraSettings = extraSettings,
    user = if (!isTRUE(useIntegratedAuth)) user else NULL,
    password = if (!isTRUE(useIntegratedAuth)) password else NULL
  ))
  do.call(DatabaseConnector::createConnectionDetails, args)
}
