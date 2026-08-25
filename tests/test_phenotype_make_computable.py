import csv
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
    assert result["capr"]["filename"] == "phenotype_definition.R"
    assert result["capr"]["entry_point"] == "phenotype_make_computable_definition"


def test_required_concept_review_returns_vocab_candidates():
    scope = {"index_event": "Cirrhosis", "criterion_domains": {"Cirrhosis": "Condition"}, "entry_limit": "First", "prior_observation": "0", "index_day_boundary": "included", "windows": "none", "exit_strategy": "observation"}
    result = StudyAgent(mcp_client=_Mcp()).run_phenotype_make_computable_flow("earliest cirrhosis", True, scope)
    assert result["status"] == "needs_concept_review"
    assert result["concept_candidates"][0]["conceptId"] == 4064161
    assert result["concept_provenance"]["tool"] == "vocab_search_standard"


def test_propose_mode_returns_llm_plan_for_review():
    scope = {"index_event": "Cirrhosis", "criterion_domains": {"Cirrhosis": "Condition"}, "entry_limit": "First", "prior_observation": "0", "index_day_boundary": "included", "windows": "none", "exit_strategy": "observation"}
    agent = StudyAgent(mcp_client=_Mcp())
    agent._call_llm = lambda prompt, required_keys: LLMCallResult(status="ok", parsed_content={"status": "needs_clarification", "scope_check": {}, "concept_sets": [], "cohort_plan": {}, "assumptions": [], "warnings": []})
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


def test_prompt_contract_requires_policy_bearing_reviewed_concept_items():
    bundle = _load_bundle()
    concept_set = bundle["output_schema"]["properties"]["concept_sets"]["items"]
    item = concept_set["properties"]["items"]["items"]
    assert concept_set["required"] == ["name", "domain", "items"]
    assert item["required"] == ["concept_id", "domain", "include_descendants", "include_mapped", "is_excluded"]


def test_propose_mode_rejects_a_plan_with_an_unsupported_exit_strategy():
    scope = {"index_event": "Cirrhosis", "criterion_domains": {"Cirrhosis": "Condition"}, "entry_limit": "First", "prior_observation": 0, "index_day_boundary": "included", "windows": "none", "exit_strategy": "observation"}
    agent = StudyAgent(mcp_client=_Mcp())
    agent._call_llm = lambda prompt, required_keys: LLMCallResult(status="ok", parsed_content={"status": "ok", "scope_check": {}, "concept_sets": [], "cohort_plan": {"exit_strategy": {"type": "observation_end"}}, "assumptions": [], "warnings": []})
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
        ("743", {"index_event": "Diabetic ketoacidosis", "entry_limit": "All", "visit_overlap": True, "exit_strategy": {"type": "fixed", "offset_days": 30}}),
        ("222", {"index_event": "SJS/TEN", "entry_limit": "All", "visit_overlap": True, "exit_strategy": {"type": "fixed", "offset_days": 1}}),
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


def test_visit_overlap_prior_observation_scope_is_preserved_in_circe():
    scope = {"index_event": "SJS/TEN", "entry_limit": "All", "prior_observation": 365, "visit_overlap": True, "exit_strategy": {"type": "fixed", "offset_days": 1}}
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
