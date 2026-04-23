import textwrap

import pytest

from study_agent_mcp.tools import _service_registry


@pytest.mark.mcp
def test_get_controlled_identifier_keys_reads_service_registry_override(tmp_path, monkeypatch) -> None:
    registry = tmp_path / "services.yaml"
    registry.write_text(
        textwrap.dedent(
            """
            services:
              case_causal_review:
                validation:
                  controlled_identifier_keys:
                    - ingred_rxcui
                    - adverse_event_meddra_id
            """
        ).strip(),
        encoding="utf-8",
    )
    monkeypatch.setenv("STUDY_AGENT_SERVICE_REGISTRY", str(registry))
    _service_registry.load_service_registry.cache_clear()

    keys = _service_registry.get_controlled_identifier_keys("case_causal_review", {"fallback_key"})

    assert keys == frozenset({"ingred_rxcui", "adverse_event_meddra_id"})


@pytest.mark.mcp
def test_get_controlled_identifier_keys_falls_back_on_invalid_registry(tmp_path, monkeypatch) -> None:
    registry = tmp_path / "services.yaml"
    registry.write_text("services:\n  case_causal_review:\n    validation: []\n", encoding="utf-8")
    monkeypatch.setenv("STUDY_AGENT_SERVICE_REGISTRY", str(registry))
    _service_registry.load_service_registry.cache_clear()

    keys = _service_registry.get_controlled_identifier_keys("case_causal_review", {"fallback_key"})

    assert keys == frozenset({"fallback_key"})
