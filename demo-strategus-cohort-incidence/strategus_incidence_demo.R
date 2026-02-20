# Demo: Study Agent phenotype flows + Strategus CohortIncidence
# Run interactively in RStudio or source() line-by-line.

suppressPackageStartupMessages({
  library(jsonlite)
  library(OHDSIAssistant)
  library(Strategus)
  library(CohortGenerator)
  library(CohortDiagnostics)
  library(CohortIncidence)
  library(ParallelLogger)
  library(Keeper)
})

# ---- User settings ----
RUN_RECOMMENDATIONS <- TRUE
RUN_IMPROVEMENTS <- TRUE
RUN_EXECUTE_COHORTS <- FALSE
RUN_KEEPER_REVIEW <- TRUE
RUN_EXECUTE_DIAGNOSTICS <- FALSE
RUN_EXECUTE_INCIDENCE <- FALSE
RUN_STRATEGUS_SPEC <- TRUE

ALLOW_CACHE <- TRUE
PROMPT_ON_CACHE <- TRUE

acp_url <- "http://127.0.0.1:8765"

study_intent <- "What is the risk of GI bleed in new users of Celecoxib compared to new users of Diclofenac?"

# Local folders
base_dir <- normalizePath("demo-strategus-cohort-incidence", winslash = "/", mustWork = FALSE)
index_dir <- normalizePath(Sys.getenv("PHENOTYPE_INDEX_DIR", "data/phenotype_index"), winslash = "/", mustWork = FALSE)
index_def_dir <- file.path(index_dir, "definitions")
output_dir <- file.path(base_dir, "outputs")
selected_dir <- file.path(base_dir, "selected-cohorts")
patched_dir <- file.path(base_dir, "patched-cohorts")
keeper_dir <- file.path(base_dir, "keeper-case-review")
analysis_settings_dir <- file.path(base_dir, "analysis-settings")

# Randomized cohort ID base (avoid collisions in CDM cohort table)
cohort_id_base <- NULL

# ---- Connection details (fill these in to run execute phases) ----
connectionDetails <- NULL
executionSettings_cohorts <- NULL
executionSettings_diagnostics <- NULL
executionSettings_incidence <- NULL
keeper_database_id <- "Synpuf"
cdm_database_schema <- "main"
cohort_database_schema <- "main"
cohort_table <- "cohort"

# ---- Helpers ----
`%||%` <- function(x, y) if (is.null(x)) y else x

ensure_dir <- function(path) {
  if (!dir.exists(path)) dir.create(path, recursive = TRUE)
}

as_scalar <- function(x, default = NA) {
  if (length(x) == 0 || is.null(x)) return(default)
  x[[1]]
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
  if (!ALLOW_CACHE || !file.exists(path)) return(FALSE)
  if (!PROMPT_ON_CACHE) return(TRUE)
  prompt_yesno(sprintf("Use cached %s at %s?", label, path), default = TRUE)
}

read_json <- function(path) {
  jsonlite::fromJSON(path, simplifyVector = FALSE)
}

write_json <- function(x, path) {
  jsonlite::write_json(x, path, pretty = TRUE, auto_unbox = TRUE)
}

