.studyAgentSlashReadCsvSafe <- function(path) {
  if (is.null(path) || !nzchar(trimws(as.character(path))) || !file.exists(path)) {
    return(NULL)
  }
  tryCatch(
    utils::read.csv(path, stringsAsFactors = FALSE, check.names = FALSE),
    error = function(e) NULL
  )
}

.studyAgentSlashCompactPreviewTable <- function(data, max_rows = 12L, max_cols = 8L) {
  if (is.null(data)) return(NULL)
  if (!is.data.frame(data)) data <- as.data.frame(data, stringsAsFactors = FALSE)
  if (ncol(data) > max_cols) data <- data[, seq_len(max_cols), drop = FALSE]
  utils::head(data, n = max_rows)
}


.studyAgentSlashSupportsDataViewer <- function() {
  isTRUE(interactive()) &&
    exists("View", where = asNamespace("utils"), mode = "function", inherits = FALSE)
}

.studyAgentSlashOpenTableViewer <- function(data, title = "Study Agent") {
  if (!isTRUE(.studyAgentSlashSupportsDataViewer()) || is.null(data)) return(FALSE)
  if (!is.data.frame(data)) data <- as.data.frame(data, stringsAsFactors = FALSE)
  utils::View(data, title = as.character(title %||% "Study Agent"))
  TRUE
}

.studyAgentSlashExplorationTableSection <- function(data,
                                                    title,
                                                    preview_data = NULL) {
  list(
    kind = "table",
    data = preview_data %||% data,
    view_data = data,
    view_title = as.character(title %||% "Study Agent")
  )
}

.studyAgentSlashResolveArtifactPath <- function(path, base_dir) {
  path <- as.character(path %||% "")
  if (!nzchar(trimws(path))) {
    return(.studyAgentSlashResolveProjectPath(path, base_dir))
  }
  if (grepl("^(?:[A-Za-z]:[/\\]|/|~)", path)) {
    return(normalizePath(path, winslash = "/", mustWork = FALSE))
  }

  candidates <- unique(c(
    .studyAgentSlashResolveProjectPath(path, base_dir),
    normalizePath(file.path(dirname(base_dir), path), winslash = "/", mustWork = FALSE),
    normalizePath(file.path(dirname(dirname(base_dir)), path), winslash = "/", mustWork = FALSE),
    normalizePath(file.path(getwd(), path), winslash = "/", mustWork = FALSE)
  ))
  existing <- Filter(function(candidate) {
    file.exists(candidate) || dir.exists(candidate)
  }, candidates)
  if (length(existing) > 0) {
    return(existing[[1]])
  }
  candidates[[1]]
}

.studyAgentSlashNewExplorationArtifact <- function(id,
                                                   artifact_class,
                                                   path,
                                                   base_dir,
                                                   type = NULL,
                                                   step_id = NULL,
                                                   status = NULL,
                                                   explorable = TRUE,
                                                   preview_kind = "table",
                                                   tags = character(0),
                                                   metadata = list()) {
  absolute_path <- .studyAgentSlashResolveProjectPath(path, base_dir)
  list(
    id = as.character(id),
    artifact_class = as.character(artifact_class),
    path = .studyAgentSlashRelativizeProjectPath(absolute_path, base_dir),
    absolute_path = absolute_path,
    exists = isTRUE(file.exists(absolute_path)),
    type = if (is.null(type)) NULL else as.character(type),
    step_id = if (is.null(step_id)) NULL else as.character(step_id),
    status = if (is.null(status)) NULL else as.character(status),
    explorable = isTRUE(explorable),
    preview_kind = as.character(preview_kind %||% "table"),
    tags = as.list(as.character(tags %||% character(0))),
    metadata = metadata %||% list()
  )
}

