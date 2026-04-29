import json
from pathlib import Path

import pytest

from study_agent_mcp.retrieval.index import PhenotypeIndex


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