# Apply JSON-pointer-like actions (best-effort)
apply_action <- function(obj, action) {
  path <- as_scalar(action$path, "")
  value <- action$value
  if (!nzchar(path)) return(obj)
  segs <- strsplit(path, "/", fixed = TRUE)[[1]]
  segs <- segs[segs != ""]

  set_in <- function(x, segs, value) {
    if (length(segs) == 0) return(value)
    seg <- segs[[1]]
    name <- seg
    idx <- NA_integer_
    if (grepl("\\[\\d+\\]$", seg)) {
      name <- sub("\\[\\d+\\]$", "", seg)
      idx <- as.integer(sub("^.*\\[(\\d+)\\]$", "\\1", seg))
    }
    if (name != "") {
      if (is.null(x[[name]])) x[[name]] <- list()
      if (length(segs) == 1) {
        if (!is.na(idx)) {
          if (length(x[[name]]) < idx) {
            while (length(x[[name]]) < idx) x[[name]][[length(x[[name]]) + 1]] <- NULL
          }
          x[[name]][[idx]] <- value
        } else {
          x[[name]] <- value
        }
        return(x)
      }
      if (!is.na(idx)) {
        if (length(x[[name]]) < idx) {
          while (length(x[[name]]) < idx) x[[name]][[length(x[[name]]) + 1]] <- list()
        }
        x[[name]][[idx]] <- set_in(x[[name]][[idx]], segs[-1], value)
      } else {
        x[[name]] <- set_in(x[[name]], segs[-1], value)
      }
      return(x)
    }
    idx <- suppressWarnings(as.integer(seg))
    if (is.na(idx)) return(x)
    if (idx == 0) idx <- 1
    if (length(x) < idx) {
      while (length(x) < idx) x[[length(x) + 1]] <- list()
    }
    if (length(segs) == 1) {
      x[[idx]] <- value
      return(x)
    }
    x[[idx]] <- set_in(x[[idx]], segs[-1], value)
    x
  }

  set_in(obj, segs, value)
}

copy_cohort_json <- function(source_id, dest_id, dest_dir) {
  src <- file.path(index_def_dir, sprintf("%s.json", source_id))
  if (!file.exists(src)) stop(sprintf("Cohort JSON not found: %s", src))
  ensure_dir(dest_dir)
  dest <- file.path(dest_dir, sprintf("%s.json", dest_id))
  file.copy(src, dest, overwrite = TRUE)
  dest
}

# ---- Setup ----
ensure_dir(output_dir)
ensure_dir(selected_dir)
ensure_dir(patched_dir)
ensure_dir(keeper_dir)
ensure_dir(analysis_settings_dir)

if (!dir.exists(index_def_dir)) {
  stop(sprintf("Missing phenotype index definitions folder: %s", index_def_dir))
}

OHDSIAssistant::acp_connect(acp_url)

# ---- Step 1: Phenotype recommendations ----
recs_path <- file.path(output_dir, "recommendations.json")
rec_response <- NULL

