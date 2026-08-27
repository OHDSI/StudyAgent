import csv
import pytest
from pathlib import Path

from study_agent_acp.llm_client import LLMCallResult
from study_agent_acp.agent import StudyAgent
from study_agent_mcp.tools.phenotype_make_computable_emit import emit_capr
from study_agent_mcp.tools.phenotype_make_computable_validate import _r_library_path, validate_capr_source
from study_agent_mcp.tools.phenotype_make_computable import _load_bundle


class _Mcp:
    def list_tools(self):
        return []

    def call_tool(self, name, arguments):
        if name == "phenotype_make_computable_emit":
            return emit_capr(**arguments)
        if name == "vocab_search_standard":
            return {"concepts": [{"conceptId": 4064161, "conceptName": "Cirrhosis of liver", "domainId": "Condition", "standardConcept": "S"}]}
        if name == "vocab_fetch_concepts":
            return {"concepts": arguments["concepts"], "provider": "db"}
        if name == "vocab_filter_standard_concepts":
            return {"concepts": arguments["concepts"], "count": len(arguments["concepts"]), "provider": "db"}
        if name == "phoebe_related_concepts":
            return {"concepts": [], "count": 0, "provider": "db", "controls": {}}
        if name == "vocab_remove_descendants":
            return {"concepts": arguments["concepts"], "count": len(arguments["concepts"]), "removed_concept_ids": []}
        if name == "phenotype_make_computable_prompt_bundle":
            return _load_bundle()
        if name == "phenotype_make_computable_validate":
            return validate_capr_source(**arguments)
        raise AssertionError(name)


def _concept_sets(case_id: str):
    path = Path("sandbox/reference_set/training_cohorts") / case_id / "concept_roots.csv"
    grouped = {}
    for row in csv.DictReader(path.open(encoding="utf-8")):
        grouped.setdefault(row["concept_set_name"], {"name": row["concept_set_name"], "domain": row["domain_id"], "concept_ids": []})["concept_ids"].append(int(row["concept_id"]))
    return list(grouped.values())


def _policy_concept_sets(case_id: str):
    path = Path("sandbox/reference_set/training_cohorts") / case_id / "concept_roots.csv"
    grouped = {}
    for row in csv.DictReader(path.open(encoding="utf-8")):
        item = grouped.setdefault(row["concept_set_name"], {"name": row["concept_set_name"], "domain": row["domain_id"], "items": []})
        item["items"].append({"concept_id": int(row["concept_id"]), "domain": row["domain_id"], "include_descendants": row["include_descendants"].lower() == "true", "include_mapped": row["include_mapped"].lower() == "true", "is_excluded": row["is_excluded"].lower() == "true"})
    return list(grouped.values())


def test_unconfirmed_request_needs_clarification():
    result = StudyAgent().run_phenotype_make_computable_flow("earliest cirrhosis")
    assert result["status"] == "needs_clarification"
    assert "index_event" in result["missing_scope_fields"]


def test_710_simple_condition_fixture():
    emitted = emit_capr({"index_event": "Cirrhosis", "entry_limit": "First", "exit_strategy": "observation"}, _policy_concept_sets("710"))
    validated = validate_capr_source(emitted["capr_code"])
    assert validated["status"] == "passed"
    circe = validated["circe_json"]
    environment = validated["r_environment"]
    assert environment["r_version"]
    assert environment["validation_packages"]["Capr"] != "not_installed"
    assert environment["validation_packages"]["CirceR"] != "not_installed"
    assert len(circe["ConceptSets"]) == 1
    assert circe["PrimaryCriteria"]["PrimaryCriteriaLimit"]["Type"] == "First"
    assert "EndStrategy" not in circe


def test_222_visit_overlap_fixture():
    emitted = emit_capr({"index_event": "SJS/TEN", "entry_limit": "All", "visit_overlap": True, "visit_overlap_mode": "entry", "exit_strategy": {"type": "fixed", "offset_days": 1}}, _policy_concept_sets("222"))
    validated = validate_capr_source(emitted["capr_code"])
    assert validated["status"] == "passed"
    circe = validated["circe_json"]
    assert len(circe["ConceptSets"]) == 2
    assert circe["PrimaryCriteria"]["PrimaryCriteriaLimit"]["Type"] == "All"
    assert circe["EndStrategy"]["DateOffset"]["Offset"] == 1
    assert len(circe["InclusionRules"]) == 0


def test_confirmed_provided_concept_set_returns_validated_artifacts():
    scope = {"index_event": "Cirrhosis", "criterion_domains": {"Cirrhosis": "Condition"}, "entry_limit": "First", "prior_observation": "0", "index_day_boundary": "included", "windows": "none", "exit_strategy": "observation"}
    result = StudyAgent(mcp_client=_Mcp()).run_phenotype_make_computable_flow("earliest cirrhosis", True, scope, "provided_only", _concept_sets("710"))
    assert result["status"] == "ok"
    assert result["validation"]["status"] == "passed"
    assert isinstance(result["circe_json"], dict)
    assert result["capr"]["filename"] == "phenotype_definition.R"
    assert result["capr"]["entry_point"] == "phenotype_make_computable_definition"


