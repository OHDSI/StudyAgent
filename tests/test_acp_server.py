import pytest

from study_agent_acp import server as acp_server
from study_agent_acp.mcp_client import StdioMCPClient
from study_agent_acp.agent import StudyAgent
from study_agent_acp.llm_client import LLMCallResult


@pytest.mark.acp
def test_acp_shutdown_closes_mcp_client():
    class FakeServer:
        def serve_forever(self) -> None:
            raise RuntimeError("stop")

    class FakeMCPClient:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    fake_server = FakeServer()
    fake_client = FakeMCPClient()

    try:
        acp_server._serve(fake_server, fake_client)
    except RuntimeError:
        pass

    assert fake_client.closed is True


@pytest.mark.acp
def test_mcp_health_check_success():
    class Portal:
        def call(self, func, *args, **kwargs):
            return func(*args, **kwargs)

    class Client:
        def __init__(self):
            self._portal = Portal()
            self._session = True

        def _ensure_session(self):
            return None

        def _ping(self):
            return {"ok": True}

        health_check = StdioMCPClient.health_check

    client = Client()
    assert client.health_check() == {"ok": True}


@pytest.mark.acp
def test_resolve_mcp_url_from_env(monkeypatch):
    monkeypatch.delenv("STUDY_AGENT_MCP_URL", raising=False)
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "8790")
    monkeypatch.setenv("MCP_PATH", "/mcp")

    assert acp_server._resolve_mcp_url_from_env() == "http://127.0.0.1:8790/mcp"


@pytest.mark.acp
def test_resolve_mcp_url_from_env_prefers_explicit(monkeypatch):
    monkeypatch.setenv("STUDY_AGENT_MCP_URL", "http://example.test:9999/custom")
    monkeypatch.setenv("MCP_TRANSPORT", "http")
    monkeypatch.setenv("MCP_HOST", "127.0.0.1")
    monkeypatch.setenv("MCP_PORT", "8790")
    monkeypatch.setenv("MCP_PATH", "/mcp")

    assert acp_server._resolve_mcp_url_from_env() == "http://example.test:9999/custom"


@pytest.mark.acp
def test_health_reports_mcp_not_configured():
    handler = acp_server.ACPRequestHandler.__new__(acp_server.ACPRequestHandler)
    handler.path = "/health"
    handler.headers = {}
    handler.debug = False
    handler.agent = StudyAgent(mcp_client=None)
    handler.mcp_client = None
    handler.wfile = None
    handler.rfile = None

    captured = {}

    def fake_write_json(_handler, status, payload):
        captured["status"] = status
        captured["payload"] = payload

    original = acp_server._write_json
    acp_server._write_json = fake_write_json
    try:
        handler.do_GET()
    finally:
        acp_server._write_json = original

    assert captured["status"] == 200
    assert captured["payload"] == {
        "status": "ok",
        "mcp": {"ok": False, "configured": False, "error": "mcp_not_configured"},
        "mcp_index": {"skipped": True, "reason": "mcp_not_configured"},
    }


