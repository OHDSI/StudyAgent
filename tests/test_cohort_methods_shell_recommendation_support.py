from pathlib import Path

from _repo_paths import repo_path

SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "strategus_cohort_methods_shell.R")

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

def test_shell_resolves_namespaced_source_definition_filenames() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert 'resolve_index_definition_path <- function(source_id, index_def_dir)' in source
    assert 'sprintf("ohdsi__%s.json", source_text)' in source
    assert 'gsub(":", "__", source_text, fixed = TRUE)' in source
    assert 'src <- resolve_index_definition_path(source_id, index_def_dir)' in source


def test_shell_normalizes_namespaced_cached_and_manual_cohort_ids() -> None:
    source = SOURCE.read_text(encoding="utf-8")

    assert 'parse_single_cohort_id <- function(x)' in source
    assert 'if (grepl("^ohdsi:[0-9]+$", piece)) {' in source
    assert 'sub("^ohdsi:", "", piece)' in source
    assert 'parse_single_cohort_id(item$original_id %||% NA_integer_)' in source
    assert 'parse_single_cohort_id(item$cohort_id %||% NA_integer_)' in source
    assert 'original_ids <- parse_ids(unlist(mapping$original_id %||% integer(0), use.names = FALSE))' in source
    assert 'cohort_ids <- parse_ids(unlist(mapping$cohort_id %||% integer(0), use.names = FALSE))' in source