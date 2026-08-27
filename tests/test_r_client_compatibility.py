import pytest

from study_agent_mcp.tools.r_client_compatibility import check_r_client_compatibility


pytestmark = pytest.mark.r_client_compatibility


def test_installed_companion_r_packages_match_public_contract() -> None:
    result = check_r_client_compatibility()

    assert result["status"] == "passed", result
    assert result["packages"]["slashOhdsiAcpClient"]["compatible"] is True
    assert result["packages"]["slashOhdsiStrategusAssistant"]["compatible"] is True
    assert all(item["compatible"] for item in result["public_contract"].values())
    assert result["strategus_runtime"]["status"] == "passed"