class _VisitUnionMcp(_Mcp):
    def call_tool(self, name, arguments):
        if name == "vocab_search_standard":
            query = arguments["query"]
            rows = {
                "Stevens-Johnson syndrome, Toxic epidermal necrolysis spectrum": [{"conceptId": 35625857, "conceptName": "SJS/TEN", "domainId": "Condition", "standardConcept": "S"}],
                "Emergency room or Inpatient Visit": [],
                "Emergency room": [
                    {"conceptId": 262, "conceptName": "Emergency Room and Inpatient Visit", "domainId": "Visit", "standardConcept": "S"},
                    {"conceptId": 9203, "conceptName": "Emergency Room Visit", "domainId": "Visit", "standardConcept": "S"},
                ],
                "Inpatient Visit": [
                    {"conceptId": 262, "conceptName": "Emergency Room and Inpatient Visit", "domainId": "Visit", "standardConcept": "S"},
                    {"conceptId": 9201, "conceptName": "Inpatient Visit", "domainId": "Visit", "standardConcept": "S"},
                ],
            }[query]
            return {"concepts": rows}
        return super().call_tool(name, arguments)


def test_visit_or_criterion_expands_to_named_union_lane():
    scope = {
        "index_event": "Stevens-Johnson syndrome, Toxic epidermal necrolysis spectrum",
        "criterion_domains": {
            "Stevens-Johnson syndrome, Toxic epidermal necrolysis spectrum": "Condition",
            "Emergency room or Inpatient Visit": "Visit",
        },
    }
    candidates, provenance, _ = StudyAgent(mcp_client=_VisitUnionMcp())._retrieve_phenotype_concept_lanes(scope)
    visit_rows = [row for row in candidates if row["conceptSetName"] == "Emergency room or Inpatient Visit"]
    assert {row["conceptId"] for row in visit_rows} == {262, 9201, 9203}
    assert {row["sourceTerm"] for row in visit_rows} >= {"Emergency room", "Inpatient Visit"}
    visit_runs = [run for run in provenance["search_runs"] if run["concept_set_name"] == "Emergency room or Inpatient Visit"]
    assert [run["query"] for run in visit_runs] == ["Emergency room or Inpatient Visit", "Emergency room", "Inpatient Visit"]


def test_required_concept_review_returns_vocab_candidates():
    scope = {"index_event": "Cirrhosis", "criterion_domains": {"Cirrhosis": "Condition"}, "entry_limit": "First", "prior_observation": "0", "index_day_boundary": "included", "windows": "none", "exit_strategy": "observation"}
    result = StudyAgent(mcp_client=_Mcp()).run_phenotype_make_computable_flow("earliest cirrhosis", True, scope)
    assert result["status"] == "needs_concept_review"
    assert result["concept_candidates"][0]["conceptId"] == 4064161
    assert result["concept_provenance"]["tool"] == "vocab_search_standard"


def test_required_drug_concept_review_uses_drug_lane_and_fixed_exit():
    class DrugMcp(_Mcp):
        def call_tool(self, name, arguments):
            if name == "vocab_search_standard":
                assert arguments == {"query": "Warfarin", "domains": ["Drug"], "vocabulary_ids": ["RxNorm"], "limit": 20}
                return {
                    "concepts": [{
                        "conceptId": 1310149,
                        "conceptName": "Warfarin",
                        "domainId": "Drug",
                        "standardConcept": "S",
                    }],
                    "returned_count": 1,
                    "matched_count": 5652,
                    "matched_count_status": "exact",
                    "limit": 20,
                    "truncated": True,
                    "ordering": "concept_name_ascending",
                    "vocabulary_filter_status": "database_filter",
                }
            return super().call_tool(name, arguments)

    scope = {
        "index_event": "Warfarin",
        "criterion_domains": {"Warfarin": "Drug"},
        "criterion_vocabularies": {"Warfarin": ["RxNorm"]},
        "entry_limit": "First",
        "prior_observation": 365,
        "index_day_boundary": "included",
        "windows": "none",
        "exit_strategy": {"type": "fixed", "index": "endDate", "offset_days": 30},
        "visit_overlap": False,
    }
    result = StudyAgent(mcp_client=DrugMcp()).run_phenotype_make_computable_flow(
        "Earliest exposure to warfarin.", True, scope, "required", review_delivery="inline"
    )
    assert result["status"] == "needs_concept_review"
    assert result["review_delivery"] == "inline"
    assert result["candidate_count"] == 1
    assert result["concept_candidates"][0]["conceptSetName"] == "Warfarin"
    assert result["concept_candidates"][0]["domainId"] == "Drug"
    assert result["scope"]["exit_strategy"] == {"type": "fixed", "index": "endDate", "offset_days": 30}
    assert result["concept_provenance"]["truncated"] is True
    assert result["concept_provenance"]["search_runs"][0]["matched_count"] == 5652
    assert result["concept_provenance"]["search_runs"][0]["vocabulary_ids"] == ["RxNorm"]
    assert result["concept_provenance"]["search_runs"][0]["vocabulary_filter_status"] == "database_filter"
    assert result["concept_provenance"]["large_result_guidance"]["lanes"] == [
        {"concept_set_name": "Warfarin", "matched_count": 5652, "returned_count": 1}
    ]


