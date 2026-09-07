import json
from pathlib import Path

import pytest

from study_agent_mcp.retrieval.index import PhenotypeIndex
from study_agent_mcp.tools.phenotype_present import build_presentation
from study_agent_mcp.tools.phenotype_conversion_readiness import assess_readiness
from study_agent_mcp.tools.phenotype_code_mapping_evidence import summarize_mapping


@pytest.mark.mcp
def test_fetch_summary_exposes_retrieval_fields(tmp_path) -> None:
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    catalog_path = index_dir / "catalog.jsonl"
    row = {
        "phenotype_id": "cipher:test-1",
        "source_dataset": "va_cipher",
        "source_record_type": "disease_phenotype",
        "name": "Post-traumatic stress disorder",
        "short_description": "PTSD phenotype",
        "tags": ["General"],
        "raw_keywords": ["veteran"],
        "retrieval_keywords": ["PTSD", "trauma cohort"],
        "retrieval_keywords_source": "llm_cached",
        "retrieval_concept_labels": ["ICD-10 Diagnostic Codes", "PTSD"],
        "methodology_summary": "Codes and narrative evidence for PTSD.",
        "primary_clinical_topic": "Post-traumatic stress disorder",
        "secondary_topics": ["trauma"],
        "phenotype_role": "diagnosis",
        "care_setting_scope": "outpatient",
        "population_scope": "veterans",
        "topic_mentions": {"primary_topics": ["post-traumatic stress disorder"], "context_only_topics": [], "downstream_or_related_topics": ["trauma"]},
        "target_vs_context_conditions": {"target_conditions": ["post-traumatic stress disorder"], "context_conditions": []},
        "exclude_from_primary_topic_match": ["trauma study context"],
        "recommendation_summary": "PTSD diagnosis phenotype for veterans.",
        "recommendation_metadata_source": "llm_cached",
        "signals": ["source:cipher", "execution:codes_only"],
        "ontology_keys": [],
        "code_systems": [],
        "executable_definition_status": "codes_only",
        "execution_readiness_score": 0.45,
        "adaptation_notes": "Requires translation to OHDSI logic.",
    }
    catalog_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    (index_dir / "meta.json").write_text(json.dumps({"catalog_count": 1}), encoding="utf-8")

    idx = PhenotypeIndex(str(index_dir), allow_dense=False, allow_sparse=False).load()
    summary = idx.fetch_summary("cipher:test-1")

    assert summary is not None
    assert summary["raw_keywords"] == ["veteran"]
    assert summary["retrieval_keywords"] == ["PTSD", "trauma cohort"]
    assert summary["retrieval_keywords_source"] == "llm_cached"
    assert summary["retrieval_concept_labels"] == ["ICD-10 Diagnostic Codes", "PTSD"]
    assert summary["methodology_summary"] == "Codes and narrative evidence for PTSD."
    assert summary["primary_clinical_topic"] == "Post-traumatic stress disorder"
    assert summary["phenotype_role"] == "diagnosis"
    assert summary["care_setting_scope"] == "outpatient"
    assert summary["recommendation_metadata_source"] == "llm_cached"