class StubMCPClient:
    def __init__(self) -> None:
        self.calls = []

    def list_tools(self):
        return []

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "phenotype_improvements":
            return {"plan": "ok", "phenotype_improvements": []}
        if name == "phenotype_prompt_bundle":
            return {"overview": "overview", "spec": "spec", "output_schema": {"type": "object"}}
        if name == "phenotype_recommendation_advice":
            return {"overview": "overview", "spec": "spec", "output_schema": {"type": "object"}}
        if name == "phenotype_intent_split":
            return {"overview": "overview", "spec": "spec", "output_schema": {"type": "object"}}
        if name == "cohort_methods_intent_split":
            return {"overview": "overview", "spec": "spec", "output_schema": {"type": "object"}}
        if name == "lint_prompt_bundle":
            return {"overview": "overview", "spec": "spec", "output_schema": {"type": "object"}}
        if name == "keeper_sanitize_row":
            return {"sanitized_row": {"age_bucket": "40-44", "gender": "Male"}}
        if name == "keeper_prompt_bundle":
            return {
                "overview": "overview",
                "spec": "spec",
                "output_schema": {"type": "object"},
                "system_prompt": "system",
            }
        if name == "keeper_build_prompt":
            return {"prompt": "main"}
        if name == "keeper_parse_response":
            return {"label": "yes", "rationale": "ok"}
        if name == "case_causal_review_sanitize_row":
            return {
                "sanitized_row": {
                    "case_id": "case-1",
                    "case_summary": "GI bleed after anticoagulation.",
                    "index_event": {
                        "domain": "index_event",
                        "label": "GI bleed",
                        "source_record_id": "reaction-1",
                        "subrole": "index_event",
                        "annotations": {"adverse_event_concept_id": 321, "adverse_event_meddra_id": "789"},
                    },
                    "candidate_items": [
                        {
                            "domain": "drug_exposures",
                            "label": "Warfarin",
                            "source_record_id": "drug-1",
                            "source_kind": "reported_drug",
                            "subrole": "primary_suspect",
                            "annotations": {"has_disproportional_signal": True, "label_mentions_event": True, "ingredient_concept_id": 123, "ingred_rxcui": "456"},
                        }
                    ],
                    "candidate_items_by_domain": {
                        "drug_exposures": [
                            {
                                "domain": "drug_exposures",
                                "label": "Warfarin",
                                "source_record_id": "drug-1",
                                "source_kind": "reported_drug",
                                "subrole": "primary_suspect",
                                "annotations": {"has_disproportional_signal": True, "label_mentions_event": True, "ingredient_concept_id": 123, "ingred_rxcui": "456"},
                            }
                        ]
                    },
                    "context_items": [
                        {
                            "domain": "labs",
                            "label": "INR 4.2",
                            "source_record_id": "lab-1",
                            "subrole": "proximate_marker",
                            "annotations": {},
                        }
                    ],
                    "context_items_by_domain": {"labs": [{"domain": "labs", "label": "INR 4.2", "source_record_id": "lab-1", "subrole": "proximate_marker", "annotations": {}}]},
                    "case_metadata": {"literature_reference_present": True, "lookup_key": {"primaryid": None, "isr": "6526923"}},
                    "annotations": {"concept_set_id": "uuid", "concept_set_version": 1, "concept_set_available_domains": ["drug_exposures"]},
                    "tool_hints": dict(arguments.get("case_row", {}).get("tool_hints") or {"available_expansions": ["get_case_review_drug_signal_details", "get_case_review_report_literature_stub"], "prefetch_expansions": []}),
                },
                "diagnostics": {"sanitization_status": "ok"},
            }
        if name == "case_causal_review_prompt_bundle":
            return {
                "overview": "overview",
                "spec": "spec",
                "output_schema": {"type": "object"},
                "system_prompt": "system",
            }
        if name == "get_case_review_concept_set_domain":
            return {"status": "ok", "domain_name": arguments.get("domain_name"), "items": []}
        if name == "get_case_review_drug_signal_details":
            return {
                "status": "ok",
                "source_record_id": arguments.get("source_record_id"),
                "adverse_event_concept_id": arguments.get("adverse_event_concept_id"),
                "has_disproportional_signal": True,
            }
        if name == "get_case_review_drug_label_details":
            return {
                "status": "ok",
                "source_record_id": arguments.get("source_record_id"),
                "adverse_event_concept_id": arguments.get("adverse_event_concept_id"),
                "label_mentions_event": True,
            }
        if name == "get_case_review_report_literature_stub":
            return {"status": "ok", "case_id": arguments.get("case_id"), "literature_reference_present": True}
        if name == "case_causal_review_build_prompt":
            return {
                "prompt": "main",
                "prompt_payload": {
                    "task": "case_causal_review",
                    "adverse_event_name": arguments.get("adverse_event_name"),
                    "source_type": arguments.get("source_type"),
                    "enrichment": arguments.get("enrichment") or {},
                },
            }
        if name == "case_causal_review_parse_response":
            return {
                "candidates_by_domain": {
                    "drug_exposures": [
                        {
                            "domain": "drug_exposures",
                            "label": "Warfarin",
                            "source_record_id": "drug-1",
                            "why_it_may_contribute": "Bleeding risk",
                            "confidence": "high",
                            "rank": 1,
                            "candidate_role": "primary_suspect",
                            "evidence_basis": "Signal and label metadata",
                        }
                    ]
                },
                "narrative": "Warfarin is a plausible contributor.",
                "mode": "case_causal_review",
                "diagnostics": {"parse_mode": "dict"},
            }
        if name == "keeper_concept_set_bundle":
            if arguments.get("domain_key"):
                domain_key = arguments["domain_key"]
                return {
                    "task": "keeper_concept_sets_generate",
                    "overview": "overview",
                    "domain": {
                        "parameterName": domain_key,
                        "domains": ["Condition"],
                        "conceptClasses": [],
                    },
                    "spec_generate_terms": "spec terms",
                    "spec_filter_concepts": "spec filter",
                    "output_schema_generate_terms": {"type": "object"},
                    "output_schema_filter_concepts": {"type": "object"},
                    "term_generation_prompt": f"generate {domain_key}",
                    "concept_filter_prompt": f"filter {domain_key}",
                }
            return {
                "task": "keeper_concept_sets_generate",
                "domains": [
                    {"parameterName": "doi"},
                    {"parameterName": "alternativeDiagnosis"},
                    {"parameterName": "symptoms"},
                ],
            }
        if name == "keeper_profile_extract":
            return {
                "profile_records": [
                    {
                        "generatedId": "1",
                        "category": "phenotype",
                        "conceptName": "GI bleed",
                        "startDay": 0,
                        "endDay": 0,
                        "target": "Other",
                        "extraData": "",
                    },
                    {
                        "generatedId": "1",
                        "category": "age",
                        "conceptName": "44",
                        "startDay": 0,
                        "endDay": 0,
                        "target": "Disease of interest",
                        "extraData": "",
                    },
                ],
                "record_count": 2,
                "sample_size_requested": 2,
                "sample_size_returned": 1,
                "sampling_mode": "ordered_head",
            }
        if name == "keeper_profile_to_rows":
            return {
                "rows": [
                    {
                        "generatedId": "1",
                        "phenotype": "GI bleed",
                        "age": "44",
                        "gender": "Male",
                        "presentation": "",
                    }
                ],
                "row_count": 1,
            }
        if name == "vocab_search_standard":
            term = arguments["query"]
            if "Mallory" in term:
                return {
                    "error": "vocab_search_provider_unconfigured",
                    "concepts": [],
                    "count": 0,
                }
            if "Gastrointestinal bleeding" in term or "hemorrhage" in term:
                return {
                    "concepts": [
                        {
                            "conceptId": 100,
                            "conceptName": "Gastrointestinal hemorrhage",
                            "vocabularyId": "SNOMED",
                            "domainId": "Condition",
                            "conceptClassId": "Clinical Finding",
                            "standardConcept": "S",
                            "recordCount": 50000,
                        }
                    ],
                    "count": 1,
                }
            if "abdominal pain" in term:
                return {
                    "concepts": [
                        {
                            "conceptId": 200,
                            "conceptName": "Abdominal pain",
                            "vocabularyId": "SNOMED",
                            "domainId": "Condition",
                            "conceptClassId": "Clinical Finding",
                            "standardConcept": "S",
                            "recordCount": 75000,
                        }
                    ],
                    "count": 1,
                }
            return {"concepts": [], "count": 0}
        if name == "vocab_filter_standard_concepts":
            return {"concepts": arguments.get("concepts", []), "count": len(arguments.get("concepts", []))}
        if name == "vocab_fetch_concepts":
            concepts = arguments.get("concepts", [])
            selected = set(arguments.get("concept_ids", []))
            return {
                "concepts": [concept for concept in concepts if concept.get("conceptId") in selected],
                "count": len([concept for concept in concepts if concept.get("conceptId") in selected]),
            }
        if name == "vocab_remove_descendants":
            return {"concepts": arguments.get("concepts", []), "count": len(arguments.get("concepts", []))}
        if name == "phoebe_related_concepts":
            return {"error": "phoebe_provider_unconfigured", "concepts": [], "count": 0}
        if name == "vocab_add_nonchildren":
            concepts = list(arguments.get("concepts", [])) + list(arguments.get("new_concepts", []))
            return {"concepts": concepts, "count": len(concepts)}
        if name == "propose_concept_set_diff":
            return {"plan": "ok", "findings": [], "patches": [], "actions": [], "risk_notes": []}
        if name == "cohort_lint":
            return {"plan": "ok", "findings": [], "patches": [], "actions": [], "risk_notes": []}
        raise ValueError("unexpected tool")