def test_propose_mode_returns_llm_plan_for_review():
    scope = {"index_event": "Cirrhosis", "criterion_domains": {"Cirrhosis": "Condition"}, "entry_limit": "First", "prior_observation": "0", "index_day_boundary": "included", "windows": "none", "exit_strategy": "observation"}
    agent = StudyAgent(mcp_client=_Mcp())
    agent._call_llm = lambda prompt, required_keys: LLMCallResult(status="ok", parsed_content={"status": "needs_clarification", "scope_check": {}, "candidate_assessments": [{"concept_id": 4064161, "precision_eligible": True, "rationale": "matches the confirmed index event"}], "concept_sets": [], "cohort_plan": {}, "assumptions": [], "warnings": []})
    result = agent.run_phenotype_make_computable_flow("earliest cirrhosis", True, scope, "propose")
    assert result["status"] == "needs_concept_review"
    assert result["llm_status"] == "ok"
    assert result["proposed_plan"]["status"] == "needs_clarification"
    assert result["concept_provenance"] == {
        "tool": "vocab_search_standard",
        "query": "Cirrhosis",
        "domains": ["Condition"],
        "tool_status": "ok",
        "metadata_tool": "vocab_fetch_concepts",
        "metadata_status": "ok",
    }


def test_propose_response_omits_verbose_raw_llm_payload(monkeypatch):
    monkeypatch.setenv("LLM_LOG_RESPONSE", "1")
    scope = {"index_event": "Cirrhosis", "criterion_domains": {"Cirrhosis": "Condition"}, "entry_limit": "First", "prior_observation": "0", "index_day_boundary": "included", "windows": "none", "exit_strategy": "observation"}
    agent = StudyAgent(mcp_client=_Mcp())
    agent._call_llm = lambda prompt, required_keys: LLMCallResult(
        status="ok",
        content_text='{"large": "raw model output"}',
        raw_response={"content": "raw model output"},
        parsed_content={"status": "ok", "scope_check": {}, "candidate_assessments": [{"concept_id": 4064161, "precision_eligible": True, "rationale": "matches"}], "concept_sets": [], "cohort_plan": {}, "assumptions": [], "warnings": []},
    )

    result = agent.run_phenotype_make_computable_flow("earliest cirrhosis", True, scope, "propose")

    assert result["status"] == "needs_concept_review"
    assert "llm_content_text" not in result["diagnostics"]
    assert "llm_raw_response" not in result["diagnostics"]


def test_session_delivery_keeps_large_review_rows_out_of_initial_response():
    scope = {"index_event": "Cirrhosis", "criterion_domains": {"Cirrhosis": "Condition"}, "entry_limit": "First", "prior_observation": 0, "index_day_boundary": "included", "windows": "none", "exit_strategy": "observation"}
    agent = StudyAgent(mcp_client=_Mcp())
    agent._call_llm = lambda prompt, required_keys: LLMCallResult(
        status="ok",
        parsed_content={"status": "ok", "scope_check": {}, "candidate_assessments": [{"concept_id": 4064161, "precision_eligible": True, "rationale": "matches"}], "concept_sets": [], "cohort_plan": {}, "assumptions": [], "warnings": []},
    )

    result = agent.run_phenotype_make_computable_flow(
        "earliest cirrhosis", True, scope, "propose", review_delivery="session"
    )

    assert result["review_delivery"] == "session"
    assert result["candidate_count"] == 1
    assert result["assessment_count"] == 1
    assert result["proposed_plan_present"] is True
    assert "concept_candidates" not in result
    assert "proposed_plan" not in result
    review_id = result["review_id"]
    page = agent.get_phenotype_review_candidates(review_id, offset=0, limit=1)
    assert page["total"] == 1
    assert page["candidates"][0]["conceptId"] == 4064161
    csv_text = agent.get_phenotype_review_csv(review_id)
    assert "assessment_status" in csv_text
    assert "proposed_include_concept" in csv_text
    assert "review_exclude_concepts" in csv_text
    assert "Cirrhosis of liver" in csv_text
    manifest = agent.get_phenotype_review_manifest(review_id)
    assert manifest["scope"]["index_event"] == "Cirrhosis"
    assert "T" in manifest["review_expires_at"]


