`%||%` <- function(x, y) if (is.null(x)) y else x

.studyAgentSlashImportedSourceIdPattern <- function() {
  "^(db:[A-Za-z][A-Za-z0-9_]*:[0-9]+|file:[0-9]+:[A-Za-z0-9_.-]+|dir:[0-9]+:[A-Za-z0-9_.-]+)$"
}

.studyAgentSlashPhenotypeDefinitionPath <- function(phenotype_id, index_def_dir, imported_def_dir = NULL) {
  phenotype_id <- as.character(phenotype_id %||% "")
  if (grepl(.studyAgentSlashImportedSourceIdPattern(), phenotype_id)) {
    return(.studyAgentSlashImportedCohortDefinitionPath(phenotype_id, imported_def_dir))
  }
  file.path(index_def_dir, sprintf("%s.json", gsub(":", "__", phenotype_id, fixed = TRUE)))
}

.studyAgentSlashStopIfUnsupportedSelected <- function(phenotype_ids, role_label) {
  supported <- grepl("^ohdsi:[0-9]+$", phenotype_ids %||% character(0)) |
    grepl(.studyAgentSlashImportedSourceIdPattern(), phenotype_ids %||% character(0))
  unsupported <- phenotype_ids[!supported]
  if (length(unsupported) > 0) {
    stop(
      sprintf(
        paste0(
          "Selected %s cohort source ids include unsupported values (%s). ",
          "Supported ids are OHDSI phenotype ids, imported database cohort ids, and imported local cohort JSON ids."
        ),
        role_label,
        paste(unique(unsupported), collapse = ", ")
      )
    )
  }
}

.studyAgentSlashDefaultCohortIdFromSource <- function(source_id) {
  source_id <- trimws(as.character(source_id %||% ""))
  if (!nzchar(source_id)) return(NA_integer_)
  if (grepl("^ohdsi:[0-9]+$", source_id)) {
    return(suppressWarnings(as.integer(sub("^ohdsi:", "", source_id))))
  }
  if (grepl("^db:[A-Za-z][A-Za-z0-9_]*:[0-9]+$", source_id)) {
    return(suppressWarnings(as.integer(sub("^db:[A-Za-z][A-Za-z0-9_]*:([0-9]+)$", "\\1", source_id))))
  }
  if (grepl("^(file|dir):[0-9]+:[A-Za-z0-9_.-]+$", source_id)) {
    return(suppressWarnings(as.integer(sub("^(file|dir):([0-9]+):[A-Za-z0-9_.-]+$", "\\2", source_id))))
  }
  suppressWarnings(as.integer(source_id))
}

.studyAgentSlashDefaultCohortIdsFromSources <- function(source_ids, role_label = "selected") {
  source_ids <- as.character(source_ids %||% character(0))
  if (length(source_ids) == 0) return(integer(0))
  derived <- vapply(source_ids, .studyAgentSlashDefaultCohortIdFromSource, integer(1))
  if (any(is.na(derived))) {
    bad <- source_ids[is.na(derived)]
    stop(sprintf(
      "Could not derive numeric cohort IDs for %s phenotype(s): %s",
      role_label,
      paste(unique(bad), collapse = ", ")
    ))
  }
  as.integer(derived)
}

.studyAgentSlashCopyCohortJsonMulti <- function(source_id, dest_id, dest_dirs, index_def_dir, imported_def_dir = NULL, ensure_dir) {
  src <- .studyAgentSlashPhenotypeDefinitionPath(source_id, index_def_dir, imported_def_dir = imported_def_dir)
  if (!file.exists(src)) stop(sprintf("Cohort JSON not found: %s", src))
  dests <- character(0)
  for (dest_dir in dest_dirs) {
    ensure_dir(dest_dir)
    dest <- file.path(dest_dir, sprintf("%s.json", dest_id))
    file.copy(src, dest, overwrite = TRUE)
    dests <- c(dests, dest)
  }
  dests
}

.studyAgentSlashSelectionRecordFromRecommendation <- function(rec) {
  list(
    source_type = "index",
    source_id = as.character(rec$phenotype_id %||% ""),
    source_schema = NA_character_,
    cohort_definition_id = .studyAgentSlashDefaultCohortIdFromSource(rec$phenotype_id %||% NULL),
    cohort_name = as.character(rec$phenotype_name %||% ""),
    logic_description = rec$justification %||% NA_character_
  )
}

.studyAgentSlashSelectionRecordFromImport <- function(imported) {
  imported$metadata
}