@pytest.mark.acp
def test_flow_phenotype_improvements_calls_tool(monkeypatch):
    import study_agent_acp.agent as agent_module

    def fake_llm(prompt):
        return {"phenotype_improvements": []}

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)
    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_phenotype_improvements_flow(
        protocol_text="protocol",
        cohorts=[{"id": 1}, {"id": 2}],
        characterization_previews=[],
    )
    assert result["status"] == "ok"
    assert result["tool"] == "phenotype_improvements"
    assert result["cohort_count"] == 1


@pytest.mark.acp
def test_flow_concept_sets_review_calls_tool(monkeypatch):
    import study_agent_acp.agent as agent_module

    def fake_llm(prompt):
        return {"findings": [], "patches": [], "risk_notes": [], "actions": []}

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)
    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_concept_sets_review_flow(
        concept_set={"items": []},
        study_intent="intent",
    )
    assert result["status"] == "ok"
    assert result["tool"] == "propose_concept_set_diff"


@pytest.mark.acp
def test_flow_cohort_critique_calls_tool(monkeypatch):
    import study_agent_acp.agent as agent_module

    def fake_llm(prompt):
        return {"findings": [], "patches": [], "risk_notes": []}

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)
    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_cohort_critique_general_design_flow(cohort={"PrimaryCriteria": {}})
    assert result["status"] == "ok"
    assert result["tool"] == "cohort_lint"


@pytest.mark.acp
def test_flow_phenotype_validation_review(monkeypatch):
    import study_agent_acp.agent as agent_module

    def fake_llm(prompt):
        return {"label": "yes", "rationale": "ok"}

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)
    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_phenotype_validation_review_flow(
        keeper_row={"age": 44, "gender": "Male"},
        disease_name="GI bleed",
    )
    assert result["status"] == "ok"
    assert result["full_result"]["label"] == "yes"


@pytest.mark.acp
def test_flow_keeper_concept_sets_generate(monkeypatch):
    import study_agent_acp.agent as agent_module

    calls = {"count": 0}

    def fake_llm(prompt, required_keys=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return {"terms": ["Gastrointestinal bleeding", "hemorrhage"]}
        if calls["count"] == 2:
            return {"conceptId": [100]}
        if calls["count"] == 3:
            return {"conceptId": [100]}
        if calls["count"] == 4:
            return {"terms": ["Mallory-Weiss tear", "Peptic ulcer disease"]}
        if calls["count"] == 5:
            return {"conceptId": []}
        if calls["count"] == 6:
            return {"conceptId": []}
        if calls["count"] == 7:
            return {"terms": ["abdominal pain"]}
        if calls["count"] == 8:
            return {"conceptId": [200]}
        if calls["count"] == 9:
            return {"conceptId": [200]}
        if required_keys == ["terms"]:
            return {"terms": []}
        return {"conceptId": []}

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)
    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_keeper_concept_sets_generate_flow(
        phenotype="Gastrointestinal bleeding",
        include_diagnostics=True,
    )
    assert result["status"] == "ok"
    assert result["phenotype"] == "Gastrointestinal bleeding"
    assert len(result["concept_sets"]) == 2
    assert {item["conceptSetName"] for item in result["concept_sets"]} == {"doi", "symptoms"}
    assert any(domain["domain_key"] == "alternativeDiagnosis" for domain in result["domains"])
    assert result["diagnostics"]["domain_runs"][0]["domain_key"] == "doi"


