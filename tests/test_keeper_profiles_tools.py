import pytest

from study_agent_mcp.tools import keeper_profiles


class ToolMCP:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self, name: str):
        def decorator(fn):
            self.tools[name] = fn
            return fn

        return decorator


@pytest.mark.mcp
def test_keeper_profile_to_rows_builds_keeper_review_row() -> None:
    mcp = ToolMCP()
    keeper_profiles.register(mcp)
    tool = mcp.tools["keeper_profile_to_rows"]
    result = tool(
        profile_records=[
            {"generatedId": "1", "category": "phenotype", "conceptName": "GI bleed", "startDay": 0, "endDay": 0, "target": "Other", "extraData": ""},
            {"generatedId": "1", "category": "age", "conceptName": "44", "startDay": 0, "endDay": 0, "target": "Disease of interest", "extraData": ""},
            {"generatedId": "1", "category": "sex", "conceptName": "Male", "startDay": 0, "endDay": 0, "target": "Disease of interest", "extraData": ""},
            {"generatedId": "1", "category": "observationPeriod", "conceptName": "Observation period", "startDay": -365, "endDay": 30, "target": "Disease of interest", "extraData": ""},
            {"generatedId": "1", "category": "presentation", "conceptName": "Gastrointestinal hemorrhage", "startDay": 0, "endDay": 0, "target": "Disease of interest", "extraData": "EHR problem list"},
            {"generatedId": "1", "category": "visits", "conceptName": "Inpatient Visit", "startDay": -1, "endDay": 2, "target": "Disease of interest", "extraData": "Gastroenterology"},
            {"generatedId": "1", "category": "measurements", "conceptName": "Hemoglobin", "startDay": -1, "endDay": -1, "target": "Disease of interest", "extraData": "8.1 g/dL, abnormal - low"},
            {"generatedId": "1", "category": "cohortPrevalence", "conceptName": "0.01234", "startDay": 0, "endDay": 0, "target": "Other", "extraData": ""},
        ],
        remove_pii=True,
    )
    row = result["rows"][0]
    assert result["row_count"] == 1
    assert row["phenotype"] == "GI bleed"
    assert row["gender"] == "Male"
    assert row["visitContext"] == row["visits"]
    assert "Gastrointestinal hemorrhage" in row["presentation"]
    assert "Hemoglobin" in row["measurements"]
    assert row["cohortPrevalence"] == pytest.approx(0.01234)


@pytest.mark.mcp
def test_keeper_profile_to_rows_includes_optional_pii_fields_only_when_requested() -> None:
    mcp = ToolMCP()
    keeper_profiles.register(mcp)
    tool = mcp.tools["keeper_profile_to_rows"]
    result = tool(
        profile_records=[
            {"generatedId": "1", "category": "personId", "conceptName": "123", "startDay": 0, "endDay": 0, "target": "Other", "extraData": ""},
            {"generatedId": "1", "category": "cohortStartDate", "conceptName": "2026-04-01", "startDay": 0, "endDay": 0, "target": "Other", "extraData": ""},
        ],
        remove_pii=False,
    )
    row = result["rows"][0]
    assert row["personId"] == "123"
    assert row["cohortStartDate"] == "2026-04-01"


@pytest.mark.mcp
def test_connection_identity_is_non_secret_and_stable_for_a_target() -> None:
    sqlalchemy = pytest.importorskip("sqlalchemy")
    engine = sqlalchemy.create_engine("sqlite:///:memory:")
    with engine.connect() as connection:
        identity = keeper_profiles._connection_identity(connection)
    assert identity["dialect"] == "sqlite"
    assert identity["target_hash"]
    assert "password" not in identity
    assert "username" not in identity


@pytest.mark.mcp
def test_concept_set_counts_by_lane_handles_missing_lane() -> None:
    assert keeper_profiles._concept_set_counts_by_lane(
        [
            {"conceptSetName": "doi"},
            {"conceptSetName": "doi"},
            {},
        ]
    ) == {"doi": 2, "unlabeled": 1}
