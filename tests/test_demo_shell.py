import pytest

from pathlib import Path

from study_agent_acp.demo_shell import (
    ACPClient,
    DemoSession,
    StudyAgentDemoShell,
    _extract_keeper_row,
    _infer_phenotype_name,
    _slugify,
    _split_csv,
    _split_query_text,
)


def test_slugify_normalizes_text() -> None:
    assert _slugify("Acute Gastrointestinal Bleeding") == "acute-gastrointestinal-bleeding"
    assert _slugify("   ") == "result"


def test_split_csv_trims_empty_values() -> None:
    assert _split_csv("Condition, Observation , , Procedure") == ["Condition", "Observation", "Procedure"]


def test_split_query_text_uses_semicolons() -> None:
    assert _split_query_text("GI bleed; abdominal pain ; melena") == ["GI bleed", "abdominal pain", "melena"]


def test_extract_keeper_row_from_rows_payload() -> None:
    payload = {
        "rows": [
            {"generatedId": "1", "presentation": "A"},
            {"generatedId": "2", "presentation": "B"},
        ]
    }
    assert _extract_keeper_row(payload, 1)["generatedId"] == "2"


def test_extract_keeper_row_from_nested_full_result() -> None:
    payload = {
        "full_result": {
            "rows": [
                {"generatedId": "1", "visitContext": "Inpatient Visit"},
            ]
        }
    }
    assert _extract_keeper_row(payload, 0)["visitContext"] == "Inpatient Visit"


def test_extract_keeper_row_accepts_direct_keeper_row() -> None:
    payload = {"keeper_row": {"generatedId": "5", "presentation": "GI hemorrhage"}}
    assert _extract_keeper_row(payload, 0)["generatedId"] == "5"


def test_extract_keeper_row_rejects_missing_rows() -> None:
    with pytest.raises(ValueError, match="could not locate a keeper row"):
        _extract_keeper_row({"concept_sets": []}, 0)


def test_extract_keeper_row_checks_row_index() -> None:
    with pytest.raises(ValueError, match="out of range"):
        _extract_keeper_row({"rows": [{"generatedId": "1"}]}, 2)


def test_infer_phenotype_name_prefers_top_level() -> None:
    assert _infer_phenotype_name({"phenotype": "GI bleed"}) == "GI bleed"


def test_infer_phenotype_name_uses_nested_full_result() -> None:
    payload = {"full_result": {"phenotype_name": "Intracranial bleeding"}}
    assert _infer_phenotype_name(payload) == "Intracranial bleeding"


class _FakeClient(ACPClient):
    def __init__(self):
        super().__init__(base_url="http://127.0.0.1:8765")
        self.last_post = None

    def post(self, path, payload):
        self.last_post = (path, payload)
        return {
            "status": "ok",
            "dialogue": {
                "answer": "Use the current step context before changing cohort IDs.",
                "current_step_guidance": ["Stay in the comparator recommendation step."],
                "cautions": ["Do not overwrite cached selections yet."],
                "suggested_next_actions": ["Review the comparator statement wording."],
            },
        }


def test_demo_shell_ohdsi_command_uses_session_context(tmp_path, capsys) -> None:
    client = _FakeClient()
    session = DemoSession(output_dir=Path(tmp_path))
    session.current_study_intent = "Compare sitagliptin versus glipizide new users."
    session.current_workflow_type = "cohort_methods"
    session.current_step = "comparator_recommendation"
    session.current_role = "comparator"
    session.current_context = {"statement": "New users of glipizide"}
    shell = StudyAgentDemoShell(client=client, session=session)

    shell.handle_line("/ohdsi why is this comparator weak?")

    assert client.last_post is not None
    path, payload = client.last_post
    assert path == "/flows/workflow_context_dialogue"
    assert payload["current_step"] == "comparator_recommendation"
    assert payload["current_role"] == "comparator"
    assert payload["study_intent"] == "Compare sitagliptin versus glipizide new users."
    out = capsys.readouterr().out
    assert "Use the current step context before changing cohort IDs." in out