.studyAgentSlashSeedDbDetailsTemplate <- function(path, write_json) {
  if (!file.exists(path)) {
    write_json(list(
      dbms = "postgresql",
      authType = "username_password",
      DB_SERVER = "",
      DB_PORT = "5432",
      DB_USER = "",
      DB_PASS = "",
      DB_DRIVER_PATH = "",
      DATABASECONNECTOR_JAR_FOLDER = "",
      extraSettings = "sslmode=disable"
    ), path)
  }
  invisible(path)
}

.studyAgentSlashSeedRuntimeTemplates <- function(base_dir, write_json) {
  db_details_path <- file.path(base_dir, "strategus-db-details.json")
  cohort_source_db_details_path <- file.path(base_dir, "strategus-cohort-source-db-details.json")
  execution_settings_path <- file.path(base_dir, "strategus-execution-settings.json")

  .studyAgentSlashSeedDbDetailsTemplate(db_details_path, write_json = write_json)
  .studyAgentSlashSeedDbDetailsTemplate(cohort_source_db_details_path, write_json = write_json)

  if (!file.exists(execution_settings_path)) {
    write_json(list(
      cdmDatabaseSchema = "",
      workDatabaseSchema = "",
      resultsDatabaseSchema = "",
      vocabularyDatabaseSchema = "",
      cohortTable = "cohort",
      workFolder = file.path(base_dir, "work"),
      resultsFolder = file.path(base_dir, "results"),
      cohortIdFieldName = "cohort_definition_id",
      maxCores = 4,
      incremental = FALSE
    ), execution_settings_path)
  }

  list(
    db_details_path = db_details_path,
    cohort_source_db_details_path = cohort_source_db_details_path,
    execution_settings_path = execution_settings_path
  )
}

.studyAgentSlashCohortSourceDbDetailsNeedConfiguration <- function(path, readStrategusDbDetails) {
  db_config <- tryCatch(readStrategusDbDetails(path), error = function(e) NULL)
  if (is.null(db_config)) return(TRUE)
  auth_type <- tolower(trimws(as.character(
    db_config$authType %||%
      db_config$authenticationType %||%
      if (isTRUE(db_config$useWindowsAuth %||% FALSE)) "windows" else "username_password"
  )))
  if (!nzchar(auth_type)) auth_type <- "username_password"
  server <- trimws(as.character(db_config$DB_SERVER %||% db_config$server %||% ""))
  if (!nzchar(server)) return(TRUE)
  if (auth_type %in% c("windows", "integrated", "integrated_windows")) return(FALSE)
  user <- trimws(as.character(db_config$DB_USER %||% db_config$user %||% ""))
  raw_password <- db_config$DB_PASS %||% db_config$password
  is.null(raw_password) || !nzchar(user)
}

.studyAgentSlashChooseSelectionSourceMode <- function(role_label, allow_index = TRUE, interactive = TRUE, readline_with_navigation, is_back_signal) {
  if (!isTRUE(interactive)) {
    if (isTRUE(allow_index)) return("index")
    stop("Non-interactive direct cohort acquisition requires explicit source handling and is not implemented for this shell.")
  }
  repeat {
    prompt <- if (isTRUE(allow_index)) {
      sprintf("Source for %s cohort [ai=agentic search (default), file=JSON file, dir=directory, db=database cohort]: ", role_label)
    } else {
      sprintf("Source for %s cohort [file=JSON file, dir=directory, db=database cohort]: ", role_label)
    }
    entered <- trimws(readline_with_navigation(prompt))
    if (is_back_signal(entered)) return(entered)
    lowered <- tolower(entered)
    if (isTRUE(allow_index) && (!nzchar(lowered) || lowered %in% c("ai", "index", "search", "s", "recommend", "agentic"))) return("index")
    if (lowered %in% c("db", "database", "existing")) return("database")
    if (lowered %in% c("file", "json", "local")) return("file")
    if (lowered %in% c("dir", "directory", "folder")) return("directory")
    cat(if (isTRUE(allow_index)) "Choose ai, file, dir, or db, or press Enter for the default.\n" else "Choose file, dir, or db.\n")
  }
}