.studyAgentSlashArtifactClassFromPath <- function(path, artifact_id = "") {
  path <- as.character(path %||% "")
  artifact_id <- as.character(artifact_id %||% "")
  base_name <- basename(path)
  if (identical(base_name, "Cohorts.csv")) return("cohort_definition_set_csv")
  if (identical(base_name, "strategus-db-details.json")) return("db_details_json")
  if (identical(base_name, "strategus-execution-settings.json")) return("execution_settings_json")
  if (identical(base_name, "cmAnalysis.json")) return("analysis_settings_json")
  if (identical(base_name, "cg_cohort_definition.csv")) return("cohort_definition_csv")
  if (identical(base_name, "cg_cohort_count.csv")) return("cohort_counts_csv")
  if (identical(base_name, "cg_cohort_inclusion.csv")) return("cohort_inclusion_csv")
  if (identical(base_name, "cg_cohort_inc_result.csv")) return("cohort_inclusion_result_csv")
  if (identical(base_name, "cg_cohort_inc_stats.csv")) return("cohort_inclusion_stats_csv")
  if (identical(base_name, "cg_cohort_summary_stats.csv")) return("cohort_summary_stats_csv")
  if (grepl("/keeper-case-review/", path, fixed = TRUE)) return("keeper_artifact")
  if (grepl("/scripts/", path, fixed = TRUE) || endsWith(path, ".R")) return("script")
  if (dir.exists(path) && identical(base_name, "CohortGeneratorModule")) return("cohort_generation_module_dir")
  if (dir.exists(path) && identical(base_name, "cohort-generation-results")) return("cohort_generation_results_dir")
  if (dir.exists(path) && identical(base_name, "cohort-generation-work")) return("cohort_generation_work_dir")
  if (nzchar(artifact_id) && grepl("cm_analysis", artifact_id, fixed = TRUE)) return("analysis_settings_json")
  "generic"
}

.studyAgentSlashRegisterExplorationArtifact <- function(registry,
                                                        id,
                                                        artifact_class,
                                                        path,
                                                        base_dir,
                                                        type = NULL,
                                                        step_id = NULL,
                                                        status = NULL,
                                                        explorable = TRUE,
                                                        preview_kind = "table",
                                                        tags = character(0),
                                                        metadata = list()) {
  registry[[as.character(id)]] <- .studyAgentSlashNewExplorationArtifact(
    id = id,
    artifact_class = artifact_class,
    path = path,
    base_dir = base_dir,
    type = type,
    step_id = step_id,
    status = status,
    explorable = explorable,
    preview_kind = preview_kind,
    tags = tags,
    metadata = metadata
  )
  registry
}

.studyAgentSlashMaybeRegisterKnownArtifact <- function(registry,
                                                       id,
                                                       path,
                                                       base_dir,
                                                       step_id = NULL,
                                                       tags = character(0),
                                                       explorable = TRUE,
                                                       preview_kind = "table") {
  absolute_path <- .studyAgentSlashResolveProjectPath(path, base_dir)
  registry <- .studyAgentSlashRegisterExplorationArtifact(
    registry = registry,
    id = id,
    artifact_class = .studyAgentSlashArtifactClassFromPath(absolute_path, id),
    path = absolute_path,
    base_dir = base_dir,
    step_id = step_id,
    explorable = explorable,
    preview_kind = preview_kind,
    tags = tags
  )
  registry
}

