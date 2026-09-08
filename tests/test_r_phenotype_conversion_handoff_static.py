from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "sandbox" / "slashOhdsiStrategusAssistant" / "R" / "phenotype_make_computable_review.R"
ACQUISITION = ROOT / "sandbox" / "slashOhdsiStrategusAssistant" / "R" / "cohort_acquisition.R"
INCIDENCE = ROOT / "sandbox" / "slashOhdsiStrategusAssistant" / "R" / "strategus_incidence_shell.R"
COHORT_METHODS = ROOT / "sandbox" / "slashOhdsiStrategusAssistant" / "R" / "strategus_cohort_methods_shell.R"


def test_mapping_evidence_handoff_remains_explicitly_review_gated() -> None:
    review = REVIEW.read_text(encoding="utf-8")
    acquisition = ACQUISITION.read_text(encoding="utf-8")

    assert '"mapping-concept-review.csv"' in review
    assert "Edit only review_* columns" in review
    assert '"mapping-concept-set-approval.json"' in acquisition
    assert 'type APPROVE' in acquisition
    assert 'concept_review_mode = "provided_only"' in review
    assert 'Use the prepared exposure-followed-by-outcome relationship as a scope template?' in acquisition
    assert 'conversion-provenance.json' in review
    assert 'conversion_source_provenance' in review
    assert 'source_payload_sha256' in review
    assert 'scope$temporal_followup <- list' in acquisition
    assert 'eligible_candidate_keys' in review
    assert 'not eligible for the confirmed-domain mapping review' in review
    assert 'mapping-evidence-confirmed-domains.json' in acquisition
    assert 'expected_domains = confirmed_domains' in acquisition
    assert 'atlas=import in Atlas and return corrected JSON' in acquisition
    assert 'More than 500 mapping candidates were returned' in acquisition
    assert 'More than 100 mapping candidates were returned' in acquisition
    assert 'expected_domains = as.list(expected_domains)' in (ROOT / "sandbox" / "slashOhdsiAcpClient" / "R" / "flows.R").read_text(encoding="utf-8")
    assert ".studyAgentSlashPreviewPhenotypeCandidate <- function" in review
    assert "Source algorithm narrative (evidence only" in review
    assert "Working local OMOP cohort statement" in acquisition


def test_incidence_recommendation_selection_routes_non_computable_items_to_review() -> None:
    incidence = INCIDENCE.read_text(encoding="utf-8")

    assert "prepare_recommended_phenotype <- function" in incidence
    assert ".studyAgentSlashPreparePhenotypeConversion(" in incidence
    assert ".studyAgentSlashCreateComputableRoleSelection(" in incidence
    assert "== Candidate definition preview ==" in incidence
    assert "type USE; /back returns to cohort-source selection" in incidence
    assert 'prepare_recommended_phenotype(selected_rec, "target")' in incidence
    assert 'prepare_recommended_phenotype(recommendations_outcome[[idx]], "outcome")' in incidence
    assert "ACP recommendation did not include a computable Circe JSON definition." not in incidence


def test_incidence_advice_does_not_end_the_session() -> None:
    incidence = INCIDENCE.read_text(encoding="utf-8")

    assert "Stopping after target advice" not in incidence
    assert "Stopping after outcome advice" not in incidence
    assert "rewrite=revise target statement" in incidence
    assert "rewrite=revise outcome statement" in incidence
    assert "choose create for Atlas review" in incidence


def test_cohort_methods_recommendation_selection_routes_non_computable_items_to_review() -> None:
    cohort_methods = COHORT_METHODS.read_text(encoding="utf-8")
    assert ".studyAgentSlashPreviewPhenotypeCandidate(" in cohort_methods
    assert "== Candidate definition preview ==" in cohort_methods
    assert "type USE; /back returns to cohort-source selection" in cohort_methods

    assert "collect_recommendation_selection <- function" in cohort_methods
    assert ".studyAgentSlashPreparePhenotypeConversion(" in cohort_methods
    assert "A local OMOP cohort definition has not been created." in cohort_methods
    assert "Stopping after %s advice" not in cohort_methods
    assert 'identical(target_rec$action %||% "", "retry")' in cohort_methods
    assert 'identical(comparator_rec$action %||% "", "retry")' in cohort_methods
    assert 'vapply(outcome_recs, function(rec) identical(rec$action %||% "", "retry")' in cohort_methods