@pytest.mark.acp
def test_flow_keeper_concept_sets_generate_salvages_concepts_array_schema(monkeypatch):
    import study_agent_acp.agent as agent_module

    calls = {"count": 0}

    def fake_llm(prompt, required_keys=None):
        calls["count"] += 1
        if calls["count"] == 1:
            return {"terms": ["Gastrointestinal bleeding", "hemorrhage"]}
        if calls["count"] == 2:
            return {
                "concepts": [
                    {"concept_id": 100, "concept_name": "Gastrointestinal hemorrhage"},
                ]
            }
        if calls["count"] == 3:
            return {
                "concepts": [
                    {"concept_id": 100, "concept_name": "Gastrointestinal hemorrhage"},
                ]
            }
        return {"conceptId": []}

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)
    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_keeper_concept_sets_generate_flow(
        phenotype="Gastrointestinal bleeding",
        domain_keys=["doi"],
        include_diagnostics=True,
    )
    assert result["status"] == "ok"
    assert len(result["concept_sets"]) == 1
    assert result["concept_sets"][0]["conceptId"] == 100
    run = result["diagnostics"]["domain_runs"][0]
    assert run["llm_filter_initial_salvage_mode"] == "concepts_array"
    assert run["llm_filter_final_salvage_mode"] == "concepts_array"


@pytest.mark.acp
def test_flow_keeper_profiles_generate():
    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_keeper_profiles_generate_flow(
        cohort_database_schema="results",
        cohort_table="cohort",
        cohort_definition_id=123,
        cdm_database_schema="cdm",
        keeper_concept_sets=[{"conceptId": 100, "conceptName": "GI bleed", "vocabularyId": "SNOMED", "conceptSetName": "doi", "target": "Disease of interest"}],
        sample_size=2,
        phenotype_name="GI bleed",
        remove_pii=True,
    )
    assert result["status"] == "ok"
    assert result["row_count"] == 1
    assert result["sample_size_requested"] == 2
    assert result["sample_size_returned"] == 1


@pytest.mark.acp
def test_extract_keeper_concept_ids_handles_scalar_and_top_level_array():
    from study_agent_acp.agent import StudyAgent
    from study_agent_acp.llm_client import LLMCallResult

    agent = StudyAgent(mcp_client=StubMCPClient())

    scalar_ids, scalar_mode = agent._extract_keeper_concept_ids(
        LLMCallResult(status="ok", parsed_content={"conceptId": "439847"})
    )
    assert scalar_ids == [439847]
    assert scalar_mode == "scalar_conceptId"

    array_ids, array_mode = agent._extract_keeper_concept_ids(
        LLMCallResult(
            status="ok",
            parsed_content=[
                {"conceptId": "42872434"},
                {"concept_id": "439847"},
            ],
        )
    )
    assert array_ids == [42872434, 439847]
    assert array_mode == "top_level_array"


@pytest.mark.acp
def test_flow_phenotype_recommendation_advice(monkeypatch):
    import study_agent_acp.agent as agent_module

    captured = {}

    def fake_llm(prompt):
        captured["prompt"] = prompt
        return {
            "plan": "plan",
            "advice": "Refine intent",
            "next_steps": ["step1"],
            "questions": ["question1"],
        }

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)
    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_phenotype_recommendation_advice_flow(
        study_intent="Intent text",
    )
    assert result["status"] == "ok"
    assert result["llm_used"] is True
    assert result["llm_status"] == "ok"
    assert result["advice"]["advice"] == "Refine intent"
    assert "Intent text" in captured.get("prompt", "")


@pytest.mark.acp
def test_flow_phenotype_recommendation_advice_parse_failure(monkeypatch):
    import study_agent_acp.agent as agent_module

    def fake_llm(prompt, required_keys=None):
        return LLMCallResult(
            status="json_parse_failed",
            error="json_parse_failed",
            parse_stage="chat_completions_content:json_brace_extract",
            request_mode="chat_completions",
        )

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)
    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_phenotype_recommendation_advice_flow(
        study_intent="Intent text",
    )
    assert result["status"] == "ok"
    assert result["llm_used"] is False
    assert result["llm_status"] == "json_parse_failed"
    assert result["fallback_reason"] == "llm_json_parse_failed"
    assert result["fallback_mode"] == "stub"
    assert result["advice"]["mode"] == "stub"


@pytest.mark.acp
def test_flow_phenotype_recommendation_advice_missing_intent():
    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_phenotype_recommendation_advice_flow(study_intent="")
    assert result["status"] == "error"
    assert result["error"] == "missing study_intent"