.studyAgentSlashBuildArtifactRegistry <- function(base_dir) {
  project_state <- .studyAgentSlashReadProjectState(base_dir)
  registry <- list()

  for (name in names(project_state$artifacts %||% list())) {
    artifact <- project_state$artifacts[[name]] %||% list()
    artifact_path <- as.character(artifact$path %||% "")
    if (!nzchar(artifact_path)) next
    absolute_path <- .studyAgentSlashResolveProjectPath(artifact_path, base_dir)
    registry[[name]] <- .studyAgentSlashNewExplorationArtifact(
      id = name,
      artifact_class = .studyAgentSlashArtifactClassFromPath(absolute_path, name),
      path = absolute_path,
      base_dir = base_dir,
      type = artifact$type %||% NULL,
      step_id = artifact$step_id %||% NULL,
      status = artifact$status %||% NULL,
      explorable = !identical(as.character(artifact$type %||% ""), "script"),
      preview_kind = if (dir.exists(absolute_path)) "dir" else "table",
      tags = as.character(unlist(artifact$tags %||% character(0), use.names = FALSE)),
      metadata = artifact$metadata %||% list()
    )
  }

  registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "db_details_json", file.path(base_dir, "strategus-db-details.json"), base_dir, tags = c("config", "db"), preview_kind = "json")
  registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "execution_settings_json", file.path(base_dir, "strategus-execution-settings.json"), base_dir, tags = c("config", "execution"), preview_kind = "json")
  registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "selected_cohorts_csv", file.path(base_dir, "selected-cohorts", "Cohorts.csv"), base_dir, step_id = "generate_cohorts", tags = c("cohort", "selection"))

  exec_settings_path <- file.path(base_dir, "strategus-execution-settings.json")
  if (file.exists(exec_settings_path)) {
    exec_cfg <- tryCatch(readStrategusExecutionSettings(exec_settings_path), error = function(e) NULL)
    if (is.list(exec_cfg)) {
      results_root <- .studyAgentSlashResolveArtifactPath(exec_cfg$resultsFolder %||% "", base_dir)
      work_root <- .studyAgentSlashResolveArtifactPath(exec_cfg$workFolder %||% "", base_dir)
      registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cohort_generation_results_dir", results_root, base_dir, step_id = "generate_cohorts", tags = c("results", "cohort_generation"), preview_kind = "dir")
      registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cohort_generation_work_dir", work_root, base_dir, step_id = "generate_cohorts", tags = c("work", "cohort_generation"), preview_kind = "dir")
      cg_dir <- file.path(results_root, "CohortGeneratorModule")
      registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cohort_generation_module_dir", cg_dir, base_dir, step_id = "generate_cohorts", tags = c("results", "cohort_generation"), preview_kind = "dir")
      registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cg_cohort_count_csv", file.path(cg_dir, "cg_cohort_count.csv"), base_dir, step_id = "generate_cohorts", tags = c("results", "counts"))
      registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cg_cohort_definition_csv", file.path(cg_dir, "cg_cohort_definition.csv"), base_dir, step_id = "generate_cohorts", tags = c("results", "definitions"))
      registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cg_cohort_inclusion_csv", file.path(cg_dir, "cg_cohort_inclusion.csv"), base_dir, step_id = "generate_cohorts", tags = c("results", "inclusion"))
      registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cg_cohort_inc_result_csv", file.path(cg_dir, "cg_cohort_inc_result.csv"), base_dir, step_id = "generate_cohorts", tags = c("results", "inclusion"))
      registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cg_cohort_inc_stats_csv", file.path(cg_dir, "cg_cohort_inc_stats.csv"), base_dir, step_id = "generate_cohorts", tags = c("results", "inclusion"))
      registry <- .studyAgentSlashMaybeRegisterKnownArtifact(registry, "cg_cohort_summary_stats_csv", file.path(cg_dir, "cg_cohort_summary_stats.csv"), base_dir, step_id = "generate_cohorts", tags = c("results", "summary"))
    }
  }

  registry
}

.studyAgentSlashArtifactRegistryForStep <- function(base_dir, step_id = NULL) {
  registry <- .studyAgentSlashBuildArtifactRegistry(base_dir)
  if (is.null(step_id) || !nzchar(trimws(as.character(step_id)))) return(registry)
  Filter(function(item) {
    item_step <- as.character(item$step_id %||% "")
    !nzchar(item_step) || identical(item_step, as.character(step_id))
  }, registry)
}

