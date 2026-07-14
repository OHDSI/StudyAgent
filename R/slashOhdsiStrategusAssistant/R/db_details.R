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

normalizeStrategusDbConfig <- function(path = file.path(getwd(), "strategus-db-details.json"),
                                       dbDetails = NULL) {
  `%||%` <- function(x, y) if (is.null(x)) y else x
  null_if_blank <- function(value) {
    if (is.null(value)) return(NULL)
    text <- trimws(as.character(value))
    if (!nzchar(text)) return(NULL)
    text
  }
  dbConfig <- dbDetails %||% readStrategusDbDetails(path)
  dbms <- null_if_blank(dbConfig$dbms) %||% "postgresql"
  rawServer <- null_if_blank(dbConfig$DB_SERVER %||% dbConfig$server)
  if (is.null(rawServer)) {
    stop("Database server must be provided in strategus-db-details.json (DB_SERVER or server).")
  }
  parseServerAndPort <- function(value) {
    value <- null_if_blank(value)
    if (is.null(value)) return(list(server = "", port = NULL))
    authority <- value
    database_suffix <- NULL
    if (identical(dbms, "postgresql") && grepl("/", value, fixed = TRUE)) {
      parts <- strsplit(value, "/", fixed = TRUE)[[1]]
      authority <- parts[[1]] %||% ""
      if (length(parts) > 1L) {
        database_path <- paste(parts[-1], collapse = "/")
        if (nzchar(trimws(database_path))) database_suffix <- database_path
      }
    }
    server <- authority
    port <- NULL
    if (grepl('^\\[[^]]+\\]:[0-9]+$', authority)) {
      server <- sub('^\\[([^]]+)\\]:([0-9]+)$', '\\1', authority)
      port <- sub('^\\[([^]]+)\\]:([0-9]+)$', '\\2', authority)
    } else if (grepl('^[^:]+:[0-9]+$', authority)) {
      server <- sub(':([0-9]+)$', '', authority)
      port <- sub('^.*:([0-9]+)$', '\\1', authority)
    }
    if (!is.null(database_suffix)) {
      server <- sprintf('%s/%s', server, database_suffix)
    }
    list(server = server, port = port)
  }
  parsedServer <- parseServerAndPort(rawServer)
  server <- parsedServer$server
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
  explicitPort <- null_if_blank(dbConfig$DB_PORT %||% dbConfig$port)
  port <- explicitPort %||% parsedServer$port %||% if (identical(dbms, "sql server")) "1433" else "5432"
  effectiveServer <- server
  effectivePort <- port
  user <- null_if_blank(dbConfig$DB_USER %||% dbConfig$user)
  raw_password <- dbConfig$DB_PASS %||% dbConfig$password
  password <- if (is.null(raw_password)) NULL else as.character(raw_password)
  pathToDriver <- null_if_blank(dbConfig$DB_DRIVER_PATH %||% dbConfig$pathToDriver)
  jarFolder <- null_if_blank(dbConfig$DATABASECONNECTOR_JAR_FOLDER %||% dbConfig$databaseConnectorJarFolder %||% dbConfig$jarFolder)
  extraSettings <- null_if_blank(dbConfig$extraSettings)
  if (is.null(extraSettings)) {
    extraSettings <- if (identical(dbms, "postgresql")) "sslmode=disable" else ""
  }
  list(
    dbConfig = dbConfig,
    dbms = dbms,
    rawServer = rawServer,
    server = server,
    port = port,
    effectiveServer = effectiveServer,
    effectivePort = effectivePort,
    authType = authType,
    useIntegratedAuth = useIntegratedAuth,
    user = user,
    password = password,
    pathToDriver = pathToDriver,
    jarFolder = jarFolder,
    extraSettings = extraSettings
  )
}

#' Create DatabaseConnector connectionDetails from strategus-db-details.json
#' @param path path to strategus-db-details.json
#' @param dbDetails optional list of db settings (if already loaded)
#' @return DatabaseConnector connectionDetails object
#' @export
createStrategusConnectionDetails <- function(path = file.path(getwd(), "strategus-db-details.json"),
                                             dbDetails = NULL) {
  normalized <- normalizeStrategusDbConfig(path = path, dbDetails = dbDetails)
  user <- normalized$user
  password <- normalized$password
  if (!isTRUE(normalized$useIntegratedAuth) && (is.null(user) || !nzchar(as.character(user)) || is.null(password))) {
    stop("Database credentials must be provided in strategus-db-details.json (DB_USER/DB_PASS or user/password) unless authType requests integrated Windows authentication.")
  }

  if (!is.null(normalized$jarFolder) && nzchar(trimws(as.character(normalized$jarFolder)))) {
    Sys.setenv(DATABASECONNECTOR_JAR_FOLDER = as.character(normalized$jarFolder))
  }

  args <- Filter(Negate(is.null), list(
    dbms = normalized$dbms,
    server = normalized$effectiveServer %||% normalized$server,
    port = normalized$effectivePort,
    pathToDriver = normalized$pathToDriver,
    extraSettings = normalized$extraSettings,
    user = if (!isTRUE(normalized$useIntegratedAuth)) user else NULL,
    password = if (!isTRUE(normalized$useIntegratedAuth)) password else NULL
  ))
  do.call(DatabaseConnector::createConnectionDetails, args)
}