@pytest.mark.acp
def test_flow_phenotype_recommendation_advice_prompt_bundle_error(monkeypatch):
    import study_agent_acp.agent as agent_module

    def fake_llm(prompt):
        return {"advice": "unused"}

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)

    class BadMCPClient(StubMCPClient):
        def call_tool(self, name, arguments):
            if name == "phenotype_recommendation_advice":
                return {"error": "bad prompt"}
            return super().call_tool(name, arguments)

    agent = StudyAgent(mcp_client=BadMCPClient())
    result = agent.run_phenotype_recommendation_advice_flow(
        study_intent="Intent text",
    )
    assert result["status"] == "error"
    assert result["error"] == "phenotype_recommendation_advice_prompt_failed"


@pytest.mark.acp
def test_flow_phenotype_intent_split(monkeypatch):
    import study_agent_acp.agent as agent_module

    captured = {}

    def fake_llm(prompt):
        captured["prompt"] = prompt
        return {
            "plan": "plan",
            "target_statement": "Target cohort",
            "outcome_statement": "Outcome cohort",
            "rationale": "Rationale",
            "questions": ["question1"],
        }

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)
    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_phenotype_intent_split_flow(
        study_intent="Intent text",
    )
    assert result["status"] == "ok"
    assert result["llm_used"] is True
    assert result["llm_status"] == "ok"
    assert result["intent_split"]["target_statement"] == "Target cohort"
    assert "Intent text" in captured.get("prompt", "")


@pytest.mark.acp
def test_flow_phenotype_intent_split_schema_mismatch(monkeypatch):
    import study_agent_acp.agent as agent_module

    def fake_llm(prompt, required_keys=None):
        return LLMCallResult(
            status="schema_mismatch",
            parsed_content={"target_statement": "Target only"},
            parse_stage="chat_completions_content:schema",
            error="missing_required_keys:outcome_statement,rationale",
            missing_keys=["outcome_statement", "rationale"],
            schema_valid=False,
            request_mode="chat_completions",
        )

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)
    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_phenotype_intent_split_flow(
        study_intent="Intent text",
    )
    assert result["status"] == "error"
    assert result["error"] == "llm_unavailable"
    assert result["diagnostics"]["llm_status"] == "schema_mismatch"
    assert result["diagnostics"]["llm_missing_keys"] == ["outcome_statement", "rationale"]


@pytest.mark.acp
def test_flow_phenotype_intent_split_missing_intent():
    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_phenotype_intent_split_flow(study_intent="")
    assert result["status"] == "error"
    assert result["error"] == "missing study_intent"


@pytest.mark.acp
def test_flow_phenotype_intent_split_prompt_bundle_error(monkeypatch):
    import study_agent_acp.agent as agent_module

    def fake_llm(prompt):
        return {"target_statement": "unused"}

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)

    class BadMCPClient(StubMCPClient):
        def call_tool(self, name, arguments):
            if name == "phenotype_intent_split":
                return {"error": "bad prompt"}
            return super().call_tool(name, arguments)

    agent = StudyAgent(mcp_client=BadMCPClient())
    result = agent.run_phenotype_intent_split_flow(
        study_intent="Intent text",
    )
    assert result["status"] == "error"
    assert result["error"] == "phenotype_intent_split_prompt_failed"


@pytest.mark.acp
def test_flow_cohort_methods_intent_split(monkeypatch):
    import study_agent_acp.agent as agent_module

    captured = {}

    def fake_llm(prompt, required_keys=None):
        captured["prompt"] = prompt
        captured["required_keys"] = required_keys
        return {
            "status": "ok",
            "plan": "plan",
            "target_statement": "Metformin users",
            "comparator_statement": "Sulfonylurea users",
            "outcome_statement": "GI bleeding",
            "outcome_statements": ["GI bleeding", "Stroke"],
            "rationale": "Rationale",
            "questions": [],
        }

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)
    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_cohort_methods_intent_split_flow(
        study_intent="Compare metformin versus sulfonylurea on GI bleeding.",
    )
    assert result["status"] == "ok"
    assert result["intent_split"]["target_statement"] == "Metformin users"
    assert result["intent_split"]["comparator_statement"] == "Sulfonylurea users"
    assert result["intent_split"]["outcome_statements"] == ["GI bleeding", "Stroke"]
    assert "cohort_methods_intent_split" in captured.get("prompt", "")
    assert "comparator_statement" in captured.get("required_keys", [])
    assert "outcome_statements" in captured.get("required_keys", [])


@pytest.mark.acp
def test_flow_cohort_methods_intent_split_schema_mismatch(monkeypatch):
    import study_agent_acp.agent as agent_module

    def fake_llm(prompt, required_keys=None):
        return LLMCallResult(
            status="schema_mismatch",
            parsed_content={"target_statement": "Target only"},
            parse_stage="chat_completions_content:schema",
            error="missing_required_keys:comparator_statement,outcome_statements,rationale",
            missing_keys=["comparator_statement", "outcome_statements", "rationale"],
            schema_valid=False,
            request_mode="chat_completions",
        )

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)
    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_cohort_methods_intent_split_flow(
        study_intent="Intent text",
    )
    assert result["status"] == "error"
    assert result["error"] == "llm_unavailable"
    assert result["diagnostics"]["llm_missing_keys"] == [
        "comparator_statement",
        "outcome_statements",
        "rationale",
    ]


