import pytest
import yaml

from study_agent_core.models import (
    CaseCausalReviewInput,
    KeeperConceptSetsGenerateInput,
    KeeperProfileRow,
    KeeperProfilesGenerateInput,
    PhenotypeValidationReviewInput,
)


@pytest.mark.core
def test_phenotype_validation_review_input_includes_keeper_row() -> None:
    schema = PhenotypeValidationReviewInput.model_json_schema()
    assert "keeper_row" in schema["properties"]
    assert "disease_name" in schema["properties"]


@pytest.mark.core
def test_keeper_concept_sets_generate_input_schema() -> None:
    schema = KeeperConceptSetsGenerateInput.model_json_schema()
    assert "phenotype" in schema["properties"]
    assert "domain_keys" in schema["properties"]
    assert schema["properties"]["candidate_limit"]["default"] == 50


@pytest.mark.core
def test_keeper_profiles_generate_input_schema() -> None:
    schema = KeeperProfilesGenerateInput.model_json_schema()
    assert "keeper_concept_sets" in schema["properties"]
    assert "sample_size" in schema["properties"]
    assert schema["properties"]["remove_pii"]["default"] is True


@pytest.mark.core
def test_keeper_profile_row_supports_legacy_and_canonical_review_fields() -> None:
    row = KeeperProfileRow(
        age=44,
        sex="Male",
        visitContext="Inpatient visit",
        priorDisease="Peptic ulcer",
        alternativeDiagnoses="Mallory-Weiss tear",
        postDrugs="Naproxen",
    )
    assert row.age == 44
    assert row.sex == "Male"
    assert row.visitContext == "Inpatient visit"
    assert row.alternativeDiagnoses == "Mallory-Weiss tear"
    assert row.postDrugs == "Naproxen"


@pytest.mark.core
def test_service_registry_declares_keeper_expansion_flows() -> None:
    with open("docs/SERVICE_REGISTRY.yaml", "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    services = data["services"]
    assert services["keeper_concept_sets_generate"]["endpoint"] == "/flows/keeper_concept_sets_generate"
    assert services["keeper_profiles_generate"]["endpoint"] == "/flows/keeper_profiles_generate"



@pytest.mark.core
def test_case_causal_review_input_schema() -> None:
    schema = CaseCausalReviewInput.model_json_schema()
    assert "adverse_event_name" in schema["properties"]
    assert "case_row" in schema["properties"]
    assert "source_type" in schema["properties"]
    assert "allowed_domains" in schema["properties"]


@pytest.mark.core
def test_service_registry_declares_case_causal_review_flow() -> None:
    with open("docs/SERVICE_REGISTRY.yaml", "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    service = data["services"]["case_causal_review"]
    assert service["endpoint"] == "/flows/case_causal_review"
    assert service["mcp_tools"] == [
        "case_causal_review_prompt_bundle",
        "case_causal_review_sanitize_row",
        "case_causal_review_build_prompt",
        "case_causal_review_parse_response",
        "get_case_review_concept_set_domain",
        "get_case_review_drug_signal_details",
        "get_case_review_drug_label_details",
        "get_case_review_report_literature_stub",
    ]
    assert service["validation"]["controlled_identifier_keys"] == [
        "ingred_rxcui",
        "rxcui",
        "adverse_event_meddra_id",
        "meddra_code",
        "meddra_id",
        "concept_id",
        "ingredient_concept_id",
        "adverse_event_concept_id",
        "outcome_concept_id",
    ]
