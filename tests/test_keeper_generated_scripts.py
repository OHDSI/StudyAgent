from _repo_paths import repo_path


COHORT_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "strategus_cohort_methods_shell.R")
INCIDENCE_SOURCE = repo_path("R", "slashOhdsiStrategusAssistant", "R", "strategus_incidence_shell.R")


def _generated_script_block(source: str, script_name: str, filename: str) -> str:
    start = source.index(f"{script_name} <- c(")
    end = source.index(f'write_lines(file.path(scripts_dir, "{filename}")', start)
    return source[start:end]


def _assert_concept_set_script_contract(block: str, intent_fragment: str) -> None:
    assert "runKeeperConceptSetWorkflow(" in block
    assert intent_fragment in block
    assert "keeper_concept_set_state.json" in block
    assert "acp_timeout_seconds <- as.numeric(Sys.getenv('ACP_TIMEOUT', '300'))" in block
    assert "Sys.setenv(ACP_TIMEOUT = as.character(acp_timeout_seconds))" in block
    assert "`%||%` <- function(x, y) if (is.null(x)) y else x" in block
    assert "acp_timeout_seconds = acp_timeout_seconds" in block
    assert "reuse_generated_concept_sets <- TRUE" in block
    assert "overwrite_approved_concept_sets <- FALSE" in block
    assert "overwrite_approved_concept_sets = overwrite_approved_concept_sets" in block
    assert "reuse_generated_concept_sets = reuse_generated_concept_sets" in block
    assert "candidate_limit = candidate_limit" in block
    assert "domain_keys = domain_keys" in block
    assert "sample_size <- 5" not in block
    assert "review_row_limit <- 5" not in block
    assert "reuse_rows <- TRUE" not in block
    assert "resume_reviews <- TRUE" not in block
    assert "review_row_selection <- NULL" not in block
    assert "library(Keeper)" not in block
    assert "library(DatabaseConnector)" not in block
    assert "createKeeper(" not in block
    assert "databaseId" not in block
    assert "strategus-db-details.json" not in block


def _assert_case_review_script_contract(block: str, intent_fragment: str) -> None:
    assert "runKeeperCaseReviewWorkflow(" in block
    assert intent_fragment in block
    assert "keeper_case_review_state.json" in block
    assert "acp_timeout_seconds <- as.numeric(Sys.getenv('ACP_TIMEOUT', '300'))" in block
    assert "Sys.setenv(ACP_TIMEOUT = as.character(acp_timeout_seconds))" in block
    assert "`%||%` <- function(x, y) if (is.null(x)) y else x" in block
    assert "acp_timeout_seconds = acp_timeout_seconds" in block
    assert "sample_size <- 5" in block
    assert "review_row_limit <- 5" in block
    assert "reuse_rows <- FALSE" in block
    assert "resume_reviews <- TRUE" in block
    assert "review_row_selection <- NULL  # e.g. '1-3,5'" in block
    assert "sample_size = sample_size" in block
    assert "review_row_limit = review_row_limit" in block
    assert "reuse_rows = reuse_rows" in block
    assert "resume_reviews = resume_reviews" in block
    assert "review_row_selection = review_row_selection" in block
    assert "remove_pii = TRUE" in block
    assert "domain_keys = domain_keys" not in block
    assert "reuse_generated_concept_sets <- TRUE" not in block
    assert "overwrite_approved_concept_sets <- FALSE" not in block
    assert "library(Keeper)" not in block
    assert "library(DatabaseConnector)" not in block
    assert "createKeeper(" not in block
    assert "databaseId" not in block
    assert "strategus-db-details.json" not in block


def test_cohort_method_generated_keeper_concept_set_script_uses_acp_helper_only() -> None:
    block = _generated_script_block(COHORT_SOURCE.read_text(encoding="utf-8"), "script_04", "04_keeper_concept_sets.R")
    _assert_concept_set_script_contract(block, "cohort_methods_intent_split.json")


def test_incidence_generated_keeper_concept_set_script_uses_acp_helper_only() -> None:
    block = _generated_script_block(INCIDENCE_SOURCE.read_text(encoding="utf-8"), "script_04", "04_keeper_concept_sets.R")
    _assert_concept_set_script_contract(block, "intent_split.json")


def test_cohort_method_generated_keeper_case_review_script_uses_acp_helper_only() -> None:
    block = _generated_script_block(COHORT_SOURCE.read_text(encoding="utf-8"), "script_05", "05_keeper_case_review.R")
    _assert_case_review_script_contract(block, "cohort_methods_intent_split.json")


def test_incidence_generated_keeper_case_review_script_uses_acp_helper_only() -> None:
    block = _generated_script_block(INCIDENCE_SOURCE.read_text(encoding="utf-8"), "script_05", "05_keeper_case_review.R")
    _assert_case_review_script_contract(block, "intent_split.json")