@pytest.mark.acp
def test_flow_cohort_methods_intent_split_missing_intent():
    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_cohort_methods_intent_split_flow(study_intent="")
    assert result["status"] == "error"
    assert result["error"] == "missing study_intent"


@pytest.mark.acp
def test_flow_cohort_methods_intent_split_prompt_bundle_error():
    class BadMCPClient(StubMCPClient):
        def call_tool(self, name, arguments):
            if name == "cohort_methods_intent_split":
                return {"error": "bad prompt"}
            return super().call_tool(name, arguments)

    agent = StudyAgent(mcp_client=BadMCPClient())
    result = agent.run_cohort_methods_intent_split_flow(
        study_intent="Intent text",
    )
    assert result["status"] == "error"
    assert result["error"] == "cohort_methods_intent_split_prompt_failed"



@pytest.mark.acp
def test_flow_case_causal_review(monkeypatch):
    import study_agent_acp.agent as agent_module

    def fake_llm(prompt, required_keys=None):
        return {
            "candidates_by_domain": {
                "drug_exposures": [
                    {
                        "domain": "drug_exposures",
                        "label": "Warfarin",
                        "source_record_id": "drug-1",
                        "why_it_may_contribute": "Bleeding risk",
                        "confidence": "high",
                        "rank": 1,
                    }
                ]
            },
            "narrative": "Warfarin is a plausible contributor.",
            "mode": "case_causal_review",
            "diagnostics": {},
        }

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)
    agent = StudyAgent(mcp_client=StubMCPClient())
    result = agent.run_case_causal_review_flow(
        adverse_event_name="GI bleed",
        case_row={
            "case_id": "case-1",
            "case_summary": "GI bleed after anticoagulation.",
            "index_event": {"domain": "index_event", "label": "GI bleed", "source_record_id": "reaction-1"},
            "candidate_items": [
                {"domain": "drug_exposures", "label": "Warfarin", "source_record_id": "drug-1", "subrole": "primary_suspect"}
            ],
            "context_items": [],
            "case_metadata": {},
            "annotations": {},
            "tool_hints": {"available_expansions": [], "prefetch_expansions": []}
        },
        source_type="signal_validation",
        allowed_domains=["drug_exposures"],
    )
    assert result["status"] == "ok"
    assert result["flow_name"] == "case_causal_review"
    assert result["candidates_by_domain"]["drug_exposures"][0]["label"] == "Warfarin"


@pytest.mark.acp
def test_route_case_causal_review_wiring(monkeypatch):
    handler = acp_server.ACPRequestHandler.__new__(acp_server.ACPRequestHandler)
    handler.path = "/flows/case_causal_review"
    handler.headers = {}
    handler.debug = False
    handler.wfile = None
    handler.rfile = None
    captured = {}

    class FakeAgent:
        def run_case_causal_review_flow(self, adverse_event_name, case_row, source_type, allowed_domains):
            captured["call"] = {
                "adverse_event_name": adverse_event_name,
                "case_row": case_row,
                "source_type": source_type,
                "allowed_domains": allowed_domains,
            }
            return {
                "status": "ok",
                "flow_name": "case_causal_review",
                "mode": "case_causal_review",
                "candidates_by_domain": {},
                "narrative": "",
                "diagnostics": {},
            }

    handler.agent = FakeAgent()
    handler.mcp_client = None

    body = {
        "adverse_event_name": "GI bleed",
        "case_row": {"case_id": "case-1", "case_summary": "summary", "index_event": {"domain": "index_event", "label": "GI bleed", "source_record_id": "reaction-1"}, "candidate_items": [{"domain": "drug_exposures", "label": "Warfarin", "source_record_id": "drug-1"}], "context_items": [], "case_metadata": {}, "annotations": {}, "tool_hints": {"available_expansions": [], "prefetch_expansions": []}},
        "source_type": "signal_validation",
        "allowed_domains": ["drug_exposures"],
    }

    original_read = acp_server._read_json
    original_write = acp_server._write_json

    def fake_read_json(_handler):
        return body

    def fake_write_json(_handler, status, payload):
        captured["status"] = status
        captured["payload"] = payload

    acp_server._read_json = fake_read_json
    acp_server._write_json = fake_write_json
    try:
        handler.do_POST()
    finally:
        acp_server._read_json = original_read
        acp_server._write_json = original_write

    assert captured["status"] == 200
    assert captured["call"]["source_type"] == "signal_validation"
    assert captured["payload"]["flow_name"] == "case_causal_review"