.studyAgentSlashPromptDatabaseCohortImports <- function(role_label,
                                                        allow_multiple = FALSE,
                                                        base_dir,
                                                        imported_definition_dir,
                                                        interactive = TRUE,
                                                        readline_with_navigation,
                                                        readline_with_dialogue,
                                                        is_back_signal,
                                                        write_json,
                                                        readStrategusDbDetails,
                                                        normalizeStrategusDbConfig,
                                                        createStrategusConnectionDetails) {
  db_details_path <- file.path(base_dir, "strategus-cohort-source-db-details.json")
  .studyAgentSlashSeedDbDetailsTemplate(db_details_path, write_json = write_json)
  if (isTRUE(.studyAgentSlashCohortSourceDbDetailsNeedConfiguration(db_details_path, readStrategusDbDetails = readStrategusDbDetails))) {
    cat(sprintf(
      "Database cohort import requires a populated %s. Fill in the cohort-source DB connection details there and then retry the db import option.\n",
      db_details_path
    ))
    return(NULL)
  }
  repeat {
    if (isTRUE(.studyAgentSlashCohortSourceDbDetailsNeedConfiguration(db_details_path, readStrategusDbDetails = readStrategusDbDetails))) {
      cat(sprintf(
        "Database cohort import requires a populated %s. Fill in the cohort-source DB connection details there and then retry the db import option.\n",
        db_details_path
      ))
      return(NULL)
    }
    normalized_db_config <- tryCatch(
      normalizeStrategusDbConfig(path = db_details_path),
      error = function(e) e
    )
    if (inherits(normalized_db_config, "error")) {
      cat(sprintf(
        "Cannot use database cohort import until %s is populated: %s\n",
        db_details_path,
        conditionMessage(normalized_db_config)
      ))
      return(NULL)
    }
    cat(sprintf(
      "Using %s connection details: server=%s, port=%s, authType=%s\n",
      as.character(normalized_db_config$dbms %||% "database"),
      as.character(normalized_db_config$server %||% ""),
      as.character(normalized_db_config$port %||% ""),
      as.character(normalized_db_config$authType %||% "")
    ))
    connectionDetails <- tryCatch(
      createStrategusConnectionDetails(path = db_details_path, dbDetails = normalized_db_config$dbConfig),
      error = function(e) e
    )
    if (inherits(connectionDetails, "error")) {
      cat(sprintf(
        "Cannot use database cohort import until %s is populated: %s\n",
        db_details_path,
        conditionMessage(connectionDetails)
      ))
      return(NULL)
    }
    schema_value <- readline_with_navigation(sprintf(
      "Schema containing cohort_definition and cohort_definition_details for the %s cohort: ",
      role_label
    ))
    if (is_back_signal(schema_value)) return(schema_value)
    schema_value <- trimws(as.character(schema_value %||% ""))
    if (!nzchar(schema_value)) {
      cat("Enter a schema name.\n")
      next
    }
    search_term <- trimws(readline_with_dialogue(sprintf(
      "Optional %s cohort name search term [Enter=list candidates]: ",
      role_label
    )))
    candidates <- tryCatch(
      .studyAgentSlashListDatabaseCohortDefinitions(
        connectionDetails = connectionDetails,
        cohort_database_schema = schema_value,
        search_term = search_term,
        sort_by = "id"
      ),
      error = function(e) e
    )
    if (inherits(candidates, "error")) {
      cat(sprintf("Database cohort lookup failed: %s\n", conditionMessage(candidates)))
      next
    }
    if (nrow(candidates) == 0) {
      cat("No matching cohort definitions were found. Try a different schema or search term.\n")
      next
    }
    preview <- data.frame(
      cohort_definition_id = candidates$cohort_definition_id,
      cohort_name = candidates$cohort_name,
      stringsAsFactors = FALSE
    )
    preview <- preview[order(preview$cohort_definition_id, preview$cohort_name), , drop = FALSE]
    rownames(preview) <- as.character(preview$cohort_definition_id)
    cat(sprintf("\nAvailable %s cohort definitions from %s\n", role_label, schema_value))
    print(preview, row.names = TRUE)
    labels <- sprintf("[%s] %s", preview$cohort_definition_id, preview$cohort_name)
    selected_ids <- integer(0)
    invalid <- character(0)
    if (isTRUE(interactive)) {
      menu_pick <- tryCatch(
        utils::select.list(
          labels,
          multiple = isTRUE(allow_multiple),
          title = sprintf("Select %s cohort definition%s", role_label, if (isTRUE(allow_multiple)) "(s)" else "")
        ),
        error = function(e) NULL
      )
      if (length(menu_pick) > 0 && any(nzchar(menu_pick))) {
        selected_ids <- unique(vapply(menu_pick[nzchar(menu_pick)], function(label) {
          idx <- which(labels == label)[1]
          preview$cohort_definition_id[[idx]]
        }, integer(1)))
      }
    }
    if (length(selected_ids) == 0) {
      selection_prompt <- if (isTRUE(allow_multiple)) {
        sprintf("Select %s cohort row numbers or cohort_definition ids (comma-separated): ", role_label)
      } else {
        sprintf("Select the %s cohort row number or cohort_definition id: ", role_label)
      }
      selected_raw <- trimws(readline_with_dialogue(selection_prompt))
      if (!nzchar(selected_raw)) {
        cat("No cohort selected.\n")
        next
      }
      selected_parts <- trimws(strsplit(selected_raw, ",", fixed = TRUE)[[1]])
      selected_parts <- selected_parts[nzchar(selected_parts)]
      if (length(selected_parts) == 0) {
        cat("No cohort selected.\n")
        next
      }
      for (part in selected_parts) {
        parsed <- suppressWarnings(as.integer(part))
        if (is.na(parsed)) {
          invalid <- c(invalid, part)
          next
        }
        if (parsed %in% preview$cohort_definition_id) {
          selected_ids <- c(selected_ids, parsed)
        } else if (parsed >= 1L && parsed <= nrow(preview)) {
          selected_ids <- c(selected_ids, preview$cohort_definition_id[[parsed]])
        } else {
          invalid <- c(invalid, part)
        }
      }
    }
    selected_ids <- unique(selected_ids)
    if (length(invalid) > 0 || length(selected_ids) == 0) {
      cat(sprintf("Invalid selection: %s\n", paste(unique(invalid), collapse = ", ")))
      next
    }
    imported <- lapply(selected_ids, function(id) {
      .studyAgentSlashImportDatabaseCohortDefinition(
        connectionDetails = connectionDetails,
        cohort_database_schema = schema_value,
        cohort_definition_id = id,
        imported_def_dir = imported_definition_dir
      )
    })
    return(imported)
  }
}

