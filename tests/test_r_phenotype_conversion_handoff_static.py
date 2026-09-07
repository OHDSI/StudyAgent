from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVIEW = ROOT / "sandbox" / "slashOhdsiStrategusAssistant" / "R" / "phenotype_make_computable_review.R"
ACQUISITION = ROOT / "sandbox" / "slashOhdsiStrategusAssistant" / "R" / "cohort_acquisition.R"


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
    assert 'Concept review source [mapping=review mapped candidates, search=run ACP vocabulary search]' in acquisition