def test_grounded_propose_mode_uses_terms_and_rejects_invented_concepts():
    scope = {"index_event": "Cirrhosis", "criterion_domains": {"Cirrhosis": "Condition"}, "entry_limit": "First", "prior_observation": 0, "index_day_boundary": "included", "windows": "none", "exit_strategy": "observation"}
    agent = StudyAgent(mcp_client=_Mcp())
    responses = iter([
        LLMCallResult(status="ok", parsed_content={"terms": ["Cirrhosis", "Hepatic cirrhosis"]}),
        LLMCallResult(status="ok", parsed_content={"status": "ok", "scope_check": {}, "candidate_assessments": [{"concept_id": 4064161, "precision_eligible": True, "rationale": "matches the confirmed index event"}], "concept_sets": [{"name": "Cirrhosis", "domain": "Condition", "items": [{"concept_id": 9999999, "domain": "Condition", "include_descendants": False, "include_mapped": False, "is_excluded": False}]}], "cohort_plan": {"mode": "condition_entry", "entry_limit": "First", "prior_observation_days": 0, "exit_strategy": "observation", "era_days": 0}, "assumptions": [], "warnings": []}),
    ])
    agent._call_llm = lambda prompt, required_keys: next(responses)
    result = agent.run_phenotype_make_computable_flow("earliest cirrhosis", True, scope, "propose", concept_build_mode="grounded")
    assert result["status"] == "unavailable"
    assert result["concept_build"]["mode"] == "grounded"
    assert result["concept_provenance"]["search_terms"] == ["Cirrhosis", "Hepatic cirrhosis"]
    assert result["proposal_validation_errors"][0]["msg"] == "proposed_concept_not_in_grounded_candidates"



class _RelationshipMcp(_Mcp):
    def call_tool(self, name, arguments):
        if name == "vocab_search_standard":
            return {"concepts": [{"conceptId": 1, "conceptName": "Parent condition", "domainId": "Condition", "standardConcept": "S"}]}
        if name == "phoebe_related_concepts":
            return {
                "concepts": [{
                    "conceptId": 2,
                    "conceptName": "Child condition",
                    "domainId": "Condition",
                    "standardConcept": "S",
                    "relationshipId": "Ontology-descendant",
                    "sourceConceptId": 1,
                }],
                "count": 1,
                "provider": "db",
                "controls": {"applied_relationship_ids": ["Ontology-descendant"]},
            }
        if name == "vocab_remove_descendants":
            ids = {row["conceptId"] for row in arguments["concepts"]}
            return {
                "concepts": [row for row in arguments["concepts"] if row["conceptId"] != 2],
                "count": len(arguments["concepts"]) - (1 if {1, 2}.issubset(ids) else 0),
                "removed_concept_ids": [2] if {1, 2}.issubset(ids) else [],
            }
        return super().call_tool(name, arguments)


def test_grounded_propose_rejects_redundant_descendant_covered_by_included_ancestor():
    scope = {"index_event": "Parent condition", "criterion_domains": {"Parent condition": "Condition"}, "entry_limit": "First", "prior_observation": 0, "index_day_boundary": "included", "windows": "none", "exit_strategy": "observation"}
    agent = StudyAgent(mcp_client=_RelationshipMcp())
    responses = iter([
        LLMCallResult(status="ok", parsed_content={"terms": ["Parent condition"]}),
        LLMCallResult(status="ok", parsed_content={
            "status": "ok",
            "scope_check": {},
            "candidate_assessments": [
                {"concept_id": 1, "precision_eligible": True, "rationale": "parent matches"},
                {"concept_id": 2, "precision_eligible": True, "rationale": "child matches"},
            ],
            "concept_sets": [{"name": "Parent", "domain": "Condition", "items": [
                {"concept_id": 1, "domain": "Condition", "include_descendants": True, "include_mapped": False, "is_excluded": False},
                {"concept_id": 2, "domain": "Condition", "include_descendants": False, "include_mapped": False, "is_excluded": False},
            ]}],
            "cohort_plan": {"mode": "condition_entry", "entry_limit": "First", "prior_observation_days": 0, "exit_strategy": "observation", "era_days": 0},
            "assumptions": [],
            "warnings": [],
        }),
    ])
    agent._call_llm = lambda prompt, required_keys: next(responses)

    result = agent.run_phenotype_make_computable_flow("earliest parent condition", True, scope, "propose", concept_build_mode="grounded")

    assert result["status"] == "needs_concept_review"
    assert result["proposal_validation_status"] == "passed"
    assert result["concept_provenance"]["relationship_expansion"]["related_candidate_count"] == 1
    assert {row["conceptId"] for row in result["concept_candidates"]} == {1, 2}
    assert any(advisory["msg"] == "explicit_child_covered_by_included_ancestor" for advisory in result["proposal_advisories"])
    assert not result["proposal_validation_errors"]