.studyAgentSlashArtifactRegistryTable <- function(registry) {
  rows <- lapply(registry, function(item) {
    data.frame(
      artifact_id = as.character(item$id %||% ""),
      artifact_class = as.character(item$artifact_class %||% ""),
      exists = isTRUE(item$exists),
      step_id = as.character(item$step_id %||% ""),
      path = as.character(item$path %||% item$absolute_path %||% ""),
      stringsAsFactors = FALSE
    )
  })
  if (length(rows) == 0) {
    return(data.frame(artifact_id = character(0), artifact_class = character(0), exists = logical(0), step_id = character(0), path = character(0), stringsAsFactors = FALSE))
  }
  do.call(rbind, rows)
}

.studyAgentSlashBuildExplorationContext <- function(base_dir, project_state, runtime_state, step = NULL) {
  registry <- .studyAgentSlashBuildArtifactRegistry(base_dir)
  step_id <- as.character(step$step_id %||% project_state$resume$current_step_id %||% "")
  list(
    base_dir = base_dir,
    project_state = project_state,
    runtime_state = runtime_state,
    workflow_type = as.character(project_state$workflow_type %||% ""),
    study_context = project_state$study_context %||% list(),
    current_step_id = step_id,
    current_step_label = as.character(step$label %||% ""),
    artifact_registry = registry,
    artifact_registry_table = .studyAgentSlashArtifactRegistryTable(registry)
  )
}

