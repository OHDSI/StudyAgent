import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "mcp_server" / "scripts" / "build_phenotype_index.py"
SPEC = importlib.util.spec_from_file_location("build_phenotype_index", MODULE_PATH)
assert SPEC and SPEC.loader
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def test_build_ohdsi_row_adds_concept_evidence_and_retrieval_fields() -> None:
    definition = {
        "ConceptSets": [
            {
                "name": "COVID-19 condition",
                "expression": {"items": [{"concept": {"CONCEPT_ID": 37311061, "CONCEPT_CODE": "840539006", "CONCEPT_NAME": "Disease caused by SARS-CoV-2", "VOCABULARY_ID": "SNOMED", "DOMAIN_ID": "Condition"}}]},
            },
            {
                "name": "SARS-CoV-2 test",
                "expression": {"items": [{"concept": {"CONCEPT_ID": 756055, "CONCEPT_CODE": "U0003", "CONCEPT_NAME": "SARS-CoV-2 test", "VOCABULARY_ID": "HCPCS", "DOMAIN_ID": "Measurement"}}]},
            },
        ]
    }
    meta = {
        "cohortId": "2",
        "cohortName": "COVID-19 positive test or diagnosis",
        "logicDescription": "Persons with a COVID-19 condition or positive SARS-CoV-2 test.",
        "notes": "Uses diagnosis or measurement entry criteria.",
        "hashTag": "covid-19, infection",
        "recommendedReferentConceptIds": "37311061;756055",
        "numberOfInclusionRules": "0",
        "numberOfConceptSets": "2",
        "domainsInEntryEvents": "Condition;Measurement",
        "status": "Published",
        "demographicCriteriaGender": "Any",
        "createdDate": "2020-01-01",
        "modifiedDate": "2020-01-02",
        "addedVersion": "v1",
        "librarian": "Test Librarian",
    }

    row = builder._build_ohdsi_row(meta, definition)

    assert row["raw_keywords"] == []
    assert "native OHDSI cohort" in row["retrieval_keywords"]
    assert "SARS-CoV-2 test" in row["retrieval_concept_labels"]
    assert "HCPCS" in row["retrieval_concept_labels"]
    assert row["methodology_summary"] == "Native OHDSI cohort with 2 concept sets and 0 inclusion rules."
    assert row["concept_evidence"]["coverage_summary"] == {
        "has_codes": True,
        "has_labels": True,
        "has_omop_mapping": True,
    }
    vocab_names = {item["system_name"] for item in row["code_systems"]}
    assert "SNOMED" in vocab_names
    assert "HCPCS" in vocab_names
    assert "HCPCS" in row["retrieval_text"]

def test_build_cipher_row_preserves_raw_keywords_and_derived_labels() -> None:
    enum_map = {
        1: {"fieldName": "ICD-9 Diagnostic Codes", "vaSpecific": False},
        2: {"fieldName": "ICD-10 Diagnostic Codes", "vaSpecific": False},
    }
    record = {
        "id": 42,
        "fullName": "Abdominal aortic aneurysm (MAP)",
        "phenotypeCategory": "General",
        "description": "MAP is an unsupervised clustering algorithm for abdominal aortic aneurysm.",
        "algorithm": {
            "algorithmDesc": "Uses ICD code evidence.",
            "assocCodes": [
                {"codeType": 1, "codes": [{"code": "441.4"}], "description": "ICD-9 Diagnostic Codes"},
                {"codeType": 2, "codes": [{"code": "I71.4"}], "description": "ICD-10 Diagnostic Codes"},
            ],
        },
    }

    row = builder._build_cipher_row("fixture.json", record, enum_map)

    assert row["tags"] == ["General"]
    assert row["raw_keywords"] == []
    assert "ICD-9 Diagnostic Codes" in row["retrieval_concept_labels"]
    assert "MAP" in row["retrieval_keywords"]
    assert row["methodology_summary"].startswith("MAP is an unsupervised clustering algorithm")
    assert row["concept_evidence"]["coverage_summary"]["has_codes"] is True
    assert row["concept_evidence"]["coverage_summary"]["has_labels"] is True
    assert any(item["system_name"] == "ICD-10 Diagnostic Codes" for item in row["code_systems"])