def test_grounded_propose_allows_ineligible_descendant_as_explicit_exclusion():
    scope = {"index_event": "Parent condition", "criterion_domains": {"Parent condition": "Condition"}, "entry_limit": "First", "prior_observation": 0, "index_day_boundary": "included", "windows": "none", "exit_strategy": "observation"}
    agent = StudyAgent(mcp_client=_RelationshipMcp())
    responses = iter([
        LLMCallResult(status="ok", parsed_content={"terms": ["Parent condition"]}),
        LLMCallResult(status="ok", parsed_content={
            "status": "ok",
            "scope_check": {},
            "candidate_assessments": [
                {"concept_id": 1, "precision_eligible": True, "rationale": "parent matches"},
                {"concept_id": 2, "precision_eligible": False, "rationale": "child must be excluded"},
            ],
            "concept_sets": [{"name": "Parent", "domain": "Condition", "items": [
                {"concept_id": 1, "domain": "Condition", "include_descendants": True, "include_mapped": False, "is_excluded": False},
                {"concept_id": 2, "domain": "Condition", "include_descendants": False, "include_mapped": False, "is_excluded": True},
            ]}],
            "cohort_plan": {"mode": "condition_entry", "entry_limit": "First", "prior_observation_days": 0, "exit_strategy": "observation", "era_days": 0},
            "assumptions": [],
            "warnings": [],
        }),
    ])
    agent._call_llm = lambda prompt, required_keys: next(responses)

    result = agent.run_phenotype_make_computable_flow("earliest parent condition", True, scope, "propose", concept_build_mode="grounded")

    assert result["status"] == "needs_concept_review"
    assert result["proposed_plan"]["concept_sets"][0]["items"][1]["is_excluded"] is True

def test_prompt_contract_requires_policy_bearing_reviewed_concept_items():
    bundle = _load_bundle()
    concept_set = bundle["output_schema"]["properties"]["concept_sets"]["items"]
    item = concept_set["properties"]["items"]["items"]
    assert concept_set["required"] == ["name", "domain", "items"]
    assert item["required"] == ["concept_id", "domain", "include_descendants", "include_mapped", "is_excluded"]


def test_propose_mode_rejects_a_plan_with_an_unsupported_exit_strategy():
    scope = {"index_event": "Cirrhosis", "criterion_domains": {"Cirrhosis": "Condition"}, "entry_limit": "First", "prior_observation": 0, "index_day_boundary": "included", "windows": "none", "exit_strategy": "observation"}
    agent = StudyAgent(mcp_client=_Mcp())
    agent._call_llm = lambda prompt, required_keys: LLMCallResult(status="ok", parsed_content={"status": "ok", "scope_check": {}, "candidate_assessments": [{"concept_id": 4064161, "precision_eligible": True, "rationale": "matches the confirmed index event"}], "concept_sets": [], "cohort_plan": {"exit_strategy": {"type": "observation_end"}}, "assumptions": [], "warnings": []})
    result = agent.run_phenotype_make_computable_flow("earliest cirrhosis", True, scope, "propose")
    assert result["status"] == "unavailable"
    assert result["proposed_plan"] is None
    assert result["proposal_validation_errors"]


def test_validator_prefers_explicit_r_library_environment(monkeypatch):
    monkeypatch.setenv("R_LIBS_USER", "/configured/r/library")
    assert _r_library_path() == "/configured/r/library"


def test_validator_rejects_indirect_process_execution():
    result = validate_capr_source("base::system('echo unsafe')")
    assert result["status"] == "failed"
    assert "system" in result["messages"][0]


def test_concept_set_policy_is_preserved_from_reviewed_items():
    emitted = emit_capr({"index_event": "Cirrhosis", "entry_limit": "First", "exit_strategy": "observation"}, _policy_concept_sets("710"))
    circe = validate_capr_source(emitted["capr_code"])["circe_json"]
    assert all(item["includeDescendants"] for item in circe["ConceptSets"][0]["expression"]["items"])
    assert not any(item["includeMapped"] for item in circe["ConceptSets"][0]["expression"]["items"])


