from pathlib import Path
import shutil
import subprocess

import pytest

from _repo_paths import repo_path


SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "strategus_cohort_methods_shell.R")
EXECUTION_SETTINGS_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "execution_settings.R")

def _generated_script_block(source: str, script_name: str, filename: str) -> str:
    start = source.index(f"{script_name} <- c(")
    end = source.index(f'write_lines(file.path(scripts_dir, "{filename}")', start)
    return source[start:end]


def _run_r_or_skip(expression: str) -> subprocess.CompletedProcess[str]:
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    result = subprocess.run(
        ["Rscript", "-e", expression],
        check=False,
        text=True,
        capture_output=True,
    )
    if result.returncode == 42:
        pytest.skip(result.stderr.strip() or result.stdout.strip() or "required R package is not available")
    return result


def test_generated_cm_spec_builds_and_executes_strategus_analysis_specification() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    block = _generated_script_block(source, "script_07", "07_cm_spec.R")

    assert "analysisSpecification.json" in block
    assert "CharacterizationModule$new()" in block
    assert "CohortIncidenceModule$new()" in block
    assert "CohortMethodModule$new()" in block
    assert "CohortGeneratorModule$new()" in block
    assert "CohortDiagnosticsModule$new()" not in block
    assert "cohortGeneratorModuleSpecifications" not in block
    assert "cohortDiagnosticsModuleSpecifications" not in block
    assert "target_id <- as.numeric(" in block
    assert "outcome_ids <- vapply(" in block
    assert "numeric(1)" in block
    assert "outcomeIds = as.numeric(outcome_ids)" in block
    assert "outcomeWashoutDays = as.numeric(" in block
    assert "maxCohortSize = studyPopulationDefaults$maxCohortSize" in block
    assert "call_with_supported_args <- function(" in block
    assert "characterizationFormals <- names(formals(characterizationModule$createModuleSpecifications))" in block
    assert "createStudyPopulationArgs <- CohortMethod::createCreateStudyPopulationArgs(" in block
    assert "removeSubjectsWithPriorOutcome = studyPopulationDefaults$removeSubjectsWithPriorOutcome" in block
    assert "useRegularization =" not in block
    assert "prior = outcomeModelPrior" in block
    assert "cmAnalysisFormals <- names(formals(CohortMethod::createCmAnalysis))" in block
    assert "if ('createStudyPopulationArgs' %in% cmAnalysisFormals)" in block
    assert "else if ('createStudyPopArgs' %in% cmAnalysisFormals)" in block
    assert "if ('cmAnalysesSpecifications' %in% cmModuleFormals)" in block
    assert "else if (all(c('cmAnalysisList', 'targetComparatorOutcomesList') %in% cmModuleFormals))" in block
    assert "cmAnalysesSpecifications = cmAnalysesSpecifications$toList()" not in block
    assert "ParallelLogger::saveSettingsToJson(analysisSpecifications, analysis_spec_path)" in block
    assert "result <- Strategus::execute(" in block
    assert "connectionDetails <- slashOhdsiStrategusAssistant::createStrategusConnectionDetails(path = db_details_path)" in block
    assert "exec <- slashOhdsiStrategusAssistant::createStrategusExecutionSettings(path = execution_settings_path)" in block
    assert "CohortMethod::runCmAnalyses(" not in block
    assert "CohortMethod::loadCmAnalysisList(" not in block
    assert "CohortMethod::loadTargetComparatorOutcomesList(" not in block


def test_cm_runner_is_merged_into_script_07() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert 'write_lines(file.path(scripts_dir, "08_cm_run_analyses.R")' not in source
    assert 'cat("  - 07_cm_run_analyses.R\\n")' not in source
    assert 'script_08 <- c(' in source
    assert 'write_lines(file.path(scripts_dir, "08_launch_diagnostics_explorer.R")' in source


def test_characterization_spec_accepts_generated_numeric_types() -> None:
    result = _run_r_or_skip(
        """
        if (!requireNamespace('Strategus', quietly = TRUE)) quit(status = 42)
        library(Strategus)
        `%||%` <- function(x, y) if (is.null(x)) y else x
        call_with_supported_args <- function(fn, args) {
          formal_names <- names(formals(fn)) %||% character(0)
          if (!('...' %in% formal_names)) {
            args <- args[names(args) %in% formal_names]
          }
          do.call(fn, args)
        }
        module <- CharacterizationModule$new()
        spec <- call_with_supported_args(module$createModuleSpecifications, list(
          targetIds = as.numeric(c(1, 2)),
          outcomeIds = as.numeric(c(3)),
          limitToFirstInNDays = as.numeric(c(99999, 99999)),
          minPriorObservation = as.numeric(365),
          outcomeWashoutDays = as.numeric(c(99999)),
          riskWindowStart = as.numeric(0),
          startAnchor = 'cohort start',
          riskWindowEnd = as.numeric(0),
          endAnchor = 'cohort end',
          mode = 'CohortIncidence'
        ))
        stopifnot(length(spec) > 0)
        """
    )
    assert result.returncode == 0, result.stderr


