from __future__ import annotations

from pathlib import Path


def test_compose_uses_read_only_config_and_secret_only_env_file() -> None:
    source = Path("compose.yaml").read_text(encoding="utf-8")
    assert "./config.yaml:/app/config.yaml:ro" in source
    assert "secrets.env" in source
    assert '"--profile", "docker"' in source
    assert "STUDY_AGENT_MCP_URL:" not in source


def test_example_config_has_docker_profile_and_no_secret_keys() -> None:
    source = Path("config.example.yaml").read_text(encoding="utf-8").lower()
    assert "profiles:" in source
    assert "docker:" in source
    for forbidden in ("api_key", "token", "password", "omop_db_engine"):
        assert forbidden not in source


def test_dockerfile_copies_example_configuration() -> None:
    assert "config.example.yaml" in Path("Dockerfile").read_text(encoding="utf-8")