def test_supported_training_cases_compile_with_reviewed_policies():
    cases = [
        ("710", {"index_event": "Cirrhosis", "entry_limit": "First", "exit_strategy": "observation"}),
        ("794", {"index_event": "Digestive hemorrhage", "entry_limit": "All", "exit_strategy": {"type": "fixed", "offset_days": 14}}),
        ("743", {"index_event": "Diabetic ketoacidosis", "entry_limit": "All", "visit_overlap": True, "visit_overlap_mode": "entry", "exit_strategy": {"type": "fixed", "offset_days": 30}}),
        ("222", {"index_event": "SJS/TEN", "entry_limit": "All", "visit_overlap": True, "visit_overlap_mode": "attrition", "exit_strategy": {"type": "fixed", "offset_days": 1}}),
        ("1340", {"index_event": "Anorexia nervosa", "entry_limit": "All", "exit_strategy": {"type": "fixed", "offset_days": 30}, "era_days": 365}),
        ("1341", {"index_event": "Eating disorders", "entry_limit": "All", "exit_strategy": {"type": "fixed", "offset_days": 30}, "era_days": 365}),
        ("1345", {"index_event": "Personality disorders", "entry_limit": "All", "exit_strategy": {"type": "fixed", "offset_days": 30}, "era_days": 365}),
        ("1346", {"index_event": "ADHD", "entry_limit": "All", "exit_strategy": {"type": "fixed", "offset_days": 30}, "era_days": 365}),
        ("1347", {"index_event": "PTSD", "entry_limit": "All", "exit_strategy": {"type": "fixed", "offset_days": 30}, "era_days": 365}),
    ]
    for case_id, scope in cases:
        emitted = emit_capr(scope, _policy_concept_sets(case_id))
        assert emitted["status"] == "passed", case_id
        assert validate_capr_source(emitted["capr_code"])["status"] == "passed", case_id



def test_emitted_capr_is_a_pure_function_artifact():
    emitted = emit_capr({"index_event": "Cirrhosis", "entry_limit": "First", "exit_strategy": "observation"}, _policy_concept_sets("710"))
    assert emitted["entry_point"] == "phenotype_make_computable_definition"
    assert "phenotype_make_computable_definition <- function()" in emitted["capr_code"]
    assert "writeCohort" not in emitted["capr_code"]
def test_era_days_becomes_circe_collapse_settings():
    emitted = emit_capr({"index_event": "Anorexia", "entry_limit": "All", "exit_strategy": {"type": "fixed", "offset_days": 30}, "era_days": 365}, _policy_concept_sets("1340"))
    circe = validate_capr_source(emitted["capr_code"])["circe_json"]
    assert circe["CollapseSettings"] == {"CollapseType": "ERA", "EraPad": 365}


@pytest.mark.parametrize(("domain", "constructor", "circe_key"), [
    ("Drug", "drugExposure", "DrugExposure"),
    ("Procedure", "procedure", "ProcedureOccurrence"),
    ("Measurement", "measurement", "Measurement"),
    ("Observation", "observation", "Observation"),
    ("Visit", "visit", "VisitOccurrence"),
    ("Device", "deviceExposure", "DeviceExposure"),
])
def test_supported_noncondition_direct_entry_domains_compile(domain, constructor, circe_key):
    emitted = emit_capr(
        {"index_event": f"{domain} event", "entry_limit": "First", "exit_strategy": "observation"},
        [{"name": f"{domain} entry", "domain": domain, "items": [{"concept_id": 1, "domain": domain, "include_descendants": False, "include_mapped": False, "is_excluded": False}]}],
    )
    assert emitted["status"] == "passed"
    assert f"Capr::{constructor}(entryCs)" in emitted["capr_code"]
    circe = validate_capr_source(emitted["capr_code"])["circe_json"]
    assert circe["PrimaryCriteria"]["CriteriaList"] == [{circe_key: {"CodesetId": 0}}]


def test_unsupported_direct_entry_domain_fails_closed():
    emitted = emit_capr(
        {"index_event": "Death", "entry_limit": "First", "exit_strategy": "observation"},
        [{"name": "Death", "domain": "Death", "items": [{"concept_id": 1, "domain": "Death", "include_descendants": False, "include_mapped": False, "is_excluded": False}]}],
    )
    assert emitted["messages"] == ["unsupported_direct_entry_domain"]


def test_mixed_domain_concept_set_fails_closed():
    emitted = emit_capr({"index_event": "Rheumatoid arthritis", "entry_limit": "First", "exit_strategy": "observation"}, _policy_concept_sets("858"))
    assert emitted["status"] == "failed"
    assert emitted["messages"] == ["mixed_domain_concept_set_requires_explicit_multi_domain_plan"]


def test_mixed_domain_concept_set_returns_clarification_card_before_emission():
    scope = {"index_event": "Rheumatoid arthritis", "criterion_domains": {"Rheumatoid arthritis": "Condition or Observation"}, "entry_limit": "First", "prior_observation": "0", "index_day_boundary": "included", "windows": "none", "exit_strategy": "observation"}
    result = StudyAgent(mcp_client=_Mcp()).run_phenotype_make_computable_flow("Earliest rheumatoid arthritis diagnosis by condition or observation date.", True, scope, "provided_only", _policy_concept_sets("858"))
    assert result["status"] == "needs_clarification"
    assert result["clarification_type"] == "mixed_domain_entry"
    assert result["detected_concept_sets"][0]["domains"] == ["Condition", "Observation"]
    assert result["clarification_provenance"]["detected_from"] == "reviewed_concept_sets"