@pytest.mark.mcp
def test_fetch_source_snapshot_uses_indexed_copy_and_canonical_hash(tmp_path) -> None:
    index_dir = tmp_path / "index"
    definitions_dir = index_dir / "definitions"
    definitions_dir.mkdir(parents=True)
    payload = {"algorithm": {"algorithmDesc": "Use two qualifying events."}, "id": 42}
    (definitions_dir / "cipher__42.json").write_text(json.dumps(payload), encoding="utf-8")
    row = {
        "phenotype_id": "cipher:42",
        "source_dataset": "va_cipher",
        "source_record_type": "disease_phenotype",
        "name": "Example CIPHER phenotype",
        "definition_ref": "cipher__42.json",
        "provenance": {"version": "v7", "modified_at": "2026-09-01"},
    }
    (index_dir / "catalog.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    (index_dir / "meta.json").write_text(json.dumps({"catalog_count": 1}), encoding="utf-8")

    index = PhenotypeIndex(str(index_dir), allow_dense=False, allow_sparse=False).load()
    snapshot = index.fetch_source_snapshot("cipher:42")

    assert snapshot is not None
    assert snapshot["source_payload"] == payload
    assert snapshot["source_revision"] == "v7"
    assert snapshot["source_modified_at"] == "2026-09-01"
    assert snapshot["source_payload_sha256"] == "5b909a1b85b9527d17fad18e679ce57e085796e886ddbbcdccd0910f99f1f742"


@pytest.mark.mcp
def test_build_presentation_distinguishes_circe_and_cipher_evidence() -> None:
    cipher = build_presentation(
        {
            "phenotype_id": "cipher:29197",
            "source_dataset": "va_cipher",
            "title": "ACE Inhibitor Induced Cough",
            "source_payload_sha256": "source-hash",
            "source_payload": {"algorithm": {"algorithmDesc": "Cases have cough after ACE inhibitor exposure."}},
        },
        {"source_dataset": "va_cipher", "code_systems": [{"system_name": "Text snippets", "codes": ["cough"]}]},
    )
    circe = build_presentation(
        {
            "phenotype_id": "ohdsi:925",
            "source_dataset": "ohdsi_phenotype_library",
            "title": "Cough",
            "source_payload": {"PrimaryCriteria": {"CriteriaList": [{}]}, "ConceptSets": [{"name": "Cough"}]},
        },
        {"source_dataset": "ohdsi_phenotype_library", "code_systems": []},
    )

    assert cipher["use_mode"] == "requires_readiness_assessment"
    assert cipher["clinical_pattern"]["algorithm_description"].startswith("Cases have cough")
    assert "Text snippets are narrative evidence, not an OMOP concept set." in cipher["important_gaps"]
    assert circe["use_mode"] == "direct"
    assert circe["available_actions"] == ["use_directly", "inspect_circe_definition"]


@pytest.mark.mcp
def test_conversion_readiness_is_source_and_deployment_aware() -> None:
    snapshot = {"source_dataset": "va_cipher", "source_payload": {"algorithm": {"algorithmDesc": "Use first qualifying event."}}}
    supported = assess_readiness(snapshot, {"source_dataset": "va_cipher", "code_systems": [{"system_name": "ICD-10 Diagnostic Codes", "codes": ["I25.1"]}]}, {"ICD10CM"})
    unavailable = assess_readiness(snapshot, {"source_dataset": "va_cipher", "code_systems": [{"system_name": "ICD-10 Diagnostic Codes", "codes": ["I25.1"]}]}, set())
    text_only = assess_readiness(snapshot, {"source_dataset": "va_cipher", "code_systems": [{"system_name": "Text snippets", "codes": ["cough"]}]}, set())

    assert supported["action_class"] == "conversion_candidate"
    assert supported["code_systems"][0]["mapping_support"] == "available"
    assert unavailable["action_class"] == "source_informed_review"
    assert text_only["action_class"] == "source_informed_review"

@pytest.mark.mcp
def test_mapping_evidence_is_exact_and_never_selects_concepts() -> None:
    lanes = [{"source_system": "ICD-10 Diagnostic Codes", "vocabulary_id": "ICD10CM", "codes": ["I25.1", "R79.81", "missing"], "source_code_count": 3, "truncated": False}]
    rows = [
        {"vocabulary_id": "ICD10CM", "concept_code": "I25.1", "standard_concept_id": 101, "standard_concept_name": "Atherosclerotic heart disease", "standard_vocabulary_id": "SNOMED", "standard_domain_id": "Condition"},
        {"vocabulary_id": "ICD10CM", "concept_code": "R79.81", "standard_concept_id": 102, "standard_concept_name": "Abnormal blood-gas level", "standard_vocabulary_id": "SNOMED", "standard_domain_id": "Condition"},
        {"vocabulary_id": "ICD10CM", "concept_code": "R79.81", "standard_concept_id": 103, "standard_concept_name": "Hypoxemia", "standard_vocabulary_id": "SNOMED", "standard_domain_id": "Condition"},
    ]

    evidence = summarize_mapping(lanes, rows)

    assert evidence["coverage"] == {"requested_code_count": 3, "matched_source_code_count": 2, "mapped_code_count": 1, "ambiguous_mapping_count": 1, "no_standard_mapping_count": 0, "unmatched_source_code_count": 1}
    assert evidence["code_results"][0]["status"] == "mapped"
    assert evidence["code_results"][1]["status"] == "ambiguous_mapping"
    assert evidence["code_results"][2]["status"] == "unmatched_source_code"
