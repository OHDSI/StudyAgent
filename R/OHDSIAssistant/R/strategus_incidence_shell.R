#' Interactive shell to generate Strategus CohortIncidence scripts
#' @param outputDir directory where scripts and artifacts will be written
#' @param acpUrl ACP base URL
#' @param studyIntent study intent text
#' @param topK number of candidates retrieved from MCP search
#' @param maxResults max phenotypes to show
#' @param candidateLimit max candidates to pass to LLM
#' @param indexDir phenotype index directory (contains definitions/)
#' @param interactive whether to prompt for inputs
#' @param allowCache reuse cached artifacts when present
#' @param promptOnCache prompt before using cached artifacts
#' @return invisible list with output paths
#' @export
runStrategusIncidenceShell <- function(outputDir = "demo-strategus-cohort-incidence",
                                      acpUrl = "http://127.0.0.1:8765",
                                      studyIntent = NULL,
                                      topK = 20,
                                      maxResults = 10,
                                      candidateLimit = 10,
                                      indexDir = Sys.getenv("PHENOTYPE_INDEX_DIR", "data/phenotype_index"),
                                      interactive = TRUE,
                                      allowCache = TRUE,
                                      promptOnCache = TRUE) {
  `%||%` <- function(x, y) if (is.null(x)) y else x

  ensure_dir <- function(path) {
    if (!dir.exists(path)) dir.create(path, recursive = TRUE)
  }

  prompt_yesno <- function(prompt, default = TRUE) {
    if (!interactive()) return(default)
    suffix <- if (default) "[Y/n]" else "[y/N]"
    resp <- tolower(trimws(readline(sprintf("%s %s ", prompt, suffix))))
    if (resp == "") return(default)
    if (resp %in% c("y", "yes")) return(TRUE)
    if (resp %in% c("n", "no")) return(FALSE)
    default
  }

  maybe_use_cache <- function(path, label) {
    if (!allowCache || !file.exists(path)) return(FALSE)
    if (!promptOnCache) return(TRUE)
    prompt_yesno(sprintf("Use cached %s at %s?", label, path), default = TRUE)
  }

  read_json <- function(path) {
    jsonlite::fromJSON(path, simplifyVector = FALSE)
  }

  write_json <- function(x, path) {
    jsonlite::write_json(x, path, pretty = TRUE, auto_unbox = TRUE)
  }

  copy_cohort_json <- function(source_id, dest_id, dest_dir, index_def_dir) {
    src <- file.path(index_def_dir, sprintf("%s.json", source_id))
    if (!file.exists(src)) stop(sprintf("Cohort JSON not found: %s", src))
    ensure_dir(dest_dir)
    dest <- file.path(dest_dir, sprintf("%s.json", dest_id))
    file.copy(src, dest, overwrite = TRUE)
    dest
  }

  outputDir <- normalizePath(outputDir, winslash = "/", mustWork = FALSE)
  base_dir <- outputDir
  index_dir <- normalizePath(indexDir, winslash = "/", mustWork = FALSE)
  if (!dir.exists(index_dir) && !grepl("^/", indexDir)) {
    alt <- file.path(getwd(), "OHDSI-Study-Agent", indexDir)
    if (dir.exists(alt)) {
      index_dir <- normalizePath(alt, winslash = "/", mustWork = FALSE)
    }
  }
  index_def_dir <- file.path(index_dir, "definitions")
  if (!dir.exists(index_def_dir)) stop(sprintf("Missing phenotype index definitions folder: %s", index_def_dir))

  output_dir <- file.path(base_dir, "outputs")
  selected_dir <- file.path(base_dir, "selected-cohorts")
  patched_dir <- file.path(base_dir, "patched-cohorts")
  keeper_dir <- file.path(base_dir, "keeper-case-review")
  analysis_settings_dir <- file.path(base_dir, "analysis-settings")
  scripts_dir <- file.path(base_dir, "scripts")

  ensure_dir(output_dir)
  ensure_dir(selected_dir)
  ensure_dir(patched_dir)
  ensure_dir(keeper_dir)
  ensure_dir(analysis_settings_dir)
  ensure_dir(scripts_dir)

  if (is.null(studyIntent) || !nzchar(trimws(studyIntent))) {
    if (interactive) {
      studyIntent <- utils::edit("Enter study intent text below and save/close to continue.")
    }
  }
  if (is.null(studyIntent) || !nzchar(trimws(studyIntent))) {
    stop("studyIntent is required.")
  }

  acp_connect(acpUrl)

  recs_path <- file.path(output_dir, "recommendations.json")
  rec_response <- NULL
  if (maybe_use_cache(recs_path, "recommendations")) {
    rec_response <- read_json(recs_path)
  } else {
    message("Calling ACP flow: phenotype_recommendation")
    body <- list(
      study_intent = studyIntent,
      top_k = topK,
      max_results = maxResults,
      candidate_limit = candidateLimit
    )
    rec_response <- .acp_post("/flows/phenotype_recommendation", body)
    write_json(rec_response, recs_path)
  }

  recs_core <- rec_response$recommendations %||% rec_response
  recommendations <- recs_core$phenotype_recommendations %||% list()
  if (length(recommendations) == 0) stop("No phenotype recommendations returned.")

  cat("\n== Phenotype Recommendations ==\n")
  for (i in seq_along(recommendations)) {
    rec <- recommendations[[i]]
    cat(sprintf("%d. %s (ID %s)\n", i, rec$cohortName %||% "<unknown>", rec$cohortId %||% "?"))
    if (!is.null(rec$justification)) cat(sprintf("   %s\n", rec$justification))
  }

  selected_ids <- NULL
  if (interactive) {
    labels <- vapply(seq_along(recommendations), function(i) {
      rec <- recommendations[[i]]
      sprintf("%s (ID %s)", rec$cohortName %||% "<unknown>", rec$cohortId %||% "?")
    }, character(1))
    picks <- utils::select.list(labels, multiple = TRUE, title = "Select phenotypes to use")
    selected_ids <- vapply(picks, function(label) {
      idx <- which(labels == label)[1]
      recommendations[[idx]]$cohortId
    }, numeric(1))
  } else {
    selected_ids <- vapply(recommendations, function(r) r$cohortId, numeric(1))
  }
  selected_ids <- as.integer(selected_ids)
  if (length(selected_ids) == 0) stop("No cohorts selected.")

  use_mapping <- FALSE
  if (interactive) {
    use_mapping <- prompt_yesno("Map cohort IDs to a new range (avoid collisions)?", default = TRUE)
  }
  new_ids <- selected_ids
  cohort_id_base <- NA_integer_
  if (use_mapping) {
    cohort_id_base <- sample(10000:50000, 1)
    if (interactive) {
      msg <- sprintf("Enter cohort ID base (10000-50000) or press Enter to use %s: ", cohort_id_base)
      inp <- trimws(readline(msg))
      if (nzchar(inp)) cohort_id_base <- as.integer(inp)
    }
    new_ids <- cohort_id_base + seq_along(selected_ids) - 1
  }

  id_map <- data.frame(
    original_id = selected_ids,
    cohort_id = new_ids,
    stringsAsFactors = FALSE
  )
  write_json(list(mapping = id_map), file.path(output_dir, "cohort_id_map.json"))

  selected_paths <- vapply(seq_along(selected_ids), function(i) {
    copy_cohort_json(selected_ids[[i]], new_ids[[i]], selected_dir, index_def_dir)
  }, character(1))

  cohort_csv <- file.path(selected_dir, "Cohorts.csv")
  cohort_rows <- lapply(seq_along(new_ids), function(i) {
    cid <- selected_ids[[i]]
    new_id <- new_ids[[i]]
    rec <- recommendations[[which(vapply(recommendations, function(r) r$cohortId == cid, logical(1)))]]
    data.frame(
      atlas_id = cid,
      cohort_id = new_id,
      cohort_name = rec$cohortName %||% paste0("Cohort ", new_id),
      logic_description = rec$justification %||% NA_character_,
      generate_stats = TRUE,
      stringsAsFactors = FALSE
    )
  })
  cohort_df <- do.call(rbind, cohort_rows)
  write.csv(cohort_df, cohort_csv, row.names = FALSE)

  improvements_path <- file.path(output_dir, "improvements.json")
  imp_response <- list()
  if (maybe_use_cache(improvements_path, "improvements")) {
    imp_response <- read_json(improvements_path)
  } else {
    for (i in seq_along(selected_paths)) {
      cohort_obj <- read_json(selected_paths[[i]])
      cohort_obj$id <- new_ids[[i]]
      body <- list(
        protocol_text = studyIntent,
        cohorts = list(cohort_obj)
      )
      message(sprintf("Calling ACP flow: phenotype_improvements (cohort %s)", new_ids[[i]]))
      resp <- .acp_post("/flows/phenotype_improvements", body)
      imp_response[[as.character(new_ids[[i]])]] <- resp
    }
    write_json(imp_response, improvements_path)
  }

  state <- list(
    study_intent = studyIntent,
    output_dir = output_dir,
    selected_dir = selected_dir,
    patched_dir = patched_dir,
    keeper_dir = keeper_dir,
    analysis_settings_dir = analysis_settings_dir,
    index_def_dir = index_def_dir,
    recommendations_path = recs_path,
    improvements_path = improvements_path,
    cohort_csv = cohort_csv,
    cohort_id_map = id_map,
    cohort_id_base = cohort_id_base
  )
  state_path <- file.path(output_dir, "study_agent_state.json")
  write_json(state, state_path)

  # ---- Generate scripts ----
  write_lines <- function(path, lines) {
    writeLines(lines, con = path, useBytes = TRUE)
  }

  script_header <- c(
    "# Generated by OHDSIAssistant::runStrategusIncidenceShell",
    "# Edit values as needed and run in order.",
    ""
  )

  # 01 - select
  script_01 <- c(
    script_header,
    "`%||%` <- function(x, y) if (is.null(x)) y else x",
    sprintf("output_dir <- '%s'", output_dir),
    sprintf("index_def_dir <- '%s'", index_def_dir),
    "selected_dir <- file.path(dirname(output_dir), 'selected-cohorts')",
    "recommendations_path <- file.path(output_dir, 'recommendations.json')",
    "id_map_path <- file.path(output_dir, 'cohort_id_map.json')",
    "dir.create(selected_dir, recursive = TRUE, showWarnings = FALSE)",
    "recs <- jsonlite::fromJSON(recommendations_path, simplifyVector = FALSE)",
    "recs_core <- recs$recommendations %||% recs",
    "items <- recs_core$phenotype_recommendations %||% list()",
    "labels <- vapply(seq_along(items), function(i) sprintf('%s (ID %s)', items[[i]]$cohortName %||% '<unknown>', items[[i]]$cohortId %||% '?'), character(1))",
    "picks <- utils::select.list(labels, multiple = TRUE, title = 'Select phenotypes to use')",
    "ids <- vapply(picks, function(label) { idx <- which(labels == label)[1]; items[[idx]]$cohortId }, numeric(1))",
    "id_map <- jsonlite::fromJSON(id_map_path)$mapping",
    "for (i in seq_along(ids)) {",
    "  src <- file.path(index_def_dir, sprintf('%s.json', ids[[i]]))",
    "  dest_id <- id_map$cohort_id[id_map$original_id == ids[[i]]][1]",
    "  dest <- file.path(selected_dir, sprintf('%s.json', dest_id))",
    "  file.copy(src, dest, overwrite = TRUE)",
    "}",
    ""
  )
  write_lines(file.path(scripts_dir, "01_recommend_and_select.R"), script_01)

  # 02 - apply improvements
  script_02 <- c(
    script_header,
    "`%||%` <- function(x, y) if (is.null(x)) y else x",
    "apply_action <- function(obj, action) {",
    "  path <- action$path %||% ''",
    "  value <- action$value",
    "  if (!nzchar(path)) return(obj)",
    "  segs <- strsplit(path, '/', fixed = TRUE)[[1]]",
    "  segs <- segs[segs != '']",
    "  set_in <- function(x, segs, value) {",
    "    if (length(segs) == 0) return(value)",
    "    seg <- segs[[1]]",
    "    name <- seg",
    "    idx <- NA_integer_",
    "    if (grepl('\\\\[\\\\d+\\\\]$', seg)) {",
    "      name <- sub('\\\\[\\\\d+\\\\]$', '', seg)",
    "      idx <- as.integer(sub('^.*\\\\[(\\\\d+)\\\\]$', '\\\\1', seg))",
    "    }",
    "    if (name != '') {",
    "      if (is.null(x[[name]])) x[[name]] <- list()",
    "      if (length(segs) == 1) {",
    "        if (!is.na(idx)) {",
    "          if (length(x[[name]]) < idx) while (length(x[[name]]) < idx) x[[name]][[length(x[[name]]) + 1]] <- NULL",
    "          x[[name]][[idx]] <- value",
    "        } else {",
    "          x[[name]] <- value",
    "        }",
    "        return(x)",
    "      }",
    "      if (!is.na(idx)) {",
    "        if (length(x[[name]]) < idx) while (length(x[[name]]) < idx) x[[name]][[length(x[[name]]) + 1]] <- list()",
    "        x[[name]][[idx]] <- set_in(x[[name]][[idx]], segs[-1], value)",
    "      } else {",
    "        x[[name]] <- set_in(x[[name]], segs[-1], value)",
    "      }",
    "      return(x)",
    "    }",
    "    idx <- suppressWarnings(as.integer(seg))",
    "    if (is.na(idx)) return(x)",
    "    if (idx == 0) idx <- 1",
    "    if (length(x) < idx) while (length(x) < idx) x[[length(x) + 1]] <- list()",
    "    if (length(segs) == 1) { x[[idx]] <- value; return(x) }",
    "    x[[idx]] <- set_in(x[[idx]], segs[-1], value)",
    "    x",
    "  }",
    "  set_in(obj, segs, value)",
    "}",
    sprintf("output_dir <- '%s'", output_dir),
    "selected_dir <- file.path(dirname(output_dir), 'selected-cohorts')",
    "patched_dir <- file.path(dirname(output_dir), 'patched-cohorts')",
    "dir.create(patched_dir, recursive = TRUE, showWarnings = FALSE)",
    "improvements_path <- file.path(output_dir, 'improvements.json')",
    "improvements <- jsonlite::fromJSON(improvements_path, simplifyVector = FALSE)",
    "for (cid in names(improvements)) {",
    "  resp <- improvements[[cid]]",
    "  core <- resp$full_result %||% resp",
    "  items <- core$phenotype_improvements %||% list()",
    "  if (length(items) == 0) next",
    "  cohort_path <- file.path(selected_dir, sprintf('%s.json', cid))",
    "  cohort_obj <- jsonlite::fromJSON(cohort_path, simplifyVector = FALSE)",
    "  for (item in items) {",
    "    if (is.null(item$actions)) next",
    "    for (act in item$actions) cohort_obj <- apply_action(cohort_obj, act)",
    "  }",
    "  out_path <- file.path(patched_dir, sprintf('%s.json', cid))",
    "  jsonlite::write_json(cohort_obj, out_path, pretty = TRUE, auto_unbox = TRUE)",
    "}",
    ""
  )
  write_lines(file.path(scripts_dir, "02_apply_improvements.R"), script_02)

  # 03 - generate cohorts
  script_03 <- c(
    script_header,
    "library(Strategus)",
    "library(CohortGenerator)",
    "library(ParallelLogger)",
    sprintf("output_dir <- '%s'", output_dir),
    "selected_dir <- file.path(dirname(output_dir), 'selected-cohorts')",
    "patched_dir <- file.path(dirname(output_dir), 'patched-cohorts')",
    "cohort_csv <- file.path(selected_dir, 'Cohorts.csv')",
    "cohort_json_dir <- if (length(list.files(patched_dir, pattern = '\\\\.(json)$')) > 0) patched_dir else selected_dir",
    "sql_dir <- file.path(selected_dir, 'sql')",
    "dir.create(sql_dir, recursive = TRUE, showWarnings = FALSE)",
    "# TODO: fill in connectionDetails and executionSettings_cohorts",
    "# connectionDetails <- DatabaseConnector::createConnectionDetails(...)",
    "# executionSettings_cohorts <- createCdmExecutionSettings(...)",
    "cohortDefinitionSet <- CohortGenerator::getCohortDefinitionSet(",
    "  settingsFileName = cohort_csv,",
    "  jsonFolder = cohort_json_dir,",
    "  sqlFolder = sql_dir",
    ")",
    "cgModule <- CohortGeneratorModule$new()",
    "cohortDefinitionSharedResource <- cgModule$createCohortSharedResourceSpecifications(",
    "  cohortDefinitionSet = cohortDefinitionSet",
    ")",
    "cohortGeneratorModuleSpecifications <- cgModule$createModuleSpecifications(generateStats = TRUE)",
    "analysisSpecifications <- createEmptyAnalysisSpecificiations() %>%",
    "  addSharedResources(cohortDefinitionSharedResource) %>%",
    "  addModuleSpecifications(cohortGeneratorModuleSpecifications)",
    "# execute(connectionDetails, analysisSpecifications, executionSettings_cohorts)",
    ""
  )
  write_lines(file.path(scripts_dir, "03_generate_cohorts.R"), script_03)

  # 04 - Keeper review
  script_04 <- c(
    script_header,
    "library(Keeper)",
    "library(jsonlite)",
    sprintf("output_dir <- '%s'", output_dir),
    "keeper_dir <- file.path(dirname(output_dir), 'keeper-case-review')",
    "dir.create(keeper_dir, recursive = TRUE, showWarnings = FALSE)",
    "id_map <- jsonlite::fromJSON(file.path(output_dir, 'cohort_id_map.json'))$mapping",
    "# TODO: fill in connectionDetails and schema/table info",
    "# connectionDetails <- DatabaseConnector::createConnectionDetails(...)",
    "databaseId <- 'Synpuf'",
    "cdmDatabaseSchema <- 'main'",
    "cohortDatabaseSchema <- 'main'",
    "cohortTable <- 'cohort'",
    "for (cid in id_map$cohort_id) {",
    "  keeper <- createKeeper(",
    "    connectionDetails = connectionDetails,",
    "    databaseId = databaseId,",
    "    cdmDatabaseSchema = cdmDatabaseSchema,",
    "    cohortDatabaseSchema = cohortDatabaseSchema,",
    "    cohortTable = cohortTable,",
    "    cohortDefinitionId = cid,",
    "    cohortName = paste('Cohort', cid),",
    "    sampleSize = 100,",
    "    assignNewId = TRUE,",
    "    useAncestor = TRUE,",
    "    doi = c(4202064, 192671, 2108878, 2108900, 2002608),",
    "    symptoms = c(4103703, 443530, 4245614, 28779),",
    "    comorbidities = c(81893, 201606, 313217, 318800, 432585, 4027663, 4180790, 4212540,
                         40481531, 42535737, 46271022),",
    "    drugs = c(904453, 906780, 923645, 929887, 948078, 953076, 961047, 985247, 992956,
               997276, 1102917, 1113648, 1115008, 1118045, 1118084, 1124300, 1126128,
               1136980, 1146810, 1150345, 1153928, 1177480, 1178663, 1185922, 1195492,
               1236607, 1303425, 1313200, 1353766, 1507835, 1522957, 1721543, 1746940,
               1777806, 19044727, 19119253, 36863425),",
    "    diagnosticProcedures = c(4087381, 4143985, 4294382, 42872565, 45888171, 46257627),",
    "    measurements = c(3000905, 3000963, 3003458, 3012471, 3016251, 3018677, 3020416,
                      3022217, 3023314, 3024929, 3034426),",
    "    alternativeDiagnosis = c(24966, 76725, 195562, 316457, 318800, 4096682),",
    "    treatmentProcedures = c(0),",
    "    complications = c(132797, 196152, 439777, 4192647)",
    "  )",
    "  out_path <- file.path(keeper_dir, sprintf('%s.csv', cid))",
    "  write.csv(keeper, out_path, row.names = FALSE)",
    "}",
    "# Optional: if ACP is available, use phenotype_validation_review on rows from keeper_dir.",
    ""
  )
  write_lines(file.path(scripts_dir, "04_keeper_review.R"), script_04)

  # 05 - diagnostics
  script_05 <- c(
    script_header,
    "library(Strategus)",
    "library(CohortDiagnostics)",
    "library(CohortGenerator)",
    "library(ParallelLogger)",
    sprintf("output_dir <- '%s'", output_dir),
    "selected_dir <- file.path(dirname(output_dir), 'selected-cohorts')",
    "patched_dir <- file.path(dirname(output_dir), 'patched-cohorts')",
    "cohort_csv <- file.path(selected_dir, 'Cohorts.csv')",
    "cohort_json_dir <- if (length(list.files(patched_dir, pattern = '\\\\.(json)$')) > 0) patched_dir else selected_dir",
    "sql_dir <- file.path(selected_dir, 'sql')",
    "dir.create(sql_dir, recursive = TRUE, showWarnings = FALSE)",
    "# TODO: fill in connectionDetails and executionSettings_diagnostics",
    "# connectionDetails <- DatabaseConnector::createConnectionDetails(...)",
    "# executionSettings_diagnostics <- createCdmExecutionSettings(...)",
    "cohortDefinitionSet <- CohortGenerator::getCohortDefinitionSet(",
    "  settingsFileName = cohort_csv,",
    "  jsonFolder = cohort_json_dir,",
    "  sqlFolder = sql_dir",
    ")",
    "cgModule <- CohortGeneratorModule$new()",
    "cohortDefinitionSharedResource <- cgModule$createCohortSharedResourceSpecifications(",
    "  cohortDefinitionSet = cohortDefinitionSet",
    ")",
    "cdModule <- CohortDiagnosticsModule$new()",
    "cohortDiagnosticsModuleSpecifications <- cdModule$createModuleSpecifications(",
    "  runInclusionStatistics = TRUE,",
    "  runIncludedSourceConcepts = TRUE,",
    "  runOrphanConcepts = TRUE,",
    "  runTimeSeries = FALSE,",
    "  runVisitContext = TRUE,",
    "  runBreakdownIndexEvents = TRUE,",
    "  runIncidenceRate = TRUE,",
    "  runCohortRelationship = TRUE,",
    "  runTemporalCohortCharacterization = TRUE",
    ")",
    "analysisSpecifications <- createEmptyAnalysisSpecificiations() %>%",
    "  addSharedResources(cohortDefinitionSharedResource) %>%",
    "  addModuleSpecifications(cohortDiagnosticsModuleSpecifications)",
    "# execute(connectionDetails, analysisSpecifications, executionSettings_diagnostics)",
    ""
  )
  write_lines(file.path(scripts_dir, "05_diagnostics.R"), script_05)

  # 06 - incidence spec
  script_06 <- c(
    script_header,
    "library(Strategus)",
    "library(CohortGenerator)",
    "library(CohortIncidence)",
    "library(ParallelLogger)",
    sprintf("output_dir <- '%s'", output_dir),
    "analysis_settings_dir <- file.path(dirname(output_dir), 'analysis-settings')",
    "dir.create(analysis_settings_dir, recursive = TRUE, showWarnings = FALSE)",
    "selected_dir <- file.path(dirname(output_dir), 'selected-cohorts')",
    "patched_dir <- file.path(dirname(output_dir), 'patched-cohorts')",
    "cohort_csv <- file.path(selected_dir, 'Cohorts.csv')",
    "cohort_json_dir <- if (length(list.files(patched_dir, pattern = '\\\\.(json)$')) > 0) patched_dir else selected_dir",
    "sql_dir <- file.path(selected_dir, 'sql')",
    "dir.create(sql_dir, recursive = TRUE, showWarnings = FALSE)",
    "# TODO: fill in connectionDetails and executionSettings_incidence",
    "# connectionDetails <- DatabaseConnector::createConnectionDetails(...)",
    "# executionSettings_incidence <- createCdmExecutionSettings(...)",
    "cohortDefinitionSet <- CohortGenerator::getCohortDefinitionSet(",
    "  settingsFileName = cohort_csv,",
    "  jsonFolder = cohort_json_dir,",
    "  sqlFolder = sql_dir",
    ")",
    "cgModule <- CohortGeneratorModule$new()",
    "cohortDefinitionSharedResource <- cgModule$createCohortSharedResourceSpecifications(",
    "  cohortDefinitionSet = cohortDefinitionSet",
    ")",
    "# TODO: assign target/outcome cohort IDs",
    "targets <- list()",
    "outcomes <- list()",
    "tars <- list(",
    "  CohortIncidence::createTimeAtRiskDef(id = 1, startWith = 'start', endWith = 'end'),",
    "  CohortIncidence::createTimeAtRiskDef(id = 2, startWith = 'start', endWith = 'start', endOffset = 365)",
    ")",
    "analysis1 <- CohortIncidence::createIncidenceAnalysis(",
    "  targets = sapply(targets, function(x) x$id),",
    "  outcomes = sapply(outcomes, function(x) x$id),",
    "  tars = c(1, 2)",
    ")",
    "irDesign <- CohortIncidence::createIncidenceDesign(",
    "  targetDefs = targets,",
    "  outcomeDefs = outcomes,",
    "  tars = tars,",
    "  analysisList = list(analysis1),",
    "  strataSettings = CohortIncidence::createStrataSettings(byYear = TRUE, byGender = TRUE)",
    ")",
    "ciModule <- CohortIncidenceModule$new()",
    "cohortIncidenceModuleSpecifications <- ciModule$createModuleSpecifications(",
    "  irDesign = irDesign$toList()",
    ")",
    "analysisSpecifications <- createEmptyAnalysisSpecificiations() %>%",
    "  addSharedResources(cohortDefinitionSharedResource) %>%",
    "  addModuleSpecifications(cohortIncidenceModuleSpecifications)",
    "analysis_spec_path <- file.path(analysis_settings_dir, 'analysisSpecification.json')",
    "ParallelLogger::saveSettingsToJson(analysisSpecifications, analysis_spec_path)",
    "# execute(connectionDetails, analysisSpecifications, executionSettings_incidence)",
    ""
  )
  write_lines(file.path(scripts_dir, "06_incidence_spec.R"), script_06)

  message("Study agent shell complete. Scripts written to: ", scripts_dir)
  invisible(list(
    output_dir = output_dir,
    scripts_dir = scripts_dir,
    recommendations = recs_path,
    improvements = improvements_path,
    cohort_csv = cohort_csv
  ))
}
