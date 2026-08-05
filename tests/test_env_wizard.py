from __future__ import annotations

import os
import stat

import pytest

from study_agent_core.env_wizard import (
    collect_configuration,
    render_env_file,
    write_env_file,
)


def _answers(values: list[str]):
    iterator = iter(values)
    return lambda _prompt: next(iterator)


def test_collect_direct_llm_and_retrieval_configuration_hides_secret_from_output() -> (
    None
):
    output: list[str] = []
    values, comments, run_style = collect_configuration(
        input_fn=_answers(
            [
                "direct",
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

    assert run_style == "direct"
    assert comments == []
    assert values["STUDY_AGENT_MCP_URL"] == "http://127.0.0.1:8790/mcp"
    assert values["LLM_API_KEY"] == "llm-secret-value"
    assert "llm-secret-value" not in "\n".join(output)


def test_collect_docker_hecate_profile_uses_container_index_path() -> None:
    values, comments, run_style = collect_configuration(
        input_fn=_answers(["docker", "", "", "no", "yes", "", "", "no", "hecate"]),
        output_fn=lambda _message: None,
        secret_input=lambda _prompt: pytest.fail("no secret should be requested"),
    )

    assert run_style == "docker"
    assert values["PHENOTYPE_INDEX_DIR"] == "/data/phenotype_index"
    assert values["VOCAB_SEARCH_PROVIDER"] == "hecate_api"
    assert any("mounts" in comment for comment in comments)


def test_render_escapes_sensitive_value_without_printing_it() -> None:
    content = render_env_file({"LLM_API_KEY": "contains $ and ' quotes"})

    assert "LLM_API_KEY='contains $ and \\' quotes'" in content


def test_write_env_file_refuses_existing_file_and_uses_private_mode(tmp_path) -> None:
    output = tmp_path / ".env"
    write_env_file(output, "LLM_API_KEY=secret\n")

    assert output.read_text(encoding="utf-8") == "LLM_API_KEY=secret\n"
    if os.name != "nt":
        assert stat.S_IMODE(output.stat().st_mode) == 0o600
    with pytest.raises(FileExistsError):
        write_env_file(output, "LLM_API_KEY=replaced\n")