.studyAgentSlashPromptFileCohortImports <- function(role_label,
                                                    allow_multiple = FALSE,
                                                    imported_definition_dir,
                                                    readline_with_navigation,
                                                    is_back_signal) {
  repeat {
    prompt <- if (isTRUE(allow_multiple)) {
      sprintf("Path to %s cohort JSON file(s) [comma-separated]: ", role_label)
    } else {
      sprintf("Path to %s cohort JSON file: ", role_label)
    }
    entered <- trimws(readline_with_navigation(prompt))
    if (is_back_signal(entered)) return(entered)
    if (!nzchar(entered)) {
      cat("Enter a cohort JSON file path.\n")
      next
    }
    parts <- trimws(strsplit(entered, ",", fixed = TRUE)[[1]])
    parts <- parts[nzchar(parts)]
    if (!isTRUE(allow_multiple) && length(parts) > 1L) {
      cat("Select exactly one cohort JSON file for this role.\n")
      next
    }
    imported <- tryCatch(
      lapply(parts, function(file_path) {
        .studyAgentSlashImportFileCohortDefinition(
          path = file_path,
          imported_def_dir = imported_definition_dir,
          source_type = "file"
        )
      }),
      error = function(e) e
    )
    if (inherits(imported, "error")) {
      cat(sprintf("File cohort import failed: %s\n", conditionMessage(imported)))
      next
    }
    return(imported)
  }
}

