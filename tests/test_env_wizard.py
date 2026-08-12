from __future__ import annotations

import os
import stat

import pytest

from study_agent_core.env_wizard import (
    collect_configuration,
    migrate_env,
    render_config_file,
    render_env_file,
    write_env_file,
)


def _answers(values: list[str]):
    iterator = iter(values)
    return lambda _prompt: next(iterator)


def test_collect_configuration_separates_secret_values_from_yaml() -> None:
    output: list[str] = []
    values, secrets, run_style = collect_configuration(
        input_fn=_answers(
            [
                "native",
                "",
                "",
                "http",
                "",
                "",
                "",
                "yes",
                "",
                "",
                "no",
                "yes",
                "",
                "",
                "",
                "no",
                "none",
            ]
        ),
        output_fn=output.append,
        secret_input=lambda _prompt: "llm-secret-value",
    )
    content = render_config_file(values, run_style)
    assert run_style == "native"
    assert secrets == {"LLM_API_KEY": "llm-secret-value"}
    assert "llm-secret-value" not in content
    assert "LLM_API_KEY" not in content
    assert "llm-secret-value" not in "\n".join(output)


def test_migrate_env_classifies_known_secret_values_without_echoing(tmp_path) -> None:
    source = tmp_path / ".env"
    source.write_text(
        "LLM_API_KEY=hidden\nOMOP_DB_ENGINE=db-secret\nMCP_PORT=9000\n",
        encoding="utf-8",
    )
    values, secrets, profile = migrate_env(source)
    assert values == {"MCP_PORT": "9000"}
    assert secrets == {"LLM_API_KEY": "hidden", "OMOP_DB_ENGINE": "db-secret"}
    assert profile == "native"


def test_render_secret_file_escapes_values() -> None:
    content = render_env_file({"LLM_API_KEY": "contains $ and ' quotes"})
    assert "LLM_API_KEY='contains $ and \\' quotes'" in content


def test_write_file_refuses_existing_file_and_uses_private_mode(tmp_path) -> None:
    output = tmp_path / "secrets.env"
    write_env_file(output, "LLM_API_KEY=secret\n")
    assert output.read_text(encoding="utf-8") == "LLM_API_KEY=secret\n"
    if os.name != "nt":
        assert stat.S_IMODE(output.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        write_env_file(output, "LLM_API_KEY=replaced\n")