.studyAgentSlashExplorationCommands <- function() {
  list(
    list(
      command_id = "artifact_inventory",
      label = "List known artifacts",
      purpose = "Show artifact ids, classes, paths, and existence.",
      workflow_types = c("strategus_incidence", "strategus_cohort_methods"),
      step_ids = character(0),
      required_packages = character(0),
      artifact_requirements = character(0),
      input_parameters = list(),
      output_kind = "table",
      safe = TRUE,
      executor = function(context) {
        list(
          status = "ok",
          title = "Artifact inventory",
          sections = list(
            .studyAgentSlashExplorationTableSection(
              data = context$artifact_registry_table,
              title = "Artifact inventory",
              preview_data = .studyAgentSlashCompactPreviewTable(context$artifact_registry_table, max_rows = 40L, max_cols = 5L)
            )
          )
        )
      }
    ),
    list(
      command_id = "results_dir_inventory",
      label = "Inventory cohort generation result files",
      purpose = "List generated result files with relative paths and sizes.",
      workflow_types = c("strategus_incidence", "strategus_cohort_methods"),
      step_ids = c("generate_cohorts", "keeper_concept_sets", "keeper_case_review", "diagnostics", "incidence_spec", "cm_spec"),
      required_packages = character(0),
      artifact_requirements = c("cohort_generation_results_dir"),
      input_parameters = list(),
      output_kind = "table",
      safe = TRUE,
      executor = function(context) {
        root <- (context$artifact_registry$cohort_generation_results_dir %||% list())$absolute_path %||% NULL
        if (is.null(root) || !dir.exists(root)) stop("Cohort generation results directory is not available.")
        paths <- list.files(root, recursive = TRUE, full.names = TRUE, all.files = FALSE, no.. = TRUE)
        if (length(paths) == 0) {
          table <- data.frame(relative_path = character(0), size_bytes = numeric(0), modified_at = character(0), stringsAsFactors = FALSE)
        } else {
          info <- file.info(paths)
          prefix <- paste0(normalizePath(root, winslash = "/", mustWork = FALSE), "/")
          rel <- sub(paste0("^", gsub("([.|()\\^{}+$*?]|\\[|\\])", "\\\\\\1", prefix)), "", normalizePath(paths, winslash = "/", mustWork = FALSE))
          table <- data.frame(
            relative_path = rel,
            size_bytes = as.numeric(info$size),
            modified_at = as.character(info$mtime),
            stringsAsFactors = FALSE
          )
        }
        list(
          status = "ok",
          title = "Cohort generation results inventory",
          sections = list(
            .studyAgentSlashExplorationTableSection(
              data = table,
              title = "Cohort generation results inventory",
              preview_data = .studyAgentSlashCompactPreviewTable(table, max_rows = 40L, max_cols = 3L)
            )
          )
        )
      }
    ),
    list(
      command_id = "cohort_definition_preview",
      label = "Preview selected cohort definitions",
      purpose = "Show selected cohort ids, names, and roles.",
      workflow_types = c("strategus_incidence", "strategus_cohort_methods"),
      step_ids = c("generate_cohorts", "keeper_concept_sets", "keeper_case_review", "diagnostics", "incidence_spec", "cm_spec"),
      required_packages = character(0),
      artifact_requirements = c("cohort_definition_set_csv"),
      input_parameters = list(),
      output_kind = "table",
      safe = TRUE,
      executor = function(context) {
        path <- (context$artifact_registry$selected_cohorts_csv %||% list())$absolute_path %||% NULL
        data <- .studyAgentSlashReadCsvSafe(path)
        if (is.null(data)) stop("Selected cohort definition file is not available.")
        keep <- intersect(c("atlas_id", "cohort_id", "cohort_name", "cohort_type", "logic_description", "generate_stats"), names(data))
        selected <- data[, keep, drop = FALSE]
        list(
          status = "ok",
          title = "Selected cohort definitions",
          sections = list(
            .studyAgentSlashExplorationTableSection(
              data = selected,
              title = "Selected cohort definitions",
              preview_data = .studyAgentSlashCompactPreviewTable(selected, max_rows = 20L, max_cols = 6L)
            )
          )
        )
      }
    ),
    list(
      command_id = "cohort_counts_summary",
      label = "Summarize generated cohort counts",
      purpose = "Show cohort entries and subjects for generated cohorts.",
      workflow_types = c("strategus_incidence", "strategus_cohort_methods"),
      step_ids = c("generate_cohorts", "keeper_concept_sets", "keeper_case_review", "diagnostics", "incidence_spec", "cm_spec"),
      required_packages = c("CohortGenerator"),
      artifact_requirements = c("cohort_counts_csv"),
      input_parameters = list(),
      output_kind = "table",
      safe = TRUE,
      executor = function(context) {
        counts_path <- (context$artifact_registry$cg_cohort_count_csv %||% list())$absolute_path %||% NULL
        selected_path <- (context$artifact_registry$selected_cohorts_csv %||% list())$absolute_path %||% NULL
        counts <- .studyAgentSlashReadCsvSafe(counts_path)
        if (is.null(counts)) stop("Cohort counts file is not available.")
        selected <- .studyAgentSlashReadCsvSafe(selected_path)
        if (!is.null(selected) && all(c("cohort_id", "cohort_name") %in% names(selected))) {
          counts <- merge(counts, unique(selected[, c("cohort_id", "cohort_name"), drop = FALSE]), by = "cohort_id", all.x = TRUE, sort = FALSE)
        }
        keep <- intersect(c("cohort_id", "cohort_name", "cohort_entries", "cohort_subjects", "database_id"), names(counts))
        if ("cohort_entries" %in% names(counts)) counts <- counts[order(-counts$cohort_entries, counts$cohort_id), , drop = FALSE]
        selected <- counts[, keep, drop = FALSE]
        list(
          status = "ok",
          title = "Generated cohort counts",
          sections = list(
            .studyAgentSlashExplorationTableSection(
              data = selected,
              title = "Generated cohort counts",
              preview_data = .studyAgentSlashCompactPreviewTable(selected, max_rows = 20L, max_cols = 5L)
            )
          )
        )
      }
    ),
    list(
      command_id = "inclusion_rules_preview",
      label = "Preview inclusion rule attrition",
      purpose = "Show inclusion rules and attrition counts for generated cohorts.",
      workflow_types = c("strategus_incidence", "strategus_cohort_methods"),
      step_ids = c("generate_cohorts", "keeper_concept_sets", "keeper_case_review", "diagnostics", "incidence_spec", "cm_spec"),
      required_packages = c("CohortGenerator"),
      artifact_requirements = c("cohort_inclusion_csv", "cohort_inclusion_stats_csv"),
      input_parameters = list(),
      output_kind = "table",
      safe = TRUE,
      executor = function(context) {
        inclusion <- .studyAgentSlashReadCsvSafe((context$artifact_registry$cg_cohort_inclusion_csv %||% list())$absolute_path %||% NULL)
        stats <- .studyAgentSlashReadCsvSafe((context$artifact_registry$cg_cohort_inc_stats_csv %||% list())$absolute_path %||% NULL)
        selected <- .studyAgentSlashReadCsvSafe((context$artifact_registry$selected_cohorts_csv %||% list())$absolute_path %||% NULL)
        if (is.null(inclusion) || is.null(stats)) stop("Inclusion rule artifacts are not available.")
        if ("mode_id" %in% names(stats)) stats <- subset(stats, mode_id == 0)
        merged <- merge(stats, inclusion, by = c("cohort_definition_id", "rule_sequence"), all.x = TRUE, sort = FALSE)
        if (!is.null(selected) && all(c("cohort_id", "cohort_name") %in% names(selected))) {
          merged <- merge(merged, unique(selected[, c("cohort_id", "cohort_name"), drop = FALSE]), by.x = "cohort_definition_id", by.y = "cohort_id", all.x = TRUE, sort = FALSE)
        }
        keep <- intersect(c("cohort_definition_id", "cohort_name", "rule_sequence", "name", "person_count", "gain_count", "person_total"), names(merged))
        selected <- merged[, keep, drop = FALSE]
        list(
          status = "ok",
          title = "Inclusion rule attrition",
          sections = list(
            .studyAgentSlashExplorationTableSection(
              data = selected,
              title = "Inclusion rule attrition",
              preview_data = .studyAgentSlashCompactPreviewTable(selected, max_rows = 20L, max_cols = 7L)
            )
          )
        )
      }
    ),
    list(
      command_id = "cohort_stats_preview",
      label = "Preview cohort generation statistics files",
      purpose = "Show available cohort-generation statistic files and a compact row sample from each.",
      workflow_types = c("strategus_incidence", "strategus_cohort_methods"),
      step_ids = c("generate_cohorts", "keeper_concept_sets", "keeper_case_review", "diagnostics", "incidence_spec", "cm_spec"),
      required_packages = character(0),
      artifact_requirements = c("cohort_generation_module_dir"),
      input_parameters = list(),
      output_kind = "mixed",
      safe = TRUE,
      executor = function(context) {
        keys <- c("cg_cohort_count_csv", "cg_cohort_inclusion_csv", "cg_cohort_inc_result_csv", "cg_cohort_inc_stats_csv", "cg_cohort_summary_stats_csv")
        labels <- c("counts", "inclusion rules", "inclusion result", "inclusion stats", "summary stats")
        sections <- list()
        for (i in seq_along(keys)) {
          item <- context$artifact_registry[[keys[[i]]]] %||% NULL
          if (is.null(item) || !isTRUE(item$exists)) next
          data <- .studyAgentSlashReadCsvSafe(item$absolute_path)
          if (is.null(data)) next
          sections[[length(sections) + 1L]] <- list(kind = "text", text = sprintf("%s: %s", labels[[i]], item$path))
          sections[[length(sections) + 1L]] <- .studyAgentSlashExplorationTableSection(
            data = data,
            title = basename(item$path %||% item$absolute_path %||% labels[[i]]),
            preview_data = .studyAgentSlashCompactPreviewTable(data, max_rows = 6L, max_cols = 6L)
          )
        }
        if (length(sections) == 0) stop("No cohort generation statistics files are available.")
        list(status = "ok", title = "Cohort generation statistics preview", sections = sections)
      }
    )
  )
}

