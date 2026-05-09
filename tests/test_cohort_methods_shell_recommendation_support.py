from pathlib import Path

SOURCE = Path("R/OHDSIAssistant/R/strategus_cohort_methods_shell.R")


def test_shell_supports_namespaced_recommendation_ids_and_blocks_unsupported_selection() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert 'recommendation_identifier <- function(rec)' in source
    assert 'recommendation_is_ohdsi_computable <- function(rec)' in source
    assert 'grepl("^ohdsi:[0-9]+$", identifier)' in source
    assert 'unsupported_recommendation_message <- function(rec, role_label)' in source
    assert 'Descriptive phenotypes such as CIPHER recommendations are not yet convertible' in source
    assert 'stop(unsupported_recommendation_message(' in source


def test_shell_displays_noncomputable_recommendation_note() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert 'recommendation_id_label(rec)' in source
    assert 'Not directly computable in this workflow; descriptive phenotype conversion is not yet implemented.' in source
