from __future__ import annotations

import os
from pathlib import Path

import pytest

from study_agent_core.config import (
    ConfigError,
    apply_config,
    load_config,
    project_to_environment,
)
from study_agent_core import config_cli


def write_config(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_load_config_resolves_relative_paths_and_projects_legacy_names(
    tmp_path, monkeypatch
) -> None:
    path = write_config(
        tmp_path / "config.yaml",
        """\
version: 1
profile: native
paths:
  phenotype_index: data/index
  logs: logs
acp:
  bind: {host: 127.0.0.1, port: 8765}
  mcp: {mode: http, url: http://127.0.0.1:8790/mcp}
mcp:
  bind: {host: 127.0.0.1, port: 8790}
  transport: http
llm: {api_url: http://llm.test/v1/chat, model: test-model}
""",
    )
    monkeypatch.setenv("LLM_MODEL", "stale-shell-model")
    config = load_config(path)
    assert config is not None
    assert config.paths.phenotype_index == tmp_path / "data/index"
    values = project_to_environment(config)
    assert values["LLM_MODEL"] == "test-model"
    apply_config(config)
    assert os.environ["LLM_MODEL"] == "test-model"


def test_profile_overlay_and_unknown_keys_are_validated(tmp_path) -> None:
    path = write_config(
        tmp_path / "config.yaml",
        """\
version: 1
profile: native
mcp:
  bind: {host: 127.0.0.1, port: 8790}
profiles:
  docker:
    mcp:
      bind: {host: 0.0.0.0, port: 8790}
""",
    )
    config = load_config(path, profile="docker")
    assert config is not None
    assert config.profile == "docker"
    assert config.mcp.bind.host == "0.0.0.0"
    write_config(tmp_path / "invalid.yaml", "version: 1\nunknown: value\n")
    with pytest.raises(ConfigError, match="Invalid configuration"):
        load_config(tmp_path / "invalid.yaml")


def test_config_rejects_secrets_and_config_path_discovery(
    tmp_path, monkeypatch
) -> None:
    path = write_config(
        tmp_path / "config.yaml", "version: 1\nllm:\n  api_key: forbidden\n"
    )
    monkeypatch.setenv("STUDY_AGENT_CONFIG", str(path))
    with pytest.raises(ConfigError, match="Secrets are not allowed"):
        load_config()
    write_config(tmp_path / "engine.yaml", "version: 1\nOMOP_DB_ENGINE: forbidden\n")
    with pytest.raises(ConfigError, match="Secrets are not allowed"):
        load_config(tmp_path / "engine.yaml")
    write_config(
        tmp_path / "url.yaml",
        "version: 1\nllm: {api_url: 'https://user:password@example.test/v1'}\n",
    )
    with pytest.raises(ConfigError, match="Secrets are not allowed"):
        load_config(tmp_path / "url.yaml")


def test_wrapper_applies_config_before_service_import(tmp_path, monkeypatch) -> None:
    path = write_config(
        tmp_path / "config.yaml", "version: 1\nllm: {model: from-yaml}\n"
    )
    observed: dict[str, str] = {}
    monkeypatch.setenv("LLM_MODEL", "legacy")
    config_cli._run(
        "test",
        ["--config", str(path)],
        lambda: observed.update(model=os.environ["LLM_MODEL"]),
    )
    assert observed == {"model": "from-yaml"}


def test_legacy_environment_only_startup_does_not_require_config(monkeypatch) -> None:
    monkeypatch.delenv("STUDY_AGENT_CONFIG", raising=False)
    started = []
    config_cli._run("test", [], lambda: started.append(True))
    assert started == [True]


def test_explicit_base_profile_is_accepted_without_an_overlay(tmp_path) -> None:
    path = write_config(tmp_path / "config.yaml", "version: 1\nprofile: native\n")
    config = load_config(path, profile="native")
    assert config is not None
    assert config.profile == "native"


def test_unreadable_config_has_clear_error(tmp_path, monkeypatch) -> None:
    path = write_config(tmp_path / "config.yaml", "version: 1\n")

    def deny_read_text(*_args, **_kwargs):
        raise PermissionError("permission denied")

    monkeypatch.setattr(Path, "read_text", deny_read_text)
    with pytest.raises(ConfigError, match="must be readable by the service user"):
        load_config(path)