def _sample_row() -> dict:
    return {
        "phenotype_id": "cipher:test-1",
        "source_dataset": "va_cipher",
        "name": "Post-traumatic stress disorder",
        "short_description": "PTSD phenotype for veterans.",
        "long_description": "Derived phenotype with ICD and narrative evidence.",
        "tags": ["General"],
        "raw_keywords": ["veteran"],
        "retrieval_keywords": ["General", "veteran", "ICD-10 Diagnostic Codes", "PTSD"],
        "retrieval_concept_labels": ["ICD-10 Diagnostic Codes", "PTSD"],
        "methodology_summary": "Codes and narrative evidence for PTSD.",
        "ontology_keys": [],
        "signals": ["source:cipher", "execution:codes_only", "method_family:map"],
        "executable_definition_status": "codes_only",
        "adaptation_notes": "Requires translation to OHDSI logic.",
        "primary_clinical_topic": "Post-traumatic stress disorder",
        "secondary_topics": [],
        "phenotype_role": "unknown",
        "care_setting_scope": "unspecified",
        "population_scope": "",
        "topic_mentions": {"primary_topics": ["Post-traumatic stress disorder"], "context_only_topics": [], "downstream_or_related_topics": []},
        "target_vs_context_conditions": {"target_conditions": ["Post-traumatic stress disorder"], "context_conditions": []},
        "exclude_from_primary_topic_match": [],
        "recommendation_summary": "PTSD phenotype for veterans.",
        "recommendation_metadata_source": "heuristic",
    }


def test_apply_llm_retrieval_keywords_uses_llm_and_cache(monkeypatch) -> None:
    calls = []

    def fake_call(prompt: str) -> dict:
        calls.append(prompt)
        return {
            "status": "ok",
            "parsed_content": {"retrieval_keywords": ["PTSD", "veteran cohort", "trauma", "ICD-10"]},
        }

    monkeypatch.setattr(builder, "_call_keyword_llm", fake_call)
    cache = {}
    row = _sample_row()

    builder._apply_llm_retrieval_keywords(row, cache, enabled=True, max_terms=6)

    assert row["retrieval_keywords_source"] == "llm"
    assert row["retrieval_keywords"] == ["PTSD", "veteran cohort", "trauma", "ICD-10"]
    assert len(cache) == 1
    assert len(calls) == 1

    monkeypatch.setattr(builder, "_call_keyword_llm", lambda prompt: (_ for _ in ()).throw(AssertionError("should use cache")))
    cached_row = _sample_row()
    builder._apply_llm_retrieval_keywords(cached_row, cache, enabled=True, max_terms=6)

    assert cached_row["retrieval_keywords_source"] == "llm_cached"
    assert cached_row["retrieval_keywords"] == ["PTSD", "veteran cohort", "trauma", "ICD-10"]



def test_apply_llm_retrieval_keywords_falls_back_on_invalid_llm(monkeypatch) -> None:
    monkeypatch.setattr(
        builder,
        "_call_keyword_llm",
        lambda prompt: {"status": "schema_mismatch", "parsed_content": {}},
    )
    cache = {}
    row = _sample_row()
    fallback = list(row["retrieval_keywords"])

    builder._apply_llm_retrieval_keywords(row, cache, enabled=True, max_terms=6)

    assert row["retrieval_keywords_source"] == "heuristic"
    assert row["retrieval_keywords"] == fallback
    assert cache == {}


def test_apply_llm_retrieval_keywords_returns_cache_entry(monkeypatch) -> None:
    monkeypatch.setattr(
        builder,
        "_call_keyword_llm",
        lambda prompt: {
            "status": "ok",
            "parsed_content": {"retrieval_keywords": ["PTSD", "trauma cohort"]},
        },
    )
    cache = {}
    row = _sample_row()

    entry = builder._apply_llm_retrieval_keywords(row, cache, enabled=True, max_terms=6)

    assert entry is not None
    assert entry["phenotype_id"] == "cipher:test-1"
    assert entry["cache_key"].startswith("cipher:test-1:")
    assert entry["retrieval_keywords"] == ["PTSD", "trauma cohort"]