.studyAgentSlashListExplorationCommands <- function(base_dir, workflow_type, step_id = NULL) {
  registry <- .studyAgentSlashBuildArtifactRegistry(base_dir)
  commands <- .studyAgentSlashExplorationCommands()
  Filter(function(cmd) {
    workflow_ok <- as.character(workflow_type %||% "") %in% as.character(cmd$workflow_types %||% character(0))
    step_ids <- as.character(cmd$step_ids %||% character(0))
    step_ok <- length(step_ids) == 0 || (!is.null(step_id) && nzchar(trimws(as.character(step_id))) && as.character(step_id) %in% step_ids)
    requirements <- as.character(cmd$artifact_requirements %||% character(0))
    requirements_ok <- all(vapply(requirements, function(req) {
      item <- Filter(function(artifact) identical(as.character(artifact$artifact_class %||% ""), req), registry)
      length(item) > 0 && any(vapply(item, function(artifact) isTRUE(artifact$exists), logical(1)))
    }, logical(1)))
    isTRUE(workflow_ok && step_ok && requirements_ok)
  }, commands)
}

.studyAgentSlashFindExplorationCommand <- function(command_id) {
  command_id <- as.character(command_id %||% "")
  for (cmd in .studyAgentSlashExplorationCommands()) {
    if (identical(as.character(cmd$command_id %||% ""), command_id)) return(cmd)
  }
  NULL
}

