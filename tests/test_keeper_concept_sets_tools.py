import json

import pytest

from study_agent_mcp.tools import keeper_concept_sets


class DummyMCP:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self, name: str):
        def decorator(fn):
            self.tools[name] = fn
            return fn

        return decorator


def _registered_tools():
    mcp = DummyMCP()
    keeper_concept_sets.register(mcp)
    return mcp.tools


@pytest.mark.mcp
def test_keeper_concept_set_bundle_renders_domain_prompt() -> None:
    tools = _registered_tools()
    result = tools["keeper_concept_set_bundle"](
        phenotype="Gastrointestinal bleeding",
        domain_key="doi",
    )

    assert result["task"] == "keeper_concept_sets_generate"
    assert result["domain"]["parameterName"] == "doi"
    assert "Gastrointestinal bleeding" in result["term_generation_prompt"]
    assert result["output_schema_generate_terms"]["title"] == "keeper_generate_terms_output"


@pytest.mark.mcp
def test_vocab_filter_standard_concepts_filters_domain_class_and_nonstandard() -> None:
    tools = _registered_tools()
    result = tools["vocab_filter_standard_concepts"](
        concepts=[
            {
                "conceptId": 1,
                "conceptName": "A",
                "domainId": "Condition",
                "conceptClassId": "Clinical Finding",
                "standardConcept": "S",
            },
            {
                "conceptId": 2,
                "conceptName": "B",
                "domainId": "Drug",
                "conceptClassId": "Ingredient",
                "standardConcept": "S",
            },
            {
                "conceptId": 3,
                "conceptName": "C",
                "domainId": "Condition",
                "conceptClassId": "Clinical Finding",
                "standardConcept": "N",
            },
        ],
        domains=["Condition"],
        concept_classes=["Clinical Finding"],
    )

    assert result["count"] == 1
    assert result["concepts"][0]["conceptId"] == 1


@pytest.mark.mcp
def test_vocab_remove_descendants_drops_selected_children() -> None:
    tools = _registered_tools()
    result = tools["vocab_remove_descendants"](
        concepts=[
            {"conceptId": 10, "conceptName": "Parent"},
            {"conceptId": 11, "conceptName": "Child"},
        ],
        ancestor_pairs=[{"ancestorConceptId": 10, "descendantConceptId": 11}],
    )

    assert result["count"] == 1
    assert result["removed_concept_ids"] == [11]
    assert result["concepts"][0]["conceptId"] == 10


@pytest.mark.mcp
def test_vocab_add_nonchildren_merges_and_skips_descendants() -> None:
    tools = _registered_tools()
    result = tools["vocab_add_nonchildren"](
        concepts=[{"conceptId": 10, "conceptName": "Parent"}],
        new_concepts=[
            {"conceptId": 11, "conceptName": "Child"},
            {"conceptId": 12, "conceptName": "Sibling"},
        ],
        ancestor_pairs=[{"ancestorConceptId": 10, "descendantConceptId": 11}],
    )

    assert result["count"] == 2
    assert [item["conceptId"] for item in result["concepts"]] == [10, 12]


@pytest.mark.mcp
def test_vocab_search_standard_reports_unconfigured_provider(monkeypatch) -> None:
    monkeypatch.delenv("VOCAB_SEARCH_PROVIDER", raising=False)
    tools = _registered_tools()
    result = tools["vocab_search_standard"](
        query="GI bleed",
        domains=["Condition"],
        concept_classes=[],
        limit=5,
    )

    assert result["error"] == "vocab_search_provider_unconfigured"
    assert result["count"] == 0


@pytest.mark.mcp
def test_phoebe_related_concepts_reports_unconfigured_provider(monkeypatch) -> None:
    monkeypatch.delenv("PHOEBE_PROVIDER", raising=False)
    tools = _registered_tools()
    result = tools["phoebe_related_concepts"](
        concept_ids=[1, 2],
    )

    assert result["error"] == "phoebe_provider_unconfigured"
    assert result["count"] == 0