@pytest.mark.acp
def test_flow_case_causal_review_prefetches_optional_enrichment(monkeypatch):
    import study_agent_acp.agent as agent_module

    def fake_llm(prompt, required_keys=None):
        return {
            "candidates_by_domain": {
                "drug_exposures": [
                    {
                        "domain": "drug_exposures",
                        "label": "Warfarin",
                        "source_record_id": "drug-1",
                        "why_it_may_contribute": "Bleeding risk",
                        "confidence": "high",
                        "rank": 1,
                    }
                ]
            },
            "narrative": "Warfarin is a plausible contributor.",
            "mode": "case_causal_review",
            "diagnostics": {},
        }

    class LabelEnrichmentClient(StubMCPClient):
        def call_tool(self, name, arguments):
            if name == "case_causal_review_sanitize_row":
                self.calls.append((name, arguments))
                return {
                    "sanitized_row": {
                        "case_id": arguments.get("case_row", {}).get("case_id") or "",
                        "case_summary": arguments.get("case_row", {}).get("case_summary") or "",
                        "index_event": arguments.get("case_row", {}).get("index_event") or {},
                        "candidate_items": arguments.get("case_row", {}).get("candidate_items") or [],
                        "candidate_items_by_domain": {
                            "drug_exposures": list(arguments.get("case_row", {}).get("candidate_items") or [])
                        },
                        "context_items": arguments.get("case_row", {}).get("context_items") or [],
                        "context_items_by_domain": {},
                        "case_metadata": arguments.get("case_row", {}).get("case_metadata") or {},
                        "annotations": arguments.get("case_row", {}).get("annotations") or {},
                        "tool_hints": arguments.get("case_row", {}).get("tool_hints") or {},
                    },
                    "diagnostics": {"sanitization_status": "ok"},
                }
            return super().call_tool(name, arguments)

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)
    client = LabelEnrichmentClient()
    agent = StudyAgent(mcp_client=client)
    result = agent.run_case_causal_review_flow(
        adverse_event_name="GI bleed",
        case_row={
            "case_id": "case-1",
            "case_summary": "GI bleed after anticoagulation.",
            "index_event": {
                "domain": "index_event",
                "label": "GI bleed",
                "source_record_id": "reaction-1",
                "annotations": {"adverse_event_concept_id": 321, "adverse_event_meddra_id": "789"},
            },
            "candidate_items": [
                {
                    "domain": "drug_exposures",
                    "label": "Warfarin",
                    "source_record_id": "drug-1",
                    "subrole": "primary_suspect",
                    "annotations": {"ingredient_concept_id": 123, "ingred_rxcui": "456"},
                }
            ],
            "context_items": [],
            "case_metadata": {"literature_reference_present": True, "lookup_key": {"primaryid": None, "isr": "6526923"}},
            "annotations": {"concept_set_available_domains": ["drug_exposures"]},
            "tool_hints": {
                "available_expansions": ["get_case_review_drug_signal_details", "get_case_review_report_literature_stub"],
                "prefetch_expansions": ["get_case_review_drug_signal_details", "get_case_review_report_literature_stub"],
            },
        },
        source_type="signal_validation",
        allowed_domains=["drug_exposures"],
    )
    assert result["status"] == "ok"
    assert result["diagnostics"]["optional_enrichment"]["called"] == [
        "get_case_review_drug_signal_details",
        "get_case_review_report_literature_stub",
    ]
    signal_call = next(arguments for name, arguments in client.calls if name == "get_case_review_drug_signal_details")
    literature_call = next(arguments for name, arguments in client.calls if name == "get_case_review_report_literature_stub")
    assert signal_call["source_record_id"] == "drug-1"
    assert signal_call["adverse_event_concept_id"] == 321
    assert signal_call["ingredient_concept_id"] == 123
    assert signal_call["ingred_rxcui"] == "456"
    assert signal_call["report_lookup_key"] == {"primaryid": None, "isr": "6526923"}
    assert signal_call["adverse_event_meddra_id"] == "789"
    assert literature_call["report_lookup_key"] == {"primaryid": None, "isr": "6526923"}


@pytest.mark.acp
def test_flow_case_causal_review_prefetches_drug_label_details_with_event_identifiers(monkeypatch):
    import study_agent_acp.agent as agent_module

    def fake_llm(prompt, required_keys=None):
        return {
            "candidates_by_domain": {
                "drug_exposures": [
                    {
                        "domain": "drug_exposures",
                        "label": "Warfarin",
                        "source_record_id": "drug-1",
                        "why_it_may_contribute": "Bleeding risk",
                        "confidence": "high",
                        "rank": 1,
                    }
                ]
            },
            "narrative": "Warfarin is a plausible contributor.",
            "mode": "case_causal_review",
            "diagnostics": {},
        }

    class LabelEnrichmentClient(StubMCPClient):
        def call_tool(self, name, arguments):
            if name == "case_causal_review_sanitize_row":
                self.calls.append((name, arguments))
                case_row = arguments.get("case_row", {})
                candidate_items = list(case_row.get("candidate_items") or [])
                context_items = list(case_row.get("context_items") or [])
                candidate_items_by_domain = {}
                for item in candidate_items:
                    candidate_items_by_domain.setdefault(item.get("domain") or "", []).append(item)
                context_items_by_domain = {}
                for item in context_items:
                    context_items_by_domain.setdefault(item.get("domain") or "", []).append(item)
                return {
                    "sanitized_row": {
                        "case_id": case_row.get("case_id") or "",
                        "case_summary": case_row.get("case_summary") or "",
                        "index_event": case_row.get("index_event") or {},
                        "candidate_items": candidate_items,
                        "candidate_items_by_domain": candidate_items_by_domain,
                        "context_items": context_items,
                        "context_items_by_domain": context_items_by_domain,
                        "case_metadata": case_row.get("case_metadata") or {},
                        "annotations": case_row.get("annotations") or {},
                        "tool_hints": case_row.get("tool_hints") or {},
                    },
                    "diagnostics": {"sanitization_status": "ok"},
                }
            return super().call_tool(name, arguments)

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)
    client = LabelEnrichmentClient()
    agent = StudyAgent(mcp_client=client)
    result = agent.run_case_causal_review_flow(
        adverse_event_name="Cystitis",
        case_row={
            "case_id": "6526923-5",
            "case_summary": "Cystitis after exposure.",
            "index_event": {
                "domain": "index_event",
                "label": "Cystitis",
                "source_record_id": "reaction-1",
                "annotations": {"adverse_event_concept_id": 36110716, "adverse_event_meddra_id": "10011781"},
            },
            "candidate_items": [
                {
                    "domain": "drug_exposures",
                    "label": "Nitrofurantoin",
                    "source_record_id": "drug-1",
                    "subrole": "primary_suspect",
                    "annotations": {"ingredient_concept_id": 785649, "ingred_rxcui": "6130"},
                }
            ],
            "context_items": [],
            "case_metadata": {"literature_reference_present": True, "lookup_key": {"primaryid": None, "isr": "6526923"}},
            "annotations": {},
            "tool_hints": {
                "available_expansions": ["get_case_review_drug_label_details"],
                "prefetch_expansions": ["get_case_review_drug_label_details"],
            },
        },
        source_type="signal_validation",
        allowed_domains=["drug_exposures"],
    )
    assert result["status"] == "ok"
    label_call = next(arguments for name, arguments in client.calls if name == "get_case_review_drug_label_details")
    assert label_call["source_type"] == "signal_validation"
    assert label_call["case_id"] == "6526923-5"
    assert label_call["source_record_id"] == "drug-1"
    assert label_call["adverse_event_name"] == "Cystitis"
    assert label_call["adverse_event_concept_id"] == 36110716
    assert label_call["adverse_event_meddra_id"] == "10011781"
    assert label_call["report_lookup_key"] == {"primaryid": None, "isr": "6526923"}
    assert label_call["ingredient_concept_id"] == 785649
    assert label_call["ingred_rxcui"] == "6130"