def test_execution_settings_falls_back_when_max_cores_is_na() -> None:
    result = _run_r_or_skip(
        f"""
        if (!requireNamespace('Strategus', quietly = TRUE) ||
            !requireNamespace('CohortGenerator', quietly = TRUE)) quit(status = 42)
        library(Strategus)
        library(CohortGenerator)
        source('{EXECUTION_SETTINGS_SOURCE.as_posix()}')
        exec <- createStrategusExecutionSettings(settings = list(
          cdmDatabaseSchema = 'cdm',
          workDatabaseSchema = 'work',
          resultsDatabaseSchema = 'results',
          vocabularyDatabaseSchema = 'vocab',
          cohortTable = 'cohort',
          workFolder = tempdir(),
          resultsFolder = tempdir(),
          maxCores = NA,
          incremental = FALSE
        ))
        stopifnot(identical(exec$maxCores, 1L))
        stopifnot(exec$executionSettings$maxCores == 1)
        stopifnot(identical(exec$incremental, FALSE))
        """
    )
    assert result.returncode == 0, result.stderr


def test_cohort_method_spec_accepts_generated_argument_shape() -> None:
    result = _run_r_or_skip(
        """
        if (!requireNamespace('CohortMethod', quietly = TRUE) ||
            !requireNamespace('FeatureExtraction', quietly = TRUE) ||
            !requireNamespace('Cyclops', quietly = TRUE) ||
            !requireNamespace('Strategus', quietly = TRUE)) quit(status = 42)
        library(CohortMethod)
        library(Strategus)
        `%||%` <- function(x, y) if (is.null(x)) y else x
        call_with_supported_args <- function(fn, args) {
          formal_names <- names(formals(fn)) %||% character(0)
          if (!('...' %in% formal_names)) {
            args <- args[names(args) %in% formal_names]
          }
          do.call(fn, args)
        }
        has_exported_function <- function(package_name, function_name) {
          function_name %in% getNamespaceExports(package_name)
        }
        target_id <- as.numeric(1)
        comparator_id <- as.numeric(2)
        outcome_ids <- as.numeric(3)
        outcomes <- lapply(outcome_ids, function(outcome_id) {
          CohortMethod::createOutcome(
            outcomeId = outcome_id,
            outcomeOfInterest = TRUE,
            priorOutcomeLookback = 99999,
            riskWindowStart = 0,
            startAnchor = 'cohort start',
            riskWindowEnd = 0,
            endAnchor = 'cohort end'
          )
        })
        targetComparatorOutcomesList <- list(
          CohortMethod::createTargetComparatorOutcomes(
            targetId = target_id,
            comparatorId = comparator_id,
            outcomes = outcomes,
            excludedCovariateConceptIds = numeric(0),
            includedCovariateConceptIds = numeric(0)
          )
        )
        getDbArgs <- CohortMethod::createGetDbCohortMethodDataArgs(
          removeDuplicateSubjects = 'keep first, truncate to second',
          firstExposureOnly = TRUE,
          washoutPeriod = 365,
          restrictToCommonPeriod = TRUE,
          studyStartDate = '',
          studyEndDate = '',
          maxCohortSize = 0,
          covariateSettings = FeatureExtraction::createDefaultCovariateSettings()
        )
        studyPopulationArgs <- CohortMethod::createCreateStudyPopulationArgs(
          removeSubjectsWithPriorOutcome = TRUE,
          priorOutcomeLookback = 99999,
          minDaysAtRisk = 1,
          riskWindowStart = 0,
          startAnchor = 'cohort start',
          riskWindowEnd = 0,
          endAnchor = 'cohort end',
          censorAtNewRiskWindow = FALSE
        )
        outcomeModelPrior <- Cyclops::createPrior(priorType = 'laplace', useCrossValidation = TRUE)
        fitOutcomeModelArgs <- CohortMethod::createFitOutcomeModelArgs(
          modelType = 'cox',
          stratified = FALSE,
          useCovariates = FALSE,
          inversePtWeighting = FALSE,
          prior = outcomeModelPrior
        )
        cmAnalysisArgs <- list(
          analysisId = 1,
          description = 'test',
          getDbCohortMethodDataArgs = getDbArgs,
          createStudyPopulationArgs = studyPopulationArgs,
          createPsArgs = NULL,
          trimByPsArgs = NULL,
          trimByPsToEquipoiseArgs = NULL,
          matchOnPsArgs = NULL,
          stratifyByPsArgs = NULL,
          fitOutcomeModelArgs = fitOutcomeModelArgs
        )
        cmAnalysisFormals <- names(formals(CohortMethod::createCmAnalysis)) %||% character(0)
        if ('createStudyPopulationArgs' %in% cmAnalysisFormals) {
          cmAnalysisArgs$createStudyPopulationArgs <- studyPopulationArgs
        } else if ('createStudyPopArgs' %in% cmAnalysisFormals) {
          cmAnalysisArgs$createStudyPopArgs <- studyPopulationArgs
          cmAnalysisArgs$createStudyPopulationArgs <- NULL
        } else {
          stop('Unsupported CohortMethod::createCmAnalysis signature')
        }
        cmAnalysisList <- list(call_with_supported_args(CohortMethod::createCmAnalysis, cmAnalysisArgs))
        cmDiagnosticThresholds <- CohortMethod::createCmDiagnosticThresholds()
        cmModule <- CohortMethodModule$new()
        cmModuleFormals <- names(formals(cmModule$createModuleSpecifications)) %||% character(0)
        if ('cmAnalysesSpecifications' %in% cmModuleFormals) {
          if (!has_exported_function('CohortMethod', 'createCmAnalysesSpecifications')) {
            stop('Expected createCmAnalysesSpecifications export')
          }
          cmAnalysesSpecifications <- CohortMethod::createCmAnalysesSpecifications(
            cmAnalysisList = cmAnalysisList,
            targetComparatorOutcomesList = targetComparatorOutcomesList,
            cmDiagnosticThresholds = cmDiagnosticThresholds
          )
          spec <- call_with_supported_args(
            cmModule$createModuleSpecifications,
            list(cmAnalysesSpecifications = cmAnalysesSpecifications)
          )
        } else if (all(c('cmAnalysisList', 'targetComparatorOutcomesList') %in% cmModuleFormals)) {
          spec <- call_with_supported_args(
            cmModule$createModuleSpecifications,
            list(
              cmAnalysisList = cmAnalysisList,
              targetComparatorOutcomesList = targetComparatorOutcomesList,
              analysesToExclude = NULL,
              refitPsForEveryOutcome = FALSE,
              refitPsForEveryStudyPopulation = TRUE,
              cmDiagnosticThresholds = cmDiagnosticThresholds
            )
          )
        } else {
          stop('Unsupported CohortMethodModule signature')
        }
        stopifnot(length(spec) > 0)
        """
    )
    assert result.returncode == 0, result.stderr

