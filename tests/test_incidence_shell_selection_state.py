from pathlib import Path

from _repo_paths import repo_path


SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "strategus_incidence_shell.R")

def test_outcome_selection_state_is_initialized_before_target_mapping_prompt() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    init = source.index("selected_ids_outcome <- character(0)")
    first_target_prompt = source.index(
        'selected_outcome_ids = as.list(selected_ids_outcome %||% list())'
    )

    assert init < first_target_prompt


def test_default_id_mapping_uses_numeric_suffix_for_ohdsi_ids() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert "default_cohort_id_from_source <- function(source_id)" in source
    assert "grepl(\"^ohdsi:[0-9]+$\", source_id)" in source
    assert "sub(\"^ohdsi:\", \"\", source_id)" in source
    assert "if (!use_mapping) return(default_cohort_ids_from_sources(ids, role_label = \"selected\"))" in source


def test_improvement_errors_are_not_silently_treated_as_empty_results() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert "extract_phenotype_improvement_items <- function(resp, cohort_label)" in source
    assert "ACP returned an error for %s phenotype improvements: %s" in source

def test_time_at_risk_configuration_context_and_state_are_persisted() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert 'set_dialogue_context(' in source
    assert '"time_at_risk_configuration"' in source
    assert 'denominator_guidance = "Denominators depend on cohort entry logic, TAR definitions, and chosen strata settings."' in source
    assert 'time_at_risk_settings_path <- file.path(analysis_settings_dir, "time_at_risk_settings.json")' in source
    assert 'incidence_time_at_risk <- collect_time_at_risk_settings(' in source
    assert 'write_json(incidence_time_at_risk, time_at_risk_settings_path)' in source
    assert 'time_at_risk_settings_path = time_at_risk_settings_path' in source
    assert 'incidence_time_at_risk = incidence_time_at_risk' in source


def test_generated_incidence_script_uses_persisted_time_at_risk_settings() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    start = source.index('script_07 <- c(')
    end = source.index('write_lines(file.path(scripts_dir, "07_incidence_spec.R")', start)
    block = source[start:end]

    assert "time_at_risk_settings_path <- file.path(analysis_settings_dir, 'time_at_risk_settings.json')" in block
    assert "tar_settings <- jsonlite::fromJSON(time_at_risk_settings_path, simplifyVector = FALSE)" in block
    assert "tar_defs <- tar_settings$time_at_risk_defs %||% list()" in block
    assert "CohortIncidence::createTimeAtRiskDef(" in block
    assert "analysis_tar_ids <- as.numeric(unlist(tar_settings$analysis_tar_ids %||% lapply(tar_defs, function(def) def$id), use.names = FALSE))" in block
    assert "target_ids <- suppressWarnings(as.integer(unlist(roles$targets %||% integer(0), use.names = FALSE)))" in block
    assert "outcome_ids <- suppressWarnings(as.integer(unlist(roles$outcomes %||% integer(0), use.names = FALSE)))" in block
    assert "cohortDefinitionSet$cohortId <- suppressWarnings(as.integer(cohortDefinitionSet$cohortId))" in block
    assert "CohortIncidence::createCohortRef(id = as.integer(id), name = row$cohortName[1])" in block
    assert "CohortIncidence::createOutcomeDef(id = as.integer(id), name = row$cohortName[1])" in block
    assert "strata_args <- tar_settings$strata_settings %||% list()" in block
    assert 'strataSettings <- do.call(CohortIncidence::createStrataSettings, strata_args)' in block
    assert 'tars = analysis_tar_ids' in block
    assert "CohortIncidence::createTimeAtRiskDef(id = 1, startWith = 'start', endWith = 'end')" not in block
    assert "CohortIncidence::createTimeAtRiskDef(id = 2, startWith = 'start', endWith = 'start', endOffset = 365)" not in block
    assert 'tars = c(1, 2)' not in block
    assert 'createStrataSettings(byYear = TRUE, byGender = TRUE)' not in block


def test_shell_seeds_runtime_templates_and_generated_scripts_use_them() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert 'seed_strategus_runtime_templates <- function(base_dir)' in source
    assert 'strategus-db-details.json' in source
    assert 'strategus-execution-settings.json' in source
    assert 'execution_settings_path = execution_settings_path,' in source

    script03_start = source.index('script_03 <- c(')
    script03_end = source.index('write_lines(file.path(scripts_dir, "03_generate_cohorts.R")', script03_start)
    script03 = source[script03_start:script03_end]
    assert "db_details_path <- file.path(base_dir, 'strategus-db-details.json')" in script03
    assert "execution_settings_path <- file.path(base_dir, 'strategus-execution-settings.json')" in script03
    assert "createStrategusConnectionDetails(path = db_details_path)" in script03
    assert "createStrategusExecutionSettings(path = execution_settings_path)" in script03
    assert "<FILL IN>" not in script03

    script05_start = source.index('script_06 <- c(')
    script05_end = source.index('write_lines(file.path(scripts_dir, "06_diagnostics.R")', script05_start)
    script05 = source[script05_start:script05_end]
    assert "db_details_path <- file.path(base_dir, 'strategus-db-details.json')" in script05
    assert "execution_settings_path <- file.path(base_dir, 'strategus-execution-settings.json')" in script05
    assert "createStrategusConnectionDetails(path = db_details_path)" in script05
    assert "createStrategusExecutionSettings(path = execution_settings_path)" in script05
    assert "<FILL IN>" not in script05

    script06_start = source.index('script_07 <- c(')
    script06_end = source.index('write_lines(file.path(scripts_dir, "07_incidence_spec.R")', script06_start)
    script06 = source[script06_start:script06_end]
    assert "db_details_path <- file.path(base_dir, 'strategus-db-details.json')" in script06
    assert "execution_settings_path <- file.path(base_dir, 'strategus-execution-settings.json')" in script06
    assert "createStrategusConnectionDetails(path = db_details_path)" in script06
    assert "createStrategusExecutionSettings(path = execution_settings_path)" in script06
    assert "<FILL IN>" not in script06