@pytest.mark.mcp
def test_phoebe_related_concepts_rejects_legacy_hecate_url_template(monkeypatch) -> None:
    tools = _registered_tools()
    monkeypatch.setenv("PHOEBE_PROVIDER", "hecate_api")
    monkeypatch.delenv("PHOEBE_BULK_URL", raising=False)
    monkeypatch.setenv("PHOEBE_URL_TEMPLATE", "https://example.test/api/concepts/{concept_id}/phoebe")

    result = tools["phoebe_related_concepts"](
        concept_ids=[1],
    )

    assert result["error"] == "phoebe_provider_failed"
    assert result["count"] == 0
    assert result["details"] == "PHOEBE_URL_TEMPLATE is no longer supported for hecate_api; set PHOEBE_BULK_URL"


@pytest.mark.mcp
def test_vocab_search_standard_hecate_provider(monkeypatch) -> None:
    tools = _registered_tools()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return (
                b'{"concepts":[{"concept_id":101,"concept_name":"GI hemorrhage","vocabulary_id":"SNOMED",'
                b'"domain_id":"Condition","concept_class_id":"Clinical Finding","standard_concept":"S",'
                b'"record_count":42000}]}'
            )

    def fake_urlopen(request, timeout=30):
        assert "search_standard" in request.full_url
        assert "q=GI+bleed" in request.full_url
        return FakeResponse()

    monkeypatch.setattr(keeper_concept_sets.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("VOCAB_SEARCH_PROVIDER", "hecate_api")
    result = tools["vocab_search_standard"](
        query="GI bleed",
        domains=["Condition"],
        concept_classes=["Clinical Finding"],
        limit=5,
    )

    assert result["count"] == 1
    assert result["provider"] == "hecate_api"
    assert result["concepts"][0]["conceptId"] == 101


@pytest.mark.mcp
def test_phoebe_related_concepts_hecate_provider(monkeypatch) -> None:
    tools = _registered_tools()

    class FakeResponse:
        def __init__(self, body: bytes):
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return self._body

    def fake_urlopen(request, timeout=30):
        assert request.get_method() == "POST"
        assert "/api/concepts/phoebe/bulk" in request.full_url
        assert json.loads(request.data.decode("utf-8")) == {"ids": [4247297, 4116092]}
        body = json.dumps(
            [
                {
                    "concept_id": 4116092,
                    "results": [
                        {
                            "relationship_id": "Lexical via standard",
                            "concept_id": 2110451,
                            "concept_name": (
                                "Craniectomy for excision of brain tumor, infratentorial or posterior fossa; "
                                "cerebellopontine angle tumor"
                            ),
                            "vocabulary_id": "CPT4",
                            "record_count": 13380,
                        },
                        {
                            "relationship_id": "Ontology-parent",
                            "concept_id": 4311115,
                            "concept_name": "Intracranial mass",
                            "vocabulary_id": "SNOMED",
                            "record_count": 40790,
                        },
                    ],
                },
                {
                    "concept_id": 4247297,
                    "results": [
                        {
                            "relationship_id": "Lexical via standard",
                            "concept_id": 435509,
                            "concept_name": "Intracranial abscess",
                            "vocabulary_id": "SNOMED",
                            "record_count": 366720,
                        },
                        {
                            "relationship_id": "Ontology-parent",
                            "concept_id": 40480849,
                            "concept_name": "Abscess of brain",
                            "vocabulary_id": "SNOMED",
                            "record_count": 1490,
                        },
                    ],
                },
            ]
        ).encode("utf-8")
        return FakeResponse(body)

    monkeypatch.setattr(keeper_concept_sets.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("PHOEBE_PROVIDER", "hecate_api")
    result = tools["phoebe_related_concepts"](
        concept_ids=[4247297, 4116092],
        relationship_ids=["Ontology-parent"],
    )

    assert result["count"] == 2
    assert result["provider"] == "hecate_api"
    assert result["concepts"][0]["conceptId"] == 4311115
    assert result["concepts"][0]["sourceConceptId"] == 4116092
    assert result["concepts"][1]["conceptId"] == 40480849
    assert result["concepts"][1]["sourceConceptId"] == 4247297


@pytest.mark.mcp
def test_phoebe_related_concepts_hecate_provider_chunks_bulk_requests(monkeypatch) -> None:
    tools = _registered_tools()
    observed_payloads = []

    class FakeResponse:
        def __init__(self, body: bytes):
            self._body = body

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return self._body

    def fake_urlopen(request, timeout=30):
        payload = json.loads(request.data.decode("utf-8"))
        observed_payloads.append(payload)
        source_id = payload["ids"][0]
        if source_id == 4247297:
            result = {
                "concept_id": 435509,
                "concept_name": "Intracranial abscess",
                "vocabulary_id": "SNOMED",
                "record_count": 366720,
                "relationship_id": "Lexical via standard",
            }
        else:
            result = {
                "concept_id": 380055,
                "concept_name": "Primary malignant neoplasm of brain",
                "vocabulary_id": "SNOMED",
                "record_count": 10257990,
                "relationship_id": "Lexical via standard",
            }
        body = json.dumps(
            [
                {
                    "concept_id": source_id,
                    "results": [result],
                }
            ]
        ).encode("utf-8")
        return FakeResponse(body)

    monkeypatch.setattr(keeper_concept_sets.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("PHOEBE_PROVIDER", "hecate_api")
    concept_ids = [4247297] * 100 + [4116092]
    result = tools["phoebe_related_concepts"](
        concept_ids=concept_ids,
        relationship_ids=["Lexical via standard"],
    )

    assert observed_payloads == [{"ids": [4247297] * 100}, {"ids": [4116092]}]
    assert result["count"] == 2
    assert result["concepts"][0]["conceptId"] == 435509
    assert result["concepts"][0]["sourceConceptId"] == 4247297
    assert result["concepts"][1]["conceptId"] == 380055
    assert result["concepts"][1]["sourceConceptId"] == 4116092


@pytest.mark.mcp
def test_vocab_search_standard_generic_provider(monkeypatch) -> None:
    tools = _registered_tools()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def __init__(self, body: bytes):
            self._body = body

        def read(self):
            return self._body

    def fake_urlopen(request, timeout=30):
        assert request.full_url == "http://127.0.0.1:18080/search"
        payload = json.loads(request.data.decode("utf-8"))
        assert payload["query_text"] == "type 2 diabetes"
        assert payload["k"] == 5
        assert payload["domains"] == ["Condition"]
        body = (
            b'{"results":[{"concept_id":201826,"concept_name":"Type 2 diabetes mellitus",'
            b'"vocabulary_id":"SNOMED","domain_id":"Condition","concept_class_id":"Disorder",'
            b'"standard_concept":"S","score":0.97}]}'
        )
        return FakeResponse(body)

    monkeypatch.setattr(keeper_concept_sets.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("STUDY_AGENT_REWRITE_CONTAINER_HOSTS", "0")
    monkeypatch.setenv("VOCAB_SEARCH_PROVIDER", "generic_search_api")
    monkeypatch.setenv("VOCAB_SEARCH_URL", "http://127.0.0.1:18080/search")
    result = tools["vocab_search_standard"](
        query="type 2 diabetes",
        domains=["Condition"],
        concept_classes=[],
        limit=5,
    )

    assert result["count"] == 1
    assert result["provider"] == "generic_search_api"
    assert result["concepts"][0]["conceptId"] == 201826
    assert result["concepts"][0]["score"] == 0.97


@pytest.mark.mcp
def test_vocab_search_standard_generic_provider_applies_query_prefix(monkeypatch) -> None:
    tools = _registered_tools()

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def __init__(self, body: bytes):
            self._body = body

        def read(self):
            return self._body

    def fake_urlopen(request, timeout=30):
        payload = json.loads(request.data.decode("utf-8"))
        assert payload["query_text"] == "Instruction: retrieve related concepts. Query: stroke"
        return FakeResponse(b'{"results":[]}')

    monkeypatch.setattr(keeper_concept_sets.urllib.request, "urlopen", fake_urlopen)
    monkeypatch.setenv("STUDY_AGENT_REWRITE_CONTAINER_HOSTS", "0")
    monkeypatch.setenv("VOCAB_SEARCH_PROVIDER", "generic_search_api")
    monkeypatch.setenv("VOCAB_SEARCH_URL", "http://127.0.0.1:18080/search")
    monkeypatch.setenv("VOCAB_SEARCH_QUERY_PREFIX", "Instruction: retrieve related concepts. Query: ")
    result = tools["vocab_search_standard"](
        query="stroke",
        domains=["Condition"],
        concept_classes=[],
        limit=5,
    )

    assert result["count"] == 0
    assert result["request_payload"]["query_text"] == "Instruction: retrieve related concepts. Query: stroke"


@pytest.mark.mcp
def test_phoebe_related_concepts_db_provider(monkeypatch) -> None:
    tools = _registered_tools()

    class FakeResult:
        def mappings(self):
            return self

        def all(self):
            return [
                {
                    "source_concept_id": 192671,
                    "concept_id": 201,
                    "relationship_id": "Patient context",
                    "concept_name": "Upper GI endoscopy",
                    "domain_id": "Procedure",
                    "vocabulary_id": "SNOMED",
                    "concept_class_id": "Procedure",
                    "standard_concept": "S",
                }
            ]

    class FakeConnection:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def execute(self, stmt, params):
            sql_text = str(stmt)
            assert "concept_recommended" in sql_text
            assert "JOIN vocabulary.concept" in sql_text
            assert params["concept_ids"] == [192671]
            assert params["relationship_ids"] == ["Patient context"]
            return FakeResult()

    class FakeEngine:
        def connect(self):
            return FakeConnection()

    monkeypatch.setattr(keeper_concept_sets, "create_engine_with_dependencies", lambda *args, **kwargs: FakeEngine())
    monkeypatch.setenv("PHOEBE_PROVIDER", "db")
    monkeypatch.setenv("OMOP_DB_ENGINE", "postgresql://example")
    monkeypatch.setenv("VOCAB_DATABASE_SCHEMA", "vocabulary")
    result = tools["phoebe_related_concepts"](
        concept_ids=[192671],
        relationship_ids=["Patient context"],
    )

    assert result["count"] == 1
    assert result["provider"] == "db"
    assert result["concepts"][0]["conceptId"] == 201
    assert result["concepts"][0]["sourceConceptId"] == 192671


@pytest.mark.mcp
def test_vocab_filter_standard_concepts_db_enriches_sparse_rows(monkeypatch) -> None:
    tools = _registered_tools()

    monkeypatch.setattr(
        keeper_concept_sets,
        "_fetch_concepts_via_db",
        lambda concept_ids, domains=None, concept_classes=None, require_standard=False: {
            "concepts": [
                {
                    "conceptId": 439847,
                    "conceptName": "Intracranial hemorrhage",
                    "vocabularyId": "SNOMED",
                    "domainId": "Condition",
                    "conceptClassId": "Disorder",
                    "standardConcept": "S",
                }
            ],
            "count": 1,
            "provider": "db",
        },
    )
    monkeypatch.setenv("VOCAB_METADATA_PROVIDER", "db")
    result = tools["vocab_filter_standard_concepts"](
        concepts=[{"conceptId": 439847, "score": 0.98}],
        domains=["Condition"],
        concept_classes=[],
    )

    assert result["count"] == 1
    assert result["provider"] == "db"
    assert result["concepts"][0]["conceptName"] == "Intracranial hemorrhage"
    assert result["concepts"][0]["score"] == 0.98


@pytest.mark.mcp
def test_vocab_fetch_concepts_db_enriches_sparse_rows(monkeypatch) -> None:
    tools = _registered_tools()

    monkeypatch.setattr(
        keeper_concept_sets,
        "_fetch_concepts_via_db",
        lambda concept_ids, domains=None, concept_classes=None, require_standard=False: {
            "concepts": [
                {
                    "conceptId": 439847,
                    "conceptName": "Intracranial hemorrhage",
                    "vocabularyId": "SNOMED",
                    "domainId": "Condition",
                    "conceptClassId": "Disorder",
                    "standardConcept": "S",
                }
            ],
            "count": 1,
            "provider": "db",
        },
    )
    monkeypatch.setenv("VOCAB_METADATA_PROVIDER", "db")
    result = tools["vocab_fetch_concepts"](
        concept_ids=[439847],
        concepts=[{"conceptId": 439847, "score": 0.98}],
    )

    assert result["count"] == 1
    assert result["provider"] == "db"
    assert result["concepts"][0]["conceptName"] == "Intracranial hemorrhage"
    assert result["concepts"][0]["score"] == 0.98