def test_diagnostics_explorer_launcher_script_is_generated() -> None:
    source = SOURCE.read_text(encoding="utf-8")
    block = _generated_script_block(source, "script_08", "08_launch_diagnostics_explorer.R")

    assert "CohortDiagnostics" in block
    assert "launchDiagnosticsExplorer" in block
    assert "sqliteDbPath" in block
    assert "createMergedResultsFile" in block
    assert "Run this script in a second R session" in block


def test_cohort_method_shell_supports_multiple_cohort_acquisition_modes() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert 'Source for %s cohort [Enter=index search, db=existing database cohort, file=JSON file, dir=directory]:' in source
    assert 'prompt_database_cohort_imports <- function(role_label, allow_multiple = FALSE)' in source
    assert 'prompt_file_cohort_imports <- function(role_label, allow_multiple = FALSE)' in source
    assert 'prompt_directory_cohort_imports <- function(role_label, allow_multiple = FALSE)' in source
    assert 'strategus-cohort-source-db-details.json' in source
    assert 'cohort_source_db_details_need_configuration <- function(path)' in source
    assert 'Database cohort import requires a populated %s.' in source
    assert 'imported-cohort-definitions' in source


def test_cohort_method_shell_persists_neutral_source_metadata_for_imported_cohorts() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert 'target_source_id <- as.character(target_rec$selected_source_id %||% selected_target_id)' in source
    assert "source_type = as.character(target_rec$selection_source %||% 'recommendation')" in source
    assert "source_type = as.character(comparator_rec$selection_source %||% 'recommendation')" in source
    assert "source_type = as.character(outcome_rec$selection_source %||% 'recommendation')" in source
    assert 'Target: %s (source %s -> cohort %s)' in source
    assert 'Comparator: %s (source %s -> cohort %s)' in source
    assert '  - %s (source %s -> cohort %s)' in source
    assert 'atlas %s -> cohort %s' not in source


def test_cohort_method_shell_supports_direct_cohort_acquisition_bypass() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert 'Study intent [Enter to acquire cohorts directly; example: %s]:' in source
    assert 'choose_selection_source_mode <- function(role_label, allow_index = TRUE)' in source
    assert 'Source for %s cohort [db=existing database cohort, file=JSON file, dir=directory]:' in source
    assert 'direct_role_statement_default <- function(role_label, study_intent)' in source
    assert 'selection_source = "function_argument_direct"' in source
    assert 'direct_acquisition_mode = isTRUE(direct_acquisition_mode)' in source


def test_cohort_method_shell_still_supports_explicit_direct_bypass_prompt() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert "Skip ACP intent split and phenotype recommendation and acquire cohorts directly?" in source
    assert "blank_study_intent_direct_acquisition" in source