.studyAgentSlashExplorationCommandTable <- function(commands) {
  rows <- lapply(commands, function(cmd) {
    data.frame(
      command_id = as.character(cmd$command_id %||% ""),
      label = as.character(cmd$label %||% ""),
      purpose = as.character(cmd$purpose %||% ""),
      stringsAsFactors = FALSE
    )
  })
  if (length(rows) == 0) {
    return(data.frame(command_id = character(0), label = character(0), purpose = character(0), stringsAsFactors = FALSE))
  }
  do.call(rbind, rows)
}

.studyAgentSlashRenderExplorationResult <- function(result, viewer = FALSE) {
  if (!identical(as.character(result$status %||% ""), "ok")) {
    cat(sprintf("Exploration failed: %s\n", as.character(result$error %||% "unknown error")))
    return(invisible(NULL))
  }
  cat(sprintf("\n%s\n", as.character(result$title %||% "Exploration result")))
  for (section in result$sections %||% list()) {
    kind <- as.character(section$kind %||% "text")
    if (identical(kind, "text")) {
      cat(sprintf("%s\n", as.character(section$text %||% "")))
      next
    }
    if (identical(kind, "table")) {
      print(section$data)
      if (isTRUE(viewer) && isTRUE(.studyAgentSlashSupportsDataViewer())) {
        .studyAgentSlashOpenTableViewer(
          data = section$view_data %||% section$data,
          title = section$view_title %||% result$title %||% "Study Agent"
        )
      }
      next
    }
  }
  cat("\n")
  invisible(NULL)
}

.studyAgentSlashRunExplorationCommand <- function(base_dir, command_id) {
  project_state <- .studyAgentSlashReadProjectState(base_dir)
  runtime_state <- .studyAgentSlashReadRuntimeState(base_dir)
  step_id <- as.character(project_state$resume$current_step_id %||% "")
  step <- if (nzchar(step_id)) .studyAgentSlashFindPlanStep(project_state, step_id) else NULL
  command <- .studyAgentSlashFindExplorationCommand(command_id)
  if (is.null(command)) stop(sprintf("Unknown exploration command: %s", command_id))
  available <- .studyAgentSlashListExplorationCommands(base_dir, workflow_type = project_state$workflow_type %||% "", step_id = step_id)
  available_ids <- vapply(available, function(item) as.character(item$command_id %||% ""), character(1))
  if (!(as.character(command_id) %in% available_ids)) stop(sprintf("Exploration command is not available in the current workflow state: %s", command_id))
  context <- .studyAgentSlashBuildExplorationContext(base_dir, project_state, runtime_state, step = step)
  tryCatch(
    command$executor(context),
    error = function(e) list(status = "error", error = conditionMessage(e))
  )
}