if (RUN_RECOMMENDATIONS) {
  if (maybe_use_cache(recs_path, "recommendations")) {
    rec_response <- read_json(recs_path)
  } else {
    body <- list(
      study_intent = study_intent,
      top_k = 20,
      max_results = 10,
      candidate_limit = 10
    )
    rec_response <- OHDSIAssistant:::`.acp_post`("/flows/phenotype_recommendation", body)
    write_json(rec_response, recs_path)
  }
} else if (file.exists(recs_path)) {
  rec_response <- read_json(recs_path)
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
if (interactive()) {
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

if (is.null(cohort_id_base)) {
  cohort_id_base <- sample(10000:50000, 1)
  if (interactive()) {
    if (!prompt_yesno(sprintf("Use cohort ID base %s?", cohort_id_base), default = TRUE)) {
      cohort_id_base <- as.integer(readline("Enter cohort ID base (10000-50000): "))
    }
  }
}

new_ids <- cohort_id_base + seq_along(selected_ids) - 1
id_map <- data.frame(
  original_id = selected_ids,
  cohort_id = new_ids,
  stringsAsFactors = FALSE
)

# Copy JSONs to selected folder with new IDs
selected_paths <- vapply(seq_along(selected_ids), function(i) {
  copy_cohort_json(selected_ids[[i]], new_ids[[i]], selected_dir)
}, character(1))

# Build a Cohorts.csv for CohortGenerator
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
write_json(list(mapping = id_map), file.path(output_dir, "cohort_id_map.json"))

# ---- Step 2: Phenotype improvements ----
improvements_path <- file.path(output_dir, "improvements.json")
imp_response <- NULL

if (RUN_IMPROVEMENTS) {
  if (maybe_use_cache(improvements_path, "improvements")) {
    imp_response <- read_json(improvements_path)
  } else {
    imp_response <- list()
    for (i in seq_along(selected_paths)) {
      cohort_obj <- read_json(selected_paths[[i]])
      cohort_obj$id <- new_ids[[i]]
      body <- list(
        protocol_text = study_intent,
        cohorts = list(cohort_obj)
      )
      resp <- OHDSIAssistant:::`.acp_post`("/flows/phenotype_improvements", body)
      imp_response[[as.character(new_ids[[i]])]] <- resp
    }
    write_json(imp_response, improvements_path)
  }
}

if (RUN_IMPROVEMENTS) {
  for (cid in names(imp_response)) {
    resp <- imp_response[[cid]]
    core <- resp$full_result %||% resp
    imp <- core$phenotype_improvements %||% list()
    if (length(imp) == 0) next
    cat(sprintf("\n== Improvements for cohort %s ==\n", cid))
    for (item in imp) {
      cat(sprintf("- %s\n", item$summary %||% "(no summary)"))
      if (!is.null(item$actions)) {
        for (act in item$actions) {
          cat(sprintf("  action: %s %s\n", act$type %||% "set", act$path %||% ""))
        }
      }
    }

    if (!prompt_yesno(sprintf("Apply suggested actions for cohort %s?", cid), default = FALSE)) next

    cohort_path <- file.path(selected_dir, sprintf("%s.json", cid))
    cohort_obj <- read_json(cohort_path)
    for (item in imp) {
      if (is.null(item$actions)) next
      for (act in item$actions) {
        cohort_obj <- apply_action(cohort_obj, act)
      }
    }
    patched_path <- file.path(patched_dir, sprintf("%s.json", cid))
    write_json(cohort_obj, patched_path)
    cat(sprintf("Patched cohort saved: %s\n", patched_path))
  }
}

cohort_json_dir <- if (length(list.files(patched_dir, pattern = "\\.json$")) > 0) patched_dir else selected_dir

# ---- Step 3: Execute CohortGenerator (optional) ----
if (RUN_EXECUTE_COHORTS) {
  if (is.null(connectionDetails) || is.null(executionSettings_cohorts)) {
    stop("Set connectionDetails and executionSettings_cohorts before running cohort generation.")
  }
  sql_dir <- file.path(selected_dir, "sql")
  ensure_dir(sql_dir)

  cohortDefinitionSet <- CohortGenerator::getCohortDefinitionSet(
    settingsFileName = cohort_csv,
    jsonFolder = cohort_json_dir,
    sqlFolder = sql_dir
  )

  cgModule <- CohortGeneratorModule$new()
  cohortDefinitionSharedResource <- cgModule$createCohortSharedResourceSpecifications(
    cohortDefinitionSet = cohortDefinitionSet
  )
  cohortGeneratorModuleSpecifications <- cgModule$createModuleSpecifications(generateStats = TRUE)

  analysisSpecifications <- createEmptyAnalysisSpecificiations() %>%
    addSharedResources(cohortDefinitionSharedResource) %>%
    addModuleSpecifications(cohortGeneratorModuleSpecifications)

  execute(connectionDetails, analysisSpecifications, executionSettings_cohorts)
}

# ---- Step 4: Keeper validation review (requires cohorts generated) ----
if (RUN_KEEPER_REVIEW) {
  if (is.null(connectionDetails)) {
    stop("Set connectionDetails before running Keeper review.")
  }
  if (!RUN_EXECUTE_COHORTS) {
    ok <- prompt_yesno("Have you already generated cohorts in the database for these cohort IDs?", default = TRUE)
    if (!ok) stop("Generate cohorts first (RUN_EXECUTE_COHORTS) before Keeper review.")
  }
  keeper_reviews_path <- file.path(output_dir, "keeper_reviews.json")
  keeper_reviews <- NULL

  if (maybe_use_cache(keeper_reviews_path, "Keeper reviews")) {
    keeper_reviews <- read_json(keeper_reviews_path)
  } else {
    keeper_reviews <- list()
    for (i in seq_along(new_ids)) {
      cid <- new_ids[[i]]
      cohort_name <- cohort_df$cohort_name[cohort_df$cohort_id == cid][1]

      keeper <- createKeeper(
        connectionDetails = connectionDetails,
        databaseId = keeper_database_id,
        cdmDatabaseSchema = cdm_database_schema,
        cohortDatabaseSchema = cohort_database_schema,
        cohortTable = cohort_table,
        cohortDefinitionId = cid,
        cohortName = cohort_name,
        sampleSize = 100,
        assignNewId = TRUE,
        useAncestor = TRUE,
        doi = c(4202064, 192671, 2108878, 2108900, 2002608),
        symptoms = c(4103703, 443530, 4245614, 28779),
        comorbidities = c(81893, 201606, 313217, 318800, 432585, 4027663, 4180790, 4212540,
                          40481531, 42535737, 46271022),
        drugs = c(904453, 906780, 923645, 929887, 948078, 953076, 961047, 985247, 992956,
                  997276, 1102917, 1113648, 1115008, 1118045, 1118084, 1124300, 1126128,
                  1136980, 1146810, 1150345, 1153928, 1177480, 1178663, 1185922, 1195492,
                  1236607, 1303425, 1313200, 1353766, 1507835, 1522957, 1721543, 1746940,
                  1777806, 19044727, 19119253, 36863425),
        diagnosticProcedures = c(4087381, 4143985, 4294382, 42872565, 45888171, 46257627),
        measurements = c(3000905, 3000963, 3003458, 3012471, 3016251, 3018677, 3020416,
                         3022217, 3023314, 3024929, 3034426),
        alternativeDiagnosis = c(24966, 76725, 195562, 316457, 318800, 4096682),
        treatmentProcedures = c(0),
        complications = c(132797, 196152, 439777, 4192647)
      )

      keeper_csv <- file.path(keeper_dir, sprintf("%s.csv", cid))
      write.csv(keeper, keeper_csv, row.names = FALSE)

      row <- keeper[1, , drop = FALSE]
      row_json <- as.list(row)
      body <- list(
        keeper_row = row_json,
        disease_name = cohort_name
      )
      resp <- OHDSIAssistant:::`.acp_post`("/flows/phenotype_validation_review", body)
      keeper_reviews[[as.character(cid)]] <- resp
      cat(sprintf("Keeper review for cohort %s: %s\n", cid, resp$full_result$label %||% "(no label)"))
    }
    write_json(keeper_reviews, keeper_reviews_path)
  }
}

# ---- Step 5: Execute CohortDiagnostics (optional) ----
if (RUN_EXECUTE_DIAGNOSTICS) {
  if (is.null(connectionDetails) || is.null(executionSettings_diagnostics)) {
    stop("Set connectionDetails and executionSettings_diagnostics before running cohort diagnostics.")
  }
  sql_dir <- file.path(selected_dir, "sql")
  ensure_dir(sql_dir)

  cohortDefinitionSet <- CohortGenerator::getCohortDefinitionSet(
    settingsFileName = cohort_csv,
    jsonFolder = cohort_json_dir,
    sqlFolder = sql_dir
  )

  cgModule <- CohortGeneratorModule$new()
  cohortDefinitionSharedResource <- cgModule$createCohortSharedResourceSpecifications(
    cohortDefinitionSet = cohortDefinitionSet
  )

  cdModule <- CohortDiagnosticsModule$new()
  cohortDiagnosticsModuleSpecifications <- cdModule$createModuleSpecifications(
    runInclusionStatistics = TRUE,
    runIncludedSourceConcepts = TRUE,
    runOrphanConcepts = TRUE,
    runTimeSeries = FALSE,
    runVisitContext = TRUE,
    runBreakdownIndexEvents = TRUE,
    runIncidenceRate = TRUE,
    runCohortRelationship = TRUE,
    runTemporalCohortCharacterization = TRUE
  )

  analysisSpecifications <- createEmptyAnalysisSpecificiations() %>%
    addSharedResources(cohortDefinitionSharedResource) %>%
    addModuleSpecifications(cohortDiagnosticsModuleSpecifications)

  execute(connectionDetails, analysisSpecifications, executionSettings_diagnostics)
}

# ---- Step 6: CohortIncidence specifications + optional execute ----
if (RUN_STRATEGUS_SPEC || RUN_EXECUTE_INCIDENCE) {
  sql_dir <- file.path(selected_dir, "sql")
  ensure_dir(sql_dir)
  cohortDefinitionSet <- CohortGenerator::getCohortDefinitionSet(
    settingsFileName = cohort_csv,
    jsonFolder = cohort_json_dir,
    sqlFolder = sql_dir
  )

  cgModule <- CohortGeneratorModule$new()
  cohortDefinitionSharedResource <- cgModule$createCohortSharedResourceSpecifications(
    cohortDefinitionSet = cohortDefinitionSet
  )

  # Manual target/outcome assignment (interactive)
  cohort_ids <- cohort_df$cohort_id
  target_ids <- cohort_ids
  outcome_ids <- cohort_ids
  if (interactive()) {
    labels <- sprintf("%s (ID %s)", cohort_df$cohort_name, cohort_df$cohort_id)
    target_sel <- utils::select.list(labels, multiple = TRUE, title = "Select target cohorts")
    outcome_sel <- utils::select.list(labels, multiple = TRUE, title = "Select outcome cohorts")
    target_ids <- cohort_df$cohort_id[labels %in% target_sel]
    outcome_ids <- cohort_df$cohort_id[labels %in% outcome_sel]
  }

  targets <- lapply(target_ids, function(cid) {
    CohortIncidence::createCohortRef(id = cid, name = cohort_df$cohort_name[cohort_df$cohort_id == cid][1])
  })
  outcomes <- lapply(seq_along(outcome_ids), function(i) {
    cid <- outcome_ids[[i]]
    CohortIncidence::createOutcomeDef(id = i, name = cohort_df$cohort_name[cohort_df$cohort_id == cid][1], cohortId = cid, cleanWindow = 9999)
  })

  tars <- list(
    CohortIncidence::createTimeAtRiskDef(id = 1, startWith = "start", endWith = "end"),
    CohortIncidence::createTimeAtRiskDef(id = 2, startWith = "start", endWith = "start", endOffset = 365)
  )

  analysis1 <- CohortIncidence::createIncidenceAnalysis(
    targets = target_ids,
    outcomes = seq_along(outcomes),
    tars = c(1, 2)
  )

  irDesign <- CohortIncidence::createIncidenceDesign(
    targetDefs = targets,
    outcomeDefs = outcomes,
    tars = tars,
    analysisList = list(analysis1),
    strataSettings = CohortIncidence::createStrataSettings(byYear = TRUE, byGender = TRUE)
  )

  ciModule <- CohortIncidenceModule$new()
  cohortIncidenceModuleSpecifications <- ciModule$createModuleSpecifications(
    irDesign = irDesign$toList()
  )

  analysisSpecifications <- createEmptyAnalysisSpecificiations() %>%
    addSharedResources(cohortDefinitionSharedResource) %>%
    addModuleSpecifications(cohortIncidenceModuleSpecifications)

  if (RUN_STRATEGUS_SPEC) {
    analysis_spec_path <- file.path(analysis_settings_dir, "analysisSpecification.json")
    ParallelLogger::saveSettingsToJson(analysisSpecifications, analysis_spec_path)
    cat(sprintf("\nSaved analysis specification: %s\n", analysis_spec_path))
  }

  if (RUN_EXECUTE_INCIDENCE) {
    if (is.null(connectionDetails) || is.null(executionSettings_incidence)) {
      stop("Set connectionDetails and executionSettings_incidence before running CohortIncidence.")
    }
    execute(connectionDetails, analysisSpecifications, executionSettings_incidence)
  }
}

cat("\nDemo complete.\n")
