from pathlib import Path
import shutil
import subprocess

import pytest


SOURCE = Path("R/OHDSIAssistant/R/strategus_cohort_methods_shell.R")
EXECUTION_SETTINGS_SOURCE = Path("R/OHDSIAssistant/R/execution_settings.R")


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
    block = _generated_script_block(source, "script_06", "06_cm_spec.R")

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
    assert "createStudyPopulationArgs <- CohortMethod::createCreateStudyPopulationArgs(" in block
    assert "removeSubjectsWithPriorOutcome = studyPopulationDefaults$removeSubjectsWithPriorOutcome" in block
    assert "useRegularization =" not in block
    assert "prior = outcomeModelPrior" in block
    assert "CohortMethod::createCmAnalysesSpecifications(" in block
    assert "cmAnalysesSpecifications = cmAnalysesSpecifications$toList()" in block
    assert "ParallelLogger::saveSettingsToJson(analysisSpecifications, analysis_spec_path)" in block
    assert "result <- Strategus::execute(" in block
    assert "connectionDetails <- OHDSIAssistant::createStrategusConnectionDetails(path = db_details_path)" in block
    assert "exec <- OHDSIAssistant::createStrategusExecutionSettings(path = execution_settings_path)" in block
    assert "CohortMethod::runCmAnalyses(" not in block
    assert "CohortMethod::loadCmAnalysisList(" not in block
    assert "CohortMethod::loadTargetComparatorOutcomesList(" not in block


def test_cm_runner_is_merged_into_script_06() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert "script_07 <- c(" not in source
    assert 'write_lines(file.path(scripts_dir, "07_cm_run_analyses.R")' not in source
    assert 'cat("  - 07_cm_run_analyses.R\\n")' not in source


def test_characterization_spec_accepts_generated_numeric_types() -> None:
    result = _run_r_or_skip(
        """
        if (!requireNamespace('Strategus', quietly = TRUE)) quit(status = 42)
        library(Strategus)
        module <- CharacterizationModule$new()
        spec <- module$createModuleSpecifications(
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
        )
        stopifnot(identical(spec$module, 'CharacterizationModule'))
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
          maxCores = NA
        ))
        stopifnot(identical(exec$maxCores, 1L))
        stopifnot(exec$executionSettings$maxCores == 1)
        """
    )
    assert result.returncode == 0, result.stderr


def test_cohort_method_spec_accepts_generated_argument_shape() -> None:
    result = _run_r_or_skip(
        """
        if (!requireNamespace('CohortMethod', quietly = TRUE) ||
            !requireNamespace('FeatureExtraction', quietly = TRUE) ||
            !requireNamespace('Cyclops', quietly = TRUE)) quit(status = 42)
        library(CohortMethod)
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
        cmAnalysisList <- list(
          CohortMethod::createCmAnalysis(
            analysisId = 1,
            description = 'test',
            getDbCohortMethodDataArgs = getDbArgs,
            createStudyPopulationArgs = studyPopulationArgs,
            createPsArgs = NULL,
            trimByPsArgs = NULL,
            matchOnPsArgs = NULL,
            stratifyByPsArgs = NULL,
            fitOutcomeModelArgs = fitOutcomeModelArgs
          )
        )
        spec <- CohortMethod::createCmAnalysesSpecifications(
          cmAnalysisList = cmAnalysisList,
          targetComparatorOutcomesList = targetComparatorOutcomesList,
          cmDiagnosticThresholds = CohortMethod::createCmDiagnosticThresholds()
        )
        stopifnot(length(spec) > 0)
        """
    )
    assert result.returncode == 0, result.stderr