def test_confirmed_condition_or_observation_entry_compiles_for_858():
    scope = {
        "index_event": "Rheumatoid arthritis",
        "criterion_domains": {"Rheumatoid arthritis": "Condition or Observation"},
        "entry_limit": "First",
        "prior_observation": 0,
        "index_day_boundary": "included",
        "windows": "none",
        "exit_strategy": "observation",
        "multi_domain_entry_policy": "any_qualifying_domain",
    }
    result = StudyAgent(mcp_client=_Mcp()).run_phenotype_make_computable_flow(
        "Earliest rheumatoid arthritis diagnosis by condition or observation date.",
        True,
        scope,
        "provided_only",
        _policy_concept_sets("858"),
    )
    assert result["status"] == "ok"
    criteria = result["circe_json"]["PrimaryCriteria"]["CriteriaList"]
    assert {next(iter(item)) for item in criteria} == {"ConditionOccurrence", "Observation"}
    assert result["circe_json"]["PrimaryCriteria"]["PrimaryCriteriaLimit"] == {"Type": "First"}


def test_mixed_domain_policy_fails_closed_for_unsupported_domain_combinations():
    emitted = emit_capr(
        {"index_event": "Mixed", "entry_limit": "First", "exit_strategy": "observation", "multi_domain_entry_policy": "any_qualifying_domain"},
        [{"name": "Mixed", "items": [
            {"concept_id": 1, "domain": "Condition", "include_descendants": False, "include_mapped": False, "is_excluded": False},
            {"concept_id": 2, "domain": "Drug", "include_descendants": False, "include_mapped": False, "is_excluded": False},
        ]}],
    )
    assert emitted["messages"] == ["mixed_domain_concept_set_requires_explicit_multi_domain_plan"]


def test_temporal_followup_with_continuous_observation_compiles():
    scope = {"index_event": "Transverse myelitis", "entry_limit": "All", "exit_strategy": {"type": "fixed", "index": "startDate", "offset_days": 1}, "temporal_followup": {"index_concept_set": "Transverse Myelitis", "trigger_concept_set": "Symptoms for Transverse Myelitis", "followup_days": 30, "washout_days": 365}}
    emitted = emit_capr(scope, _policy_concept_sets("63"))
    circe = validate_capr_source(emitted["capr_code"])["circe_json"]
    assert circe["PrimaryCriteria"]["ObservationWindow"] == {"PriorDays": 365, "PostDays": 0}
    assert circe["EndStrategy"]["DateOffset"] == {"DateField": "StartDate", "Offset": 1}
    assert len(circe["InclusionRules"]) == 1
    assert circe["PrimaryCriteria"]["ObservationWindow"] == {"PriorDays": 365, "PostDays": 0}


def test_single_condition_prior_observation_scope_is_preserved_in_circe():
    emitted = emit_capr({"index_event": "Cirrhosis", "entry_limit": "First", "prior_observation": 365, "exit_strategy": "observation"}, _policy_concept_sets("710"))
    circe = validate_capr_source(emitted["capr_code"])["circe_json"]
    assert circe["PrimaryCriteria"]["ObservationWindow"] == {"PriorDays": 365, "PostDays": 0}


def test_visit_overlap_requires_explicit_mode_before_emission():
    scope = {
        "index_event": "SJS/TEN",
        "criterion_domains": {"SJS/TEN": "Condition", "Emergency room or Inpatient Visit": "Visit"},
        "entry_limit": "First",
        "prior_observation": 0,
        "index_day_boundary": "included",
        "windows": "none",
        "exit_strategy": {"type": "fixed", "offset_days": 1},
        "visit_overlap": True,
    }
    result = StudyAgent(mcp_client=_Mcp()).run_phenotype_make_computable_flow(
        "SJS/TEN with visit overlap", True, scope, "provided_only", _policy_concept_sets("222")
    )
    assert result["status"] == "needs_clarification"
    assert result["missing_scope_fields"] == ["visit_overlap_mode"]
    assert emit_capr({"index_event": "SJS/TEN", "entry_limit": "First", "visit_overlap": True, "exit_strategy": {"type": "fixed", "offset_days": 1}}, _policy_concept_sets("222"))["status"] == "failed"


