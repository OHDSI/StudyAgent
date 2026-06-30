from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
FLOWS_SOURCE = REPO_ROOT / "R/slashOhdsiAcpClient/R/flows.R"
RUNTIME_SOURCE = REPO_ROOT / "R/slashOhdsiStrategusAssistant/R/slash_ohdsi_runtime.R"
NAMESPACE_SOURCE = REPO_ROOT / "R/slashOhdsiAcpClient/NAMESPACE"


def test_keeper_concept_set_wrapper_covers_full_r_contract() -> None:
    source = FLOWS_SOURCE.read_text(encoding="utf-8")

    assert "acp_keeper_concept_sets_generate <- function(" in source
    assert "domain_keys = NULL" in source
    assert "vocab_search_provider = NULL" in source
    assert "phoebe_provider = NULL" in source
    assert "min_record_count = NULL" in source
    assert 'acp_call_flow(client, "keeper_concept_sets_generate", body)' in source
    assert 'body$vocab_search_provider <- trimws(as.character(vocab_search_provider))' in source
    assert 'body$phoebe_provider <- trimws(as.character(phoebe_provider))' in source
    assert 'body$min_record_count <- as.numeric(min_record_count)' in source


def test_keeper_profile_and_review_wrappers_are_exposed() -> None:
    source = FLOWS_SOURCE.read_text(encoding="utf-8")
    namespace = NAMESPACE_SOURCE.read_text(encoding="utf-8")

    assert "acp_keeper_profiles_generate <- function(" in source
    assert 'acp_call_flow(client, "keeper_profiles_generate", body)' in source
    assert "keeper_concept_sets = NULL" in source
    assert "keeper_concept_sets_path = NULL" in source
    assert 'keeper_concept_sets <- .acp_load_keeper_concept_sets(keeper_concept_sets_path)' in source
    assert 'body$keeper_concept_sets <- .acp_minimize_keeper_concept_sets(keeper_concept_sets)' in source
    assert "person_ids = as.list(person_ids)" in source
    assert "acp_phenotype_validation_review <- function(" in source
    assert "keeper_row_path = NULL" in source
    assert "row_index = NULL" in source
    assert "keeper_row <- .acp_load_keeper_row(keeper_row_path, row_index = row_index)" in source
    assert "body$keeper_row <- .acp_minimize_keeper_row(keeper_row)" in source
    assert ".acp_minimize_keeper_row <- function(keeper_row) {" in source
    assert '"phenotype_validation_review"' in source
    assert "export(acp_keeper_profiles_generate)" in namespace
    assert "export(acp_phenotype_validation_review)" in namespace


def test_strategus_runtime_exposes_keeper_passthrough_helpers() -> None:
    source = RUNTIME_SOURCE.read_text(encoding="utf-8")

    assert ".studyAgentSlashAcpKeeperConceptSetsGenerate <- function(" in source
    assert "slashOhdsiAcpClient::acp_keeper_concept_sets_generate(" in source
    assert ".studyAgentSlashAcpKeeperProfilesGenerate <- function(" in source
    assert "slashOhdsiAcpClient::acp_keeper_profiles_generate(" in source
    assert "keeper_concept_sets_path = NULL" in source
    assert ".studyAgentSlashAcpPhenotypeValidationReview <- function(" in source
    assert "keeper_row_path = NULL" in source
    assert "row_index = NULL" in source
    assert "slashOhdsiAcpClient::acp_phenotype_validation_review(" in source
