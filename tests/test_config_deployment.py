from __future__ import annotations

from pathlib import Path


def test_compose_uses_read_only_config_and_secret_only_env_file() -> None:
    source = Path("compose.yaml").read_text(encoding="utf-8")
    assert "./config.yaml:/app/config.yaml:ro" in source
    assert "secrets.env" in source
    assert '"--profile", "docker"' in source
    assert source.count("host.docker.internal:host-gateway") == 2
    assert "STUDY_AGENT_MCP_URL:" not in source


def test_example_config_has_docker_profile_and_no_secret_keys() -> None:
    source = Path("config.example.yaml").read_text(encoding="utf-8").lower()
    assert "profiles:" in source
    assert "docker:" in source
    assert "host.docker.internal" in source
    for forbidden in ("api_key", "token", "password", "omop_db_engine"):
        assert forbidden not in source


def test_dockerfile_copies_example_configuration() -> None:
    assert "config.example.yaml" in Path("Dockerfile").read_text(encoding="utf-8")


def test_declared_runtime_dependencies_match_service_imports() -> None:
    pyproject = Path("pyproject.toml").read_text(encoding="utf-8")
    environment = Path("environment.yml").read_text(encoding="utf-8")
    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert '"mcp>=1.10,<2"' in pyproject
    assert '"httpx>=0.27.1,<1"' in pyproject
    assert "mcp>=1.10,<2" in environment
    assert "httpx>=0.27.1,<1" in environment
    assert "from mcp.server.fastmcp import FastMCP" in dockerfile


def test_dodo_and_calibration_use_configured_cross_platform_paths() -> None:
    dodo = Path("dodo.py").read_text(encoding="utf-8")
    calibration = Path("scripts/calibrate_timeouts.py").read_text(encoding="utf-8")
    assert "load_config(cwd=REPO_ROOT)" in dodo
    assert "STUDY_AGENT_RUNTIME_DIR" in dodo
    assert "load_secret_environment(cwd=REPO_ROOT)" in dodo
    assert "/tmp/study_agent" not in dodo
    assert '[sys.executable, "tests/' in dodo
    assert "load_config(cwd=REPO_ROOT)" in calibration
    assert "/tmp/study_agent" not in calibration


def test_dodo_runtime_environment_is_loadable() -> None:
    import dodo

    environment = dodo._runtime_env()
    assert environment["STUDY_AGENT_PORT"]
    assert dodo._runtime_dir(environment).is_dir()
