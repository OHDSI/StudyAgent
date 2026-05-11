from pathlib import Path


SOURCE = Path("R/slashOhdsiStrategusAssistant/R/strategus_incidence_shell.R")


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