def test_apply_llm_recommendation_metadata_uses_llm_and_cache(monkeypatch) -> None:
    calls = []

    def fake_call(prompt: str) -> dict:
        calls.append(prompt)
        return {
            "status": "ok",
            "parsed_content": {
                "primary_clinical_topic": "Post-traumatic stress disorder",
                "secondary_topics": ["trauma"],
                "phenotype_role": "diagnosis",
                "care_setting_scope": "outpatient",
                "population_scope": "veterans",
                "topic_mentions": {
                    "primary_topics": ["post-traumatic stress disorder"],
                    "context_only_topics": [],
                    "downstream_or_related_topics": ["trauma"],
                },
                "target_vs_context_conditions": {
                    "target_conditions": ["post-traumatic stress disorder"],
                    "context_conditions": [],
                },
                "exclude_from_primary_topic_match": ["trauma study context"],
                "recommendation_summary": "PTSD diagnosis phenotype for veterans.",
            },
        }

    monkeypatch.setattr(builder, "_call_recommendation_metadata_llm", fake_call)
    cache = {}
    row = _sample_row()

    entry = builder._apply_llm_recommendation_metadata(row, cache, enabled=True)

    assert row["recommendation_metadata_source"] == "llm"
    assert row["phenotype_role"] == "diagnosis"
    assert row["care_setting_scope"] == "outpatient"
    assert row["primary_clinical_topic"] == "Post-traumatic stress disorder"
    assert row["recommendation_summary"] == "PTSD diagnosis phenotype for veterans."
    assert entry is not None
    assert entry["cache_key"].startswith("recommendation:cipher:test-1:")
    assert len(calls) == 1

    monkeypatch.setattr(builder, "_call_recommendation_metadata_llm", lambda prompt: (_ for _ in ()).throw(AssertionError("should use cache")))
    cached_row = _sample_row()
    builder._apply_llm_recommendation_metadata(cached_row, cache, enabled=True)

    assert cached_row["recommendation_metadata_source"] == "llm_cached"
    assert cached_row["phenotype_role"] == "diagnosis"
    assert cached_row["care_setting_scope"] == "outpatient"


def test_jsonl_cache_append_and_load_round_trip(tmp_path) -> None:
    cache_path = tmp_path / "keyword_cache.jsonl"
    entry_a = {
        "cache_key": "cipher:test-1:abc",
        "phenotype_id": "cipher:test-1",
        "retrieval_keywords": ["PTSD", "trauma cohort"],
    }
    entry_b = {
        "cache_key": "ohdsi:2:def",
        "phenotype_id": "ohdsi:2",
        "retrieval_keywords": ["COVID-19", "SARS-CoV-2"],
    }

    builder._append_jsonl_cache_entry(str(cache_path), entry_a)
    builder._append_jsonl_cache_entry(str(cache_path), entry_b)

    loaded = builder._load_jsonl_cache(str(cache_path))

    assert loaded["cipher:test-1:abc"]["retrieval_keywords"] == ["PTSD", "trauma cohort"]
    assert loaded["ohdsi:2:def"]["retrieval_keywords"] == ["COVID-19", "SARS-CoV-2"]


def test_build_keyword_prompt_uses_prompt_bundle_files() -> None:
    prompt = builder._build_keyword_prompt(
        {
            "phenotype_id": "cipher:test-1",
            "name": "Post-traumatic stress disorder",
        },
        max_terms=8,
    )

    assert "Task: `phenotype_index_keywords`." in prompt
    assert "Output contract:" in prompt
    assert '"retrieval_keywords"' in prompt
    assert '"max_terms": 8' in prompt


def test_main_dense_only_reuses_existing_catalog(monkeypatch, tmp_path) -> None:
    out_dir = tmp_path / "index"
    out_dir.mkdir()
    row = {
        "phenotype_id": "cipher:test-1",
        "name": "PTSD phenotype",
        "retrieval_text": "ptsd veteran trauma",
    }
    (out_dir / "catalog.jsonl").write_text(json.dumps(row) + "\n", encoding="utf-8")
    (out_dir / "meta.json").write_text(json.dumps({"catalog_count": 1, "source_counts": {"va_cipher": 1}}), encoding="utf-8")

    def fake_build_dense_index(catalog, output_path, embed_client, cache_path, batch_size=64, require_dense=False):
        Path(output_path).write_text("dense-placeholder", encoding="utf-8")
        Path(cache_path).write_bytes(b"cache")
        return {"status": "ok", "dim": 8, "count": len(catalog)}

    monkeypatch.setattr(builder, "_build_dense_index", fake_build_dense_index)
    monkeypatch.setattr(
        "sys.argv",
        [
            "build_phenotype_index.py",
            "--output-dir",
            str(out_dir),
            "--build-dense",
            "--dense-only",
        ],
    )

    rc = builder.main()

    assert rc == 0
    meta = json.loads((out_dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["dense"] == {"status": "ok", "dim": 8, "count": 1}
    assert (out_dir / "dense.index").exists()
    catalog_text = (out_dir / "catalog.jsonl").read_text(encoding="utf-8")
    assert "text_for_embedding_hash" not in catalog_text or "text_for_embedding" not in catalog_text or isinstance(catalog_text, str)