def test_visit_overlap_prior_observation_scope_is_preserved_in_circe():
    scope = {"index_event": "SJS/TEN", "entry_limit": "All", "prior_observation": 365, "visit_overlap": True, "visit_overlap_mode": "entry", "exit_strategy": {"type": "fixed", "offset_days": 1}}
    emitted = emit_capr(scope, _policy_concept_sets("222"))
    circe = validate_capr_source(emitted["capr_code"])["circe_json"]
    assert circe["PrimaryCriteria"]["ObservationWindow"] == {"PriorDays": 365, "PostDays": 0}


def test_temporal_followup_rejects_inconsistent_prior_observation():
    scope = {"index_event": "Transverse myelitis", "entry_limit": "All", "prior_observation": 0, "temporal_followup": {"index_concept_set": "Transverse Myelitis", "trigger_concept_set": "Symptoms for Transverse Myelitis", "followup_days": 30, "washout_days": 365}}
    result = emit_capr(scope, _policy_concept_sets("63"))
    assert result["messages"] == ["temporal_followup_prior_observation_must_equal_washout_days"]


def test_invalid_declared_scope_is_returned_as_clarification_before_emission():
    result = StudyAgent(mcp_client=_Mcp()).run_phenotype_make_computable_flow(
        "earliest cirrhosis",
        True,
        {"index_event": "Cirrhosis", "entry_limit": "Earliest", "exit_strategy": "observation"},
        "provided_only",
        _policy_concept_sets("710"),
    )
    assert result["status"] == "needs_clarification"
    assert result["clarification_type"] == "invalid_scope"
    assert result["scope_errors"][0]["loc"] == ("scope", "entry_limit")


def test_scope_rejects_undeclared_semantics_before_emission():
    result = StudyAgent(mcp_client=_Mcp()).run_phenotype_make_computable_flow(
        "earliest cirrhosis",
        True,
        {"index_event": "Cirrhosis", "entry_limit": "First", "exit_strategy": "observation", "drug_era": {"days": 30}},
        "provided_only",
        _policy_concept_sets("710"),
    )
    assert result["status"] == "needs_clarification"
    assert result["clarification_type"] == "invalid_scope"
    assert result["scope_errors"][0]["type"] == "extra_forbidden"


def test_concept_set_input_normalizes_ohdsi_aliases_before_emission():
    scope = {"index_event": "Cirrhosis", "criterion_domains": {"Cirrhosis": "Condition"}, "entry_limit": "First", "prior_observation": 0, "index_day_boundary": "included", "windows": "none", "exit_strategy": "observation"}
    concept_sets = [{"name": "Cirrhosis", "domainId": "Condition", "concepts": [{"conceptId": 4064161, "domainId": "Condition", "includeDescendants": True, "includeMapped": False, "isExcluded": False}]}]
    result = StudyAgent(mcp_client=_Mcp()).run_phenotype_make_computable_flow("earliest cirrhosis", True, scope, "provided_only", concept_sets)
    assert result["status"] == "ok"
    assert result["circe_json"]["ConceptSets"][0]["expression"]["items"][0]["includeDescendants"] is True


def test_single_item_domain_is_inferred_when_set_domain_is_omitted():
    emitted = emit_capr(
        {"index_event": "Cirrhosis", "entry_limit": "First", "exit_strategy": "observation"},
        [{"name": "Cirrhosis", "items": [{"concept_id": 4064161, "domain": "Condition", "include_descendants": False, "include_mapped": False, "is_excluded": False}]}],
    )
    assert emitted["status"] == "passed"


def test_invalid_reviewed_concept_set_returns_clarification_before_emission():
    scope = {"index_event": "Cirrhosis", "criterion_domains": {"Cirrhosis": "Condition"}, "entry_limit": "First", "prior_observation": 0, "index_day_boundary": "included", "windows": "none", "exit_strategy": "observation"}
    result = StudyAgent(mcp_client=_Mcp()).run_phenotype_make_computable_flow("earliest cirrhosis", True, scope, "provided_only", [{"name": "Cirrhosis", "domain": "Condition", "items": [{"concept_id": "not-an-id"}]}])
    assert result["status"] == "needs_clarification"
    assert result["clarification_type"] == "invalid_concept_sets"
    assert result["concept_set_errors"][0]["loc"] == ("concept_sets", 0, "items", 0, "concept_id")


def test_unsupported_scope_semantics_fail_closed():
    concepts = _policy_concept_sets("710")
    boundary = emit_capr({"index_event": "Cirrhosis", "entry_limit": "First", "index_day_boundary": "excluded", "exit_strategy": "observation"}, concepts)
    windows = emit_capr({"index_event": "Cirrhosis", "entry_limit": "First", "windows": {"start": -30, "end": 0}, "exit_strategy": "observation"}, concepts)
    assert boundary["messages"] == ["unsupported_index_day_boundary"]
    assert windows["messages"] == ["unsupported_temporal_windows_require_explicit_emitter_mode"]