@pytest.mark.acp
def test_flow_case_causal_review_succeeds_when_optional_enrichment_is_unavailable(monkeypatch):
    import study_agent_acp.agent as agent_module

    class UnavailableEnrichmentClient(StubMCPClient):
        def call_tool(self, name, arguments):
            if name in {
                "get_case_review_drug_signal_details",
                "get_case_review_report_literature_stub",
            }:
                self.calls.append((name, arguments))
                return {"status": "unavailable", "error": "transport_error"}
            return super().call_tool(name, arguments)

    def fake_llm(prompt, required_keys=None):
        return {
            "candidates_by_domain": {
                "drug_exposures": [
                    {
                        "domain": "drug_exposures",
                        "label": "Warfarin",
                        "source_record_id": "drug-1",
                        "why_it_may_contribute": "Bleeding risk",
                        "confidence": "high",
                        "rank": 1,
                    }
                ]
            },
            "narrative": "Warfarin is a plausible contributor.",
            "mode": "case_causal_review",
            "diagnostics": {},
        }

    monkeypatch.setattr(agent_module, "call_llm", fake_llm)
    client = UnavailableEnrichmentClient()
    agent = StudyAgent(mcp_client=client)
    result = agent.run_case_causal_review_flow(
        adverse_event_name="GI bleed",
        case_row={
            "case_id": "case-1",
            "case_summary": "GI bleed after anticoagulation.",
            "index_event": {
                "domain": "index_event",
                "label": "GI bleed",
                "source_record_id": "reaction-1",
                "annotations": {"adverse_event_concept_id": 321, "adverse_event_meddra_id": "789"},
            },
            "candidate_items": [
                {
                    "domain": "drug_exposures",
                    "label": "Warfarin",
                    "source_record_id": "drug-1",
                    "subrole": "primary_suspect",
                    "annotations": {"ingredient_concept_id": 123, "ingred_rxcui": "456"},
                }
            ],
            "context_items": [],
            "case_metadata": {"literature_reference_present": True, "lookup_key": {"primaryid": None, "isr": "6526923"}},
            "annotations": {},
            "tool_hints": {
                "available_expansions": ["get_case_review_drug_signal_details", "get_case_review_report_literature_stub"],
                "prefetch_expansions": ["get_case_review_drug_signal_details", "get_case_review_report_literature_stub"],
            },
        },
        source_type="signal_validation",
        allowed_domains=["drug_exposures"],
    )
    assert result["status"] == "ok"
    assert result["candidates_by_domain"]["drug_exposures"][0]["label"] == "Warfarin"
    assert result["diagnostics"]["optional_enrichment"]["results"]["get_case_review_drug_signal_details"][0]["status"] == "unavailable"
    assert result["diagnostics"]["optional_enrichment"]["results"]["get_case_review_report_literature_stub"]["status"] == "unavailable"
    signal_call = next(arguments for name, arguments in client.calls if name == "get_case_review_drug_signal_details")
    assert signal_call["source_record_id"] == "drug-1"
    assert signal_call["adverse_event_concept_id"] == 321
    assert signal_call["ingredient_concept_id"] == 123
    assert signal_call["ingred_rxcui"] == "456"
    assert signal_call["report_lookup_key"] == {"primaryid": None, "isr": "6526923"}
    assert signal_call["adverse_event_meddra_id"] == "789"