.studyAgentSlashPromptDirectoryCohortImports <- function(role_label,
                                                         allow_multiple = FALSE,
                                                         imported_definition_dir,
                                                         interactive = TRUE,
                                                         readline_with_navigation,
                                                         readline_with_dialogue,
                                                         is_back_signal) {
  repeat {
    directory <- trimws(readline_with_navigation(sprintf(
      "Directory containing %s cohort JSON files: ",
      role_label
    )))
    if (is_back_signal(directory)) return(directory)
    if (!nzchar(directory)) {
      cat("Enter a directory path.\n")
      next
    }
    candidates <- tryCatch(
      .studyAgentSlashListLocalCohortDefinitionFiles(directory, limit = 100L),
      error = function(e) e
    )
    if (inherits(candidates, "error")) {
      cat(sprintf("Directory cohort lookup failed: %s\n", conditionMessage(candidates)))
      next
    }
    if (nrow(candidates) == 0) {
      cat("No readable cohort JSON files were found in that directory.\n")
      next
    }
    preview <- data.frame(
      cohort_definition_id = candidates$cohort_definition_id,
      cohort_name = candidates$cohort_name,
      path = candidates$path,
      stringsAsFactors = FALSE
    )
    rownames(preview) <- seq_len(nrow(preview))
    cat(sprintf("\nAvailable %s cohort JSON files from %s\n", role_label, normalizePath(directory, winslash = "/", mustWork = FALSE)))
    print(preview, row.names = TRUE)
    labels <- sprintf("[%s] %s", preview$cohort_definition_id, preview$cohort_name)
    selected_rows <- integer(0)
    invalid <- character(0)
    if (isTRUE(interactive)) {
      menu_pick <- tryCatch(
        utils::select.list(
          labels,
          multiple = isTRUE(allow_multiple),
          title = sprintf("Select %s cohort JSON%s", role_label, if (isTRUE(allow_multiple)) "(s)" else "")
        ),
        error = function(e) NULL
      )
      if (length(menu_pick) > 0 && any(nzchar(menu_pick))) {
        selected_rows <- unique(vapply(menu_pick[nzchar(menu_pick)], function(label) {
          which(labels == label)[1]
        }, integer(1)))
      }
    }
    if (length(selected_rows) == 0) {
      selection_prompt <- if (isTRUE(allow_multiple)) {
        sprintf("Select %s cohort row numbers (comma-separated): ", role_label)
      } else {
        sprintf("Select the %s cohort row number: ", role_label)
      }
      selected_raw <- trimws(readline_with_dialogue(selection_prompt))
      if (!nzchar(selected_raw)) {
        cat("No cohort selected.\n")
        next
      }
      selected_parts <- trimws(strsplit(selected_raw, ",", fixed = TRUE)[[1]])
      selected_parts <- selected_parts[nzchar(selected_parts)]
      for (part in selected_parts) {
        parsed <- suppressWarnings(as.integer(part))
        if (is.na(parsed) || parsed < 1L || parsed > nrow(preview)) {
          invalid <- c(invalid, part)
        } else {
          selected_rows <- c(selected_rows, parsed)
        }
      }
    }
    selected_rows <- unique(selected_rows)
    if (length(invalid) > 0 || length(selected_rows) == 0) {
      cat(sprintf("Invalid selection: %s\n", paste(unique(invalid), collapse = ", ")))
      next
    }
    imported <- tryCatch(
      lapply(selected_rows, function(row_idx) {
        .studyAgentSlashImportFileCohortDefinition(
          path = preview$path[[row_idx]],
          imported_def_dir = imported_definition_dir,
          source_type = "directory"
        )
      }),
      error = function(e) e
    )
    if (inherits(imported, "error")) {
      cat(sprintf("Directory cohort import failed: %s\n", conditionMessage(imported)))
      next
    }
    return(imported)
  }
}

.studyAgentSlashAcquireImportedRoleSelection <- function(source_mode,
                                                         role_label,
                                                         allow_multiple = FALSE,
                                                         interactive = TRUE,
                                                         step_messages = list(database = NULL, file = NULL, directory = NULL),
                                                         prompt_database_imports,
                                                         prompt_file_imports,
                                                         prompt_directory_imports,
                                                         selection_record_from_import = .studyAgentSlashSelectionRecordFromImport) {
  if (!(source_mode %in% c("database", "file", "directory"))) return(NULL)
  if (isTRUE(interactive)) {
    step_message <- step_messages[[source_mode]] %||% NULL
    if (nzchar(trimws(as.character(step_message %||% "")))) {
      cat(sprintf("\n== %s ==\n", step_message))
    }
  }
  imported <- switch(
    source_mode,
    database = prompt_database_imports(role_label, allow_multiple = allow_multiple),
    file = prompt_file_imports(role_label, allow_multiple = allow_multiple),
    directory = prompt_directory_imports(role_label, allow_multiple = allow_multiple)
  )
  if (inherits(imported, "workflow_navigation_signal")) return(imported)
  if (is.null(imported) || length(imported) == 0) {
    return(list(action = "retry", imported = imported))
  }
  imported_items <- imported
  list(
    action = "handled",
    imported = imported_items,
    selected_source_ids = as.character(vapply(imported_items, function(item) item$source_id %||% "", character(1))),
    selected_ids = as.integer(vapply(imported_items, function(item) item$cohort_definition_id, integer(1))),
    records = lapply(imported_items, selection_record_from_import)
  )
}
