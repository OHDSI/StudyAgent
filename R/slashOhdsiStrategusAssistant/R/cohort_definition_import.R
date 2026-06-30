`%||%` <- function(x, y) if (is.null(x)) y else x

.studyAgentSlashValidateCohortDefinitionSchema <- function(schema) {
  schema <- trimws(as.character(schema %||% ""))
  if (!nzchar(schema)) {
    stop("Provide a cohort definition schema name.")
  }
  if (!grepl("^[A-Za-z][A-Za-z0-9_]*$", schema)) {
    stop("Schema names may contain only letters, numbers, and underscores, and must start with a letter.")
  }
  schema
}

.studyAgentSlashDatabaseCohortSourceId <- function(schema, cohort_definition_id) {
  schema <- .studyAgentSlashValidateCohortDefinitionSchema(schema)
  cohort_definition_id <- suppressWarnings(as.integer(cohort_definition_id))
  if (is.na(cohort_definition_id) || cohort_definition_id <= 0L) {
    stop("cohort_definition_id must be a positive integer.")
  }
  sprintf("db:%s:%s", schema, cohort_definition_id)
}

.studyAgentSlashImportedCohortDefinitionPath <- function(source_id, imported_def_dir) {
  source_id <- as.character(source_id %||% "")
  imported_def_dir <- as.character(imported_def_dir %||% "")
  if (!nzchar(imported_def_dir)) {
    stop("Provide imported_def_dir for cached database cohort definitions.")
  }
  file.path(imported_def_dir, sprintf("%s.json", gsub(":", "__", source_id, fixed = TRUE)))
}

.studyAgentSlashListDatabaseCohortDefinitions <- function(connectionDetails,
                                                           cohort_database_schema,
                                                           search_term = NULL,
                                                           limit = 100L) {
  schema <- .studyAgentSlashValidateCohortDefinitionSchema(cohort_database_schema)
  limit <- suppressWarnings(as.integer(limit %||% 100L))
  if (is.na(limit) || limit <= 0L) limit <- 100L
  sql <- sprintf(
    paste(
      "SELECT id AS cohort_definition_id, name AS cohort_name, expression_type",
      "FROM %s.cohort_definition"
    ),
    schema
  )
  connection <- DatabaseConnector::connect(connectionDetails)
  on.exit(DatabaseConnector::disconnect(connection), add = TRUE)
  rows <- DatabaseConnector::querySql(connection, sql)
  if (is.null(rows) || nrow(rows) == 0) {
    return(data.frame(
      cohort_definition_id = integer(0),
      cohort_name = character(0),
      expression_type = character(0),
      stringsAsFactors = FALSE
    ))
  }
  keep <- intersect(c("cohort_definition_id", "cohort_name", "expression_type"), names(rows))
  rows <- rows[, keep, drop = FALSE]
  rows$cohort_definition_id <- suppressWarnings(as.integer(rows$cohort_definition_id))
  rows$cohort_name <- as.character(rows$cohort_name %||% "")
  rows$expression_type <- as.character(rows$expression_type %||% "")
  search_term <- trimws(as.character(search_term %||% ""))
  if (nzchar(search_term)) {
    lowered <- tolower(search_term)
    id_match <- suppressWarnings(as.integer(search_term))
    keep_rows <- grepl(lowered, tolower(rows$cohort_name), fixed = TRUE)
    if (!is.na(id_match)) {
      keep_rows <- keep_rows | rows$cohort_definition_id == id_match
    }
    rows <- rows[keep_rows, , drop = FALSE]
  }
  if (nrow(rows) == 0) return(rows)
  rows <- rows[order(rows$cohort_name, rows$cohort_definition_id), , drop = FALSE]
  utils::head(rows, n = limit)
}

