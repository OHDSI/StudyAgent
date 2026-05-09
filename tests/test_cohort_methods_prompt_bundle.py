import pytest
from pathlib import Path

from study_agent_mcp.tools import cohort_methods_prompt_bundle
from study_agent_core.cohort_methods_spec_validation import COHORT_METHODS_SPEC_TOP_LEVEL_KEYS, validate_cohort_methods_spec


class DummyMCP:
    def __init__(self) -> None:
        self.tools: dict = {}

    def tool(self, name: str):
        def decorator(fn):
            self.tools[name] = fn
            return fn

        return decorator


PROMPT_DIR = Path("mcp_server/prompts/cohort_methods")


@pytest.mark.mcp
def test_bundle_returns_expected_keys() -> None:
    mcp = DummyMCP()
    cohort_methods_prompt_bundle.register(mcp)
    fn = mcp.tools["cohort_methods_prompt_bundle"]
    payload = fn()
    assert "instruction_template" in payload
    assert "output_style_template" in payload
    assert "annotated_template" in payload
    assert "analysis_specifications_template" in payload
    assert "json_field_descriptions" in payload
    assert "defaults_spec" in payload
    assert payload["schema_version"] == "v1.4.0"


@pytest.mark.mcp
def test_instruction_and_output_style_load_from_prompt_files() -> None:
    mcp = DummyMCP()
    cohort_methods_prompt_bundle.register(mcp)
    fn = mcp.tools["cohort_methods_prompt_bundle"]
    payload = fn()
    assert payload["instruction_template"] == (PROMPT_DIR / "instruction_cohort_methods_specs.md").read_text(encoding="utf-8").strip()
    assert payload["output_style_template"] == (PROMPT_DIR / "output_style_cohort_methods_specs.md").read_text(encoding="utf-8").strip()
    assert "<Instruction>" in payload["instruction_template"]
    assert "<Output Style>" in payload["output_style_template"]


@pytest.mark.mcp
def test_analysis_template_loads_cm_analysis_template() -> None:
    mcp = DummyMCP()
    cohort_methods_prompt_bundle.register(mcp)
    fn = mcp.tools["cohort_methods_prompt_bundle"]
    payload = fn()
    assert "customAtlasTemplate" not in payload["analysis_specifications_template"]
    assert "/*" not in payload["analysis_specifications_template"]
    assert "fitOutcomeModelArgs" in payload["analysis_specifications_template"]
    assert payload["annotated_template"] == payload["analysis_specifications_template"]


@pytest.mark.mcp
def test_json_field_descriptions_start_at_top_level_shape() -> None:
    mcp = DummyMCP()
    cohort_methods_prompt_bundle.register(mcp)
    fn = mcp.tools["cohort_methods_prompt_bundle"]
    payload = fn()
    descriptions = payload["json_field_descriptions"]
    assert descriptions.startswith("## Top-Level Shape")
    assert "temporary StudyAgent-specific contract" not in descriptions
    assert "fitOutcomeModelArgs" in descriptions


@pytest.mark.mcp
def test_defaults_spec_is_cm_analysis_template_json() -> None:
    mcp = DummyMCP()
    cohort_methods_prompt_bundle.register(mcp)
    fn = mcp.tools["cohort_methods_prompt_bundle"]
    payload = fn()
    defaults = payload["defaults_spec"]
    assert isinstance(defaults, dict)
    for key in COHORT_METHODS_SPEC_TOP_LEVEL_KEYS:
        assert key in defaults, f"missing key in defaults_spec: {key}"
    ok, missing = validate_cohort_methods_spec(defaults)
    assert ok is True, f"defaults_spec failed top-level validation: {missing}"


@pytest.mark.mcp
def test_bundle_is_cached() -> None:
    mcp = DummyMCP()
    cohort_methods_prompt_bundle.register(mcp)
    fn = mcp.tools["cohort_methods_prompt_bundle"]
    a = fn()
    b = fn()
    assert a is b  # same object identity means cached
