import copy
import json

import pytest

from study_agent_core.tools import cohort_lint

from _repo_paths import repo_path


def _demo_cohort():
    # Atlas/Circe export used by scripts/test_cohort_critique_general_design.R
    return json.loads(repo_path("scripts", "cohort_definition.json").read_text(encoding="utf-8"))


def _window(start_days, start_coeff, end_days, end_coeff):
    return {
        "Start": {"Days": start_days, "Coeff": start_coeff},
        "End": {"Days": end_days, "Coeff": end_coeff},
        "UseEventEnd": False,
    }


def _finding_ids(cohort):
    return {finding.get("id") for finding in cohort_lint(cohort)["findings"]}


@pytest.mark.core
@pytest.mark.parametrize(
    "path",
    [
        ("scripts", "cohort_definition.json"),
        ("scripts", "1197_Acute_gastrointestinal_bleeding.json"),
        ("data", "cohorts", "13.json"),
    ],
)
def test_cohort_lint_valid_circe_windows_are_not_flagged(path):
    cohort = json.loads(repo_path(*path).read_text(encoding="utf-8"))
    assert cohort["InclusionRules"]
    assert not any(finding_id.startswith("inverted_window") for finding_id in _finding_ids(cohort))


@pytest.mark.core
def test_cohort_lint_flags_inverted_circe_start_window():
    cohort = _demo_cohort()
    # 0 days after index through 180 days before index: no event can match.
    cohort["InclusionRules"][0]["expression"]["CriteriaList"][0]["StartWindow"] = _window(0, 1, 180, -1)

    result = cohort_lint(cohort)

    findings = [finding for finding in result["findings"] if finding.get("id") == "inverted_window_0"]
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"
    assert findings[0]["evidence"] == [{"ref": "/InclusionRules/0/expression/CriteriaList/0/StartWindow"}]


@pytest.mark.core
def test_cohort_lint_flags_inverted_circe_windows_in_nested_groups_and_correlated_criteria():
    cohort = _demo_cohort()
    rule = cohort["InclusionRules"][0]["expression"]
    criterion = rule["CriteriaList"][0]
    nested = copy.deepcopy(criterion)
    nested["EndWindow"] = _window(30, 1, 10, 1)
    rule["Groups"] = [{"Type": "ANY", "CriteriaList": [nested], "DemographicCriteriaList": [], "Groups": []}]
    correlated = copy.deepcopy(criterion)
    correlated["StartWindow"] = _window(7, 1, 7, -1)
    cohort["InclusionRules"].append(
        {
            "name": "drug with a correlated event",
            "expression": {
                "Type": "ALL",
                "CriteriaList": [
                    {
                        "Criteria": {
                            "DrugExposure": {
                                "CodesetId": 3,
                                "CorrelatedCriteria": {
                                    "Type": "ALL",
                                    "CriteriaList": [correlated],
                                    "DemographicCriteriaList": [],
                                    "Groups": [],
                                },
                            }
                        },
                        "StartWindow": _window(None, -1, None, 1),
                        "Occurrence": {"Type": 2, "Count": 1},
                    }
                ],
                "DemographicCriteriaList": [],
                "Groups": [],
            },
        }
    )

    findings = {finding["id"]: finding for finding in cohort_lint(cohort)["findings"]}

    assert findings["inverted_window_0"]["evidence"] == [
        {"ref": "/InclusionRules/0/expression/Groups/0/CriteriaList/0/EndWindow"}
    ]
    assert findings["inverted_window_1"]["evidence"] == [
        {"ref": "/InclusionRules/1/expression/CriteriaList/0/Criteria/DrugExposure/CorrelatedCriteria/CriteriaList/0/StartWindow"}
    ]


@pytest.mark.core
def test_cohort_lint_does_not_flag_unbounded_circe_window_endpoints():
    cohort = _demo_cohort()
    # "All days before" through "0 days after": Days is null on the unbounded side.
    cohort["InclusionRules"][0]["expression"]["CriteriaList"][0]["StartWindow"] = _window(None, -1, 0, 1)

    assert "inverted_window_0" not in _finding_ids(cohort)