.studyAgentSlashReadDatabaseCohortDefinition <- function(connectionDetails,
                                                         cohort_database_schema,
                                                         cohort_definition_id) {
  schema <- .studyAgentSlashValidateCohortDefinitionSchema(cohort_database_schema)
  cohort_definition_id <- suppressWarnings(as.integer(cohort_definition_id))
  if (is.na(cohort_definition_id) || cohort_definition_id <= 0L) {
    stop("cohort_definition_id must be a positive integer.")
  }
  sql <- sprintf(
    paste(
      "SELECT cd.id AS cohort_definition_id,",
      "cd.name AS cohort_name,",
      "cd.expression_type AS expression_type,",
      "cdd.expression AS expression",
      "FROM %s.cohort_definition cd",
      "LEFT JOIN %s.cohort_definition_details cdd",
      "  ON cd.id = cdd.id",
      "WHERE cd.id = %s"
    ),
    schema,
    schema,
    cohort_definition_id
  )
  connection <- DatabaseConnector::connect(connectionDetails)
  on.exit(DatabaseConnector::disconnect(connection), add = TRUE)
  rows <- DatabaseConnector::querySql(connection, sql)
  if (is.null(rows) || nrow(rows) == 0) {
    stop(sprintf("No cohort_definition row found for id %s in schema %s.", cohort_definition_id, schema))
  }
  row <- rows[1, , drop = FALSE]
  expression_type <- toupper(trimws(as.character(row$expression_type[[1]] %||% "")))
  if (!identical(expression_type, "SIMPLE_EXPRESSION")) {
    stop(sprintf(
      "Cohort definition %s in schema %s uses expression_type '%s'. Only SIMPLE_EXPRESSION is currently supported.",
      cohort_definition_id,
      schema,
      as.character(row$expression_type[[1]] %||% "")
    ))
  }
  expression_text <- as.character(row$expression[[1]] %||% "")
  if (!nzchar(trimws(expression_text))) {
    stop(sprintf(
      "Cohort definition %s in schema %s has no cohort_definition_details.expression payload.",
      cohort_definition_id,
      schema
    ))
  }
  cohort_json <- tryCatch(
    jsonlite::fromJSON(expression_text, simplifyVector = FALSE),
    error = function(e) {
      stop(sprintf(
        "Cohort definition %s in schema %s does not contain valid JSON in cohort_definition_details.expression: %s",
        cohort_definition_id,
        schema,
        conditionMessage(e)
      ))
    }
  )
  if (!is.list(cohort_json) || is.null(cohort_json$PrimaryCriteria) || is.null(cohort_json$ConceptSets)) {
    stop(sprintf(
      "Cohort definition %s in schema %s does not look like a Circe SIMPLE_EXPRESSION JSON payload.",
      cohort_definition_id,
      schema
    ))
  }
  source_id <- .studyAgentSlashDatabaseCohortSourceId(schema, cohort_definition_id)
  list(
    source_id = source_id,
    cohort_definition_id = cohort_definition_id,
    cohort_name = as.character(row$cohort_name[[1]] %||% sprintf("Cohort %s", cohort_definition_id)),
    expression_type = expression_type,
    expression_text = expression_text,
    cohort_json = cohort_json,
    metadata = list(
      source_type = "database",
      source_id = source_id,
      source_schema = schema,
      cohort_definition_id = cohort_definition_id,
      cohort_name = as.character(row$cohort_name[[1]] %||% sprintf("Cohort %s", cohort_definition_id)),
      logic_description = sprintf("Imported from %s.cohort_definition (%s).", schema, cohort_definition_id),
      expression_type = expression_type
    )
  )
}

.studyAgentSlashImportDatabaseCohortDefinition <- function(connectionDetails,
                                                           cohort_database_schema,
                                                           cohort_definition_id,
                                                           imported_def_dir) {
  imported <- .studyAgentSlashReadDatabaseCohortDefinition(
    connectionDetails = connectionDetails,
    cohort_database_schema = cohort_database_schema,
    cohort_definition_id = cohort_definition_id
  )
  dir.create(imported_def_dir, recursive = TRUE, showWarnings = FALSE)
  cache_path <- .studyAgentSlashImportedCohortDefinitionPath(imported$source_id, imported_def_dir)
  jsonlite::write_json(imported$cohort_json, cache_path, pretty = TRUE, auto_unbox = TRUE)
  imported$cache_path <- cache_path
  imported$metadata$cache_path <- cache_path
  imported
}
