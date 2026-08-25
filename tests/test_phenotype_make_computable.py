import csv
from pathlib import Path

from study_agent_acp.llm_client import LLMCallResult
from study_agent_acp.agent import StudyAgent
from study_agent_mcp.tools.phenotype_make_computable_emit import emit_capr
from study_agent_mcp.tools.phenotype_make_computable_validate import validate_capr_source
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
    assert len(circe["ConceptSets"]) == 1
    assert circe["PrimaryCriteria"]["PrimaryCriteriaLimit"]["Type"] == "First"
    assert "EndStrategy" not in circe


def test_222_visit_overlap_fixture():
    emitted = emit_capr({"index_event": "SJS/TEN", "entry_limit": "All", "visit_overlap": True, "exit_strategy": {"type": "fixed", "offset_days": 1}}, _policy_concept_sets("222"))
    validated = validate_capr_source(emitted["capr_code"])
    assert validated["status"] == "passed"
    circe = validated["circe_json"]
    assert len(circe["ConceptSets"]) == 2
    assert circe["PrimaryCriteria"]["PrimaryCriteriaLimit"]["Type"] == "All"
    assert circe["EndStrategy"]["DateOffset"]["Offset"] == 1
    assert len(circe["InclusionRules"]) == 1


def test_confirmed_provided_concept_set_returns_validated_artifacts():
    scope = {"index_event": "Cirrhosis", "criterion_domains": {"Cirrhosis": "Condition"}, "entry_limit": "First", "prior_observation": "0", "index_day_boundary": "included", "windows": "none", "exit_strategy": "observation"}
    result = StudyAgent(mcp_client=_Mcp()).run_phenotype_make_computable_flow("earliest cirrhosis", True, scope, "provided_only", _concept_sets("710"))
    assert result["status"] == "ok"
    assert result["validation"]["status"] == "passed"
    assert isinstance(result["circe_json"], dict)


def test_required_concept_review_returns_vocab_candidates():
    scope = {"index_event": "Cirrhosis", "criterion_domains": {"Cirrhosis": "Condition"}, "entry_limit": "First", "prior_observation": "0", "index_day_boundary": "included", "windows": "none", "exit_strategy": "observation"}
    result = StudyAgent(mcp_client=_Mcp()).run_phenotype_make_computable_flow("earliest cirrhosis", True, scope)
    assert result["status"] == "needs_concept_review"
    assert result["concept_candidates"][0]["conceptId"] == 4064161
    assert result["concept_provenance"]["tool"] == "vocab_search_standard"


def test_propose_mode_returns_llm_plan_for_review():
    scope = {"index_event": "Cirrhosis", "criterion_domains": {"Cirrhosis": "Condition"}, "entry_limit": "First", "prior_observation": "0", "index_day_boundary": "included", "windows": "none", "exit_strategy": "observation"}
    agent = StudyAgent(mcp_client=_Mcp())
    agent._call_llm = lambda prompt, required_keys: LLMCallResult(status="ok", parsed_content={"status": "needs_concept_review", "scope_check": {}, "concept_sets": [], "cohort_plan": {}, "assumptions": [], "warnings": []})
    result = agent.run_phenotype_make_computable_flow("earliest cirrhosis", True, scope, "propose")
    assert result["status"] == "needs_concept_review"
    assert result["llm_status"] == "ok"
    assert result["proposed_plan"]["status"] == "needs_concept_review"


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
        ("743", {"index_event": "Diabetic ketoacidosis", "entry_limit": "All", "visit_overlap": True, "exit_strategy": {"type": "fixed", "offset_days": 30}}),
        ("222", {"index_event": "SJS/TEN", "entry_limit": "All", "visit_overlap": True, "exit_strategy": {"type": "fixed", "offset_days": 1}}),
    ]
    for case_id, scope in cases:
        ("1340", {"index_event": "Anorexia nervosa", "entry_limit": "All", "exit_strategy": {"type": "fixed", "offset_days": 30}, "era_days": 365}),
        ("1341", {"index_event": "Eating disorders", "entry_limit": "All", "exit_strategy": {"type": "fixed", "offset_days": 30}, "era_days": 365}),
        ("1345", {"index_event": "Personality disorders", "entry_limit": "All", "exit_strategy": {"type": "fixed", "offset_days": 30}, "era_days": 365}),
        ("1346", {"index_event": "ADHD", "entry_limit": "All", "exit_strategy": {"type": "fixed", "offset_days": 30}, "era_days": 365}),
        ("1347", {"index_event": "PTSD", "entry_limit": "All", "exit_strategy": {"type": "fixed", "offset_days": 30}, "era_days": 365}),
        emitted = emit_capr(scope, _policy_concept_sets(case_id))
        assert emitted["status"] == "passed", case_id
        assert validate_capr_source(emitted["capr_code"])["status"] == "passed", case_id


def test_era_days_becomes_circe_collapse_settings():
    emitted = emit_capr({"index_event": "Anorexia", "entry_limit": "All", "exit_strategy": {"type": "fixed", "offset_days": 30}, "era_days": 365}, _policy_concept_sets("1340"))
    circe = validate_capr_source(emitted["capr_code"])["circe_json"]
    assert circe["CollapseSettings"] == {"CollapseType": "ERA", "EraPad": 365}


def test_mixed_domain_concept_set_fails_closed():
    emitted = emit_capr({"index_event": "Rheumatoid arthritis", "entry_limit": "First", "exit_strategy": "observation"}, _policy_concept_sets("858"))
    assert emitted["status"] == "failed"
    assert emitted["messages"] == ["mixed_domain_concept_set_requires_explicit_multi_domain_plan"]
