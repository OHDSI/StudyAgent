"""Versioned, non-secret deployment configuration for Study Agent services."""

from __future__ import annotations

import copy
import os
import re
import shlex
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

CONFIG_ENV_VAR = "STUDY_AGENT_CONFIG"
SECRETS_ENV_VAR = "STUDY_AGENT_SECRETS_FILE"
DEFAULT_CONFIG_NAME = "config.yaml"
DEFAULT_SECRETS_NAME = "secrets.env"
_SECRET_NAME_RE = re.compile(
    r"(?:api[_-]?key|token|secret|password|passwd|pwd|dsn|connection[_-]?string|database[_-]?url)",
    re.I,
)
_SECRET_ENV_NAMES = {"ENGINE", "OMOP_DB_ENGINE"}
_SECRET_VALUE_RE = re.compile(
    r"(?:[a-z][a-z0-9+.\-]*://[^/\s:@]+:[^@/\s]*@|[?&](?:api[_-]?key|token|secret|password)=[^&\s]+)",
    re.I,
)


def is_secret_name(name: str) -> bool:
    """Return whether a setting name may contain a credential or connection secret."""
    return name.upper() in _SECRET_ENV_NAMES or bool(_SECRET_NAME_RE.search(name))


def load_secret_environment(
    path: str | Path | None = None, *, cwd: Path | None = None
) -> dict[str, str]:
    """Read a local secret-only env file without changing process environment.

    Explicit shell environment values can be layered over this result by callers.
    Ordinary configuration entries are rejected so the file cannot bypass
    config.yaml validation or precedence.
    """
    explicit = path is not None or bool(os.getenv(SECRETS_ENV_VAR, "").strip())
    source = (
        Path(path).expanduser()
        if path is not None
        else Path(
            os.getenv(SECRETS_ENV_VAR, "").strip()
            or (cwd or Path.cwd()) / DEFAULT_SECRETS_NAME
        )
    )
    source = source.resolve()
    if not source.exists():
        if explicit:
            raise ConfigError(f"Secret environment file does not exist: {source}")
        return {}
    if not source.is_file():
        raise ConfigError(f"Secret environment path is not a file: {source}")
    values: dict[str, str] = {}
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise ConfigError(
            f"Unable to read secret environment file {source}: {exc}"
        ) from exc
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "=" not in stripped:
            raise ConfigError(
                f"Invalid secrets.env assignment at {source}:{line_number}"
            )
        name, raw_value = stripped.split("=", 1)
        name = name.strip()
        if not name or not is_secret_name(name):
            raise ConfigError(
                f"Only secret settings are allowed in secrets.env ({source}:{line_number})."
            )
        try:
            parsed = shlex.split(raw_value, posix=True)
        except ValueError as exc:
            raise ConfigError(
                f"Invalid secret value at {source}:{line_number}: {exc}"
            ) from exc
        if len(parsed) != 1:
            raise ConfigError(f"Invalid secret value at {source}:{line_number}")
        values[name] = parsed[0]
    return values


class ConfigError(ValueError):
    """Raised when deployment configuration is missing or invalid."""


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BindConfig(StrictModel):
    host: str = "127.0.0.1"
    port: int = Field(ge=1, le=65535)


class PathsConfig(StrictModel):
    phenotype_index: Path = Path("data/phenotype_index")
    logs: Path | None = None
    runtime: Path = Path(".study-agent-runtime")


class ACPMCPConfig(StrictModel):
    mode: Literal["http", "stdio"] = "http"
    url: str | None = None
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    cwd: Path | None = None
    timeout_seconds: int = Field(default=240, ge=1)
    oneshot: bool = False


class ACPConfig(StrictModel):
    bind: BindConfig = Field(default_factory=lambda: BindConfig(port=8765))
    public_url: str | None = None
    request_timeout_seconds: int | None = Field(default=None, ge=1)
    mcp: ACPMCPConfig = Field(default_factory=ACPMCPConfig)
    allow_core_fallback: bool = True
    debug: bool = False
    threaded: bool = True
    health_deep: bool = False
    service_registry: Path = Path("docs/SERVICE_REGISTRY.yaml")


class MCPConfig(StrictModel):
    bind: BindConfig = Field(default_factory=lambda: BindConfig(port=8790))
    transport: Literal["http", "stdio", "sse"] = "http"
    path: str = "/mcp"


class LLMConfig(StrictModel):
    api_url: str = "http://localhost:3000/api/chat/completions"
    model: str = "agentstudyassistant"
    timeout_seconds: int = Field(default=300, ge=1)
    use_responses_api: bool = False
    dry_run: bool = False
    log: bool = False
    log_prompt: bool = False
    log_response: bool = False
    log_json: bool = False
    candidate_limit: int | None = Field(default=None, ge=1)
    recommendation_top_k: int | None = Field(default=None, ge=1)
    recommendation_max_results: int | None = Field(default=None, ge=1)
    planning_candidate_limit: int | None = Field(default=None, ge=1)
    planning_top_band: int | None = Field(default=None, ge=1)


class RetrievalConfig(StrictModel):
    embedding_url: str = "http://localhost:3000/ollama/api/embed"
    embedding_model: str = "qwen3-embedding:4b"
    timeout_seconds: int = Field(default=120, ge=1)
    log: bool = False
    dense_weight: float | None = None
    sparse_weight: float | None = None
    reindex_allow: bool = False


class LoggingConfig(StrictModel):
    level: str | None = None
    acp_level: str | None = None
    mcp_level: str | None = None
    max_bytes: int = Field(default=10485760, ge=1)
    backup_count: int = Field(default=5, ge=0)
    acp_file: Path | None = None
    mcp_file: Path | None = None
    acp_to_console: bool = True
    mcp_to_console: bool = True


class NetworkConfig(StrictModel):
    # Native config must keep localhost local even when launched from a nested
    # containerized development environment. Docker profiles opt in explicitly.
    rewrite_container_hosts: bool = False
    host_gateway: str = "host.docker.internal"


class VocabularyConfig(StrictModel):
    search_provider: str | None = None
    search_url: str | None = None
    search_timeout_seconds: int | None = Field(default=None, ge=1)
    search_query_prefix: str | None = None
    search_query_id: str | None = None
    metadata_provider: str | None = None
    database_schema: str = "vocabulary"
    concept_table: str = "concept"


class PhoebeConfig(StrictModel):
    provider: str | None = None
    bulk_url: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=1)
    http_retries: int | None = Field(default=None, ge=0)
    http_backoff_ms: int | None = Field(default=None, ge=0)
    max_concepts: int | None = Field(default=None, ge=1)
    max_concepts_per_relationship: int | None = Field(default=None, ge=1)
    relationship_ids: list[str] | None = None
    db_table: str | None = None


class ExternalServiceConfig(StrictModel):
    base_url: str | None = None
    host: str | None = None
    port: int | None = Field(default=None, ge=1, le=65535)
    scheme: str | None = None
    api_prefix: str | None = None
    timeout_seconds: int | None = Field(default=None, ge=1)


class KeeperConfig(StrictModel):
    vocabulary: VocabularyConfig = Field(default_factory=VocabularyConfig)
    phoebe: PhoebeConfig = Field(default_factory=PhoebeConfig)


class DemoConfig(StrictModel):
    acp_url: str | None = None
    output_dir: Path | None = None


class CalibrationConfig(StrictModel):
    acp_base_url: str | None = None
    runs: int | None = Field(default=None, ge=1)
    candidate_limits: list[int] | None = None
    output_env_path: Path | None = None
    output_json_path: Path | None = None
    mcp_stdout_path: Path | None = None


class StudyAgentConfig(StrictModel):
    version: Literal[1]
    profile: str | None = None
    paths: PathsConfig = Field(default_factory=PathsConfig)
    acp: ACPConfig = Field(default_factory=ACPConfig)
    mcp: MCPConfig = Field(default_factory=MCPConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    retrieval: RetrievalConfig = Field(default_factory=RetrievalConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    network: NetworkConfig = Field(default_factory=NetworkConfig)
    keeper: KeeperConfig = Field(default_factory=KeeperConfig)
    pv_copilot: ExternalServiceConfig = Field(default_factory=ExternalServiceConfig)
    demo: DemoConfig = Field(default_factory=DemoConfig)
    calibration: CalibrationConfig = Field(default_factory=CalibrationConfig)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def _reject_secrets(value: Any, path: str = "") -> None:
    if isinstance(value, dict):
        for key, inner in value.items():
            next_path = f"{path}.{key}" if path else str(key)
            if is_secret_name(str(key)):
                raise ConfigError(
                    f"Secrets are not allowed in config.yaml ({next_path}); use an environment variable."
                )
            _reject_secrets(inner, next_path)
    elif isinstance(value, list):
        for index, inner in enumerate(value):
            _reject_secrets(inner, f"{path}[{index}]")
    elif isinstance(value, str) and _SECRET_VALUE_RE.search(value):
        raise ConfigError(
            f"Secrets are not allowed in config.yaml ({path}); use an environment variable."
        )


def find_config_path(
    explicit: str | Path | None = None, *, cwd: Path | None = None
) -> Path | None:
    if explicit is not None:
        return Path(explicit).expanduser().resolve()
    configured = os.getenv(CONFIG_ENV_VAR, "").strip()
    if configured:
        return Path(configured).expanduser().resolve()
    candidate = (cwd or Path.cwd()) / DEFAULT_CONFIG_NAME
    return candidate.resolve() if candidate.is_file() else None


def _resolve_paths(config: StudyAgentConfig, source: Path) -> StudyAgentConfig:
    base = source.parent

    def resolve(value: Path | None) -> Path | None:
        if value is None or value.is_absolute():
            return value
        return (base / value).resolve()

    update = {
        "paths": config.paths.model_copy(
            update={
                "phenotype_index": resolve(config.paths.phenotype_index),
                "logs": resolve(config.paths.logs),
                "runtime": resolve(config.paths.runtime),
            }
        ),
        "acp": config.acp.model_copy(
            update={
                "mcp": config.acp.mcp.model_copy(
                    update={"cwd": resolve(config.acp.mcp.cwd)}
                ),
                "service_registry": resolve(config.acp.service_registry),
            }
        ),
        "logging": config.logging.model_copy(
            update={
                "acp_file": resolve(config.logging.acp_file),
                "mcp_file": resolve(config.logging.mcp_file),
            }
        ),
        "demo": config.demo.model_copy(
            update={"output_dir": resolve(config.demo.output_dir)}
        ),
        "calibration": config.calibration.model_copy(
            update={
                "output_env_path": resolve(config.calibration.output_env_path),
                "output_json_path": resolve(config.calibration.output_json_path),
                "mcp_stdout_path": resolve(config.calibration.mcp_stdout_path),
            }
        ),
    }
    return config.model_copy(update=update)


def load_config(
    path: str | Path | None = None,
    *,
    profile: str | None = None,
    required: bool = False,
    cwd: Path | None = None,
) -> StudyAgentConfig | None:
    source = find_config_path(path, cwd=cwd)
    if source is None:
        if required:
            raise ConfigError(
                "No config.yaml found. Pass --config or create config.yaml in the current directory."
            )
        return None
    if not source.is_file():
        raise ConfigError(f"Configuration file does not exist: {source}")
    try:
        raw = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise ConfigError(
            f"Unable to read configuration file {source}: {exc}. "
            "config.yaml contains no secrets and must be readable by the service user."
        ) from exc
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {source}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("config.yaml must contain a mapping at its top level.")
    _reject_secrets(raw)
    profiles = raw.pop("profiles", {})
    selected_profile = profile or raw.get("profile")
    if profiles and not isinstance(profiles, dict):
        raise ConfigError("profiles must be a mapping.")
    if selected_profile and selected_profile in profiles:
        overlay = profiles[selected_profile]
        if not isinstance(overlay, dict):
            raise ConfigError(f"Profile {selected_profile} must be a mapping.")
        raw = _deep_merge(raw, overlay)
    elif profile and profile != raw.get("profile"):
        raise ConfigError(f"Unknown configuration profile: {profile}")
    raw["profile"] = selected_profile
    try:
        config = StudyAgentConfig.model_validate(raw)
    except ValidationError as exc:
        raise ConfigError(f"Invalid configuration in {source}: {exc}") from exc
    return _resolve_paths(config, source)


def _env_value(value: str | int | float | bool | Path) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    return str(value)


def project_to_environment(config: StudyAgentConfig) -> dict[str, str]:
    """Map validated non-secret config to the legacy process environment API."""
    values: dict[str, str | int | float | bool | Path | None] = {
        "PHENOTYPE_INDEX_DIR": config.paths.phenotype_index,
        "STUDY_AGENT_LOG_DIR": config.paths.logs,
        "STUDY_AGENT_RUNTIME_DIR": config.paths.runtime,
        "STUDY_AGENT_HOST": config.acp.bind.host,
        "STUDY_AGENT_PORT": config.acp.bind.port,
        "ACP_TIMEOUT": config.acp.request_timeout_seconds,
        "STUDY_AGENT_MCP_URL": config.acp.mcp.url,
        "STUDY_AGENT_MCP_COMMAND": config.acp.mcp.command,
        "STUDY_AGENT_MCP_ARGS": " ".join(config.acp.mcp.args),
        "STUDY_AGENT_MCP_CWD": config.acp.mcp.cwd,
        "STUDY_AGENT_MCP_TIMEOUT": config.acp.mcp.timeout_seconds,
        "STUDY_AGENT_MCP_ONESHOT": config.acp.mcp.oneshot,
        "STUDY_AGENT_ALLOW_CORE_FALLBACK": config.acp.allow_core_fallback,
        "STUDY_AGENT_DEBUG": config.acp.debug,
        "STUDY_AGENT_THREADING": config.acp.threaded,
        "STUDY_AGENT_HEALTH_DEEP": config.acp.health_deep,
        "STUDY_AGENT_SERVICE_REGISTRY": config.acp.service_registry,
        "MCP_TRANSPORT": config.mcp.transport,
        "MCP_HOST": config.mcp.bind.host,
        "MCP_PORT": config.mcp.bind.port,
        "MCP_PATH": config.mcp.path,
        "LLM_API_URL": config.llm.api_url,
        "LLM_MODEL": config.llm.model,
        "LLM_TIMEOUT": config.llm.timeout_seconds,
        "LLM_USE_RESPONSES": config.llm.use_responses_api,
        "LLM_DRY_RUN": config.llm.dry_run,
        "LLM_LOG": config.llm.log,
        "LLM_LOG_PROMPT": config.llm.log_prompt,
        "LLM_LOG_RESPONSE": config.llm.log_response,
        "LLM_LOG_JSON": config.llm.log_json,
        "LLM_CANDIDATE_LIMIT": config.llm.candidate_limit,
        "LLM_RECOMMENDATION_TOP_K": config.llm.recommendation_top_k,
        "LLM_RECOMMENDATION_MAX_RESULTS": config.llm.recommendation_max_results,
        "LLM_PLANNING_CANDIDATE_LIMIT": config.llm.planning_candidate_limit,
        "LLM_PLANNING_TOP_BAND": config.llm.planning_top_band,
        "EMBED_URL": config.retrieval.embedding_url,
        "EMBED_MODEL": config.retrieval.embedding_model,
        "EMBED_TIMEOUT": config.retrieval.timeout_seconds,
        "EMBED_LOG": config.retrieval.log,
        "PHENOTYPE_DENSE_WEIGHT": config.retrieval.dense_weight,
        "PHENOTYPE_SPARSE_WEIGHT": config.retrieval.sparse_weight,
        "PHENOTYPE_REINDEX_ALLOW": config.retrieval.reindex_allow,
        "STUDY_AGENT_LOG_LEVEL": config.logging.level,
        "ACP_LOG_LEVEL": config.logging.acp_level,
        "MCP_LOG_LEVEL": config.logging.mcp_level,
        "STUDY_AGENT_LOG_MAX_BYTES": config.logging.max_bytes,
        "STUDY_AGENT_LOG_BACKUP_COUNT": config.logging.backup_count,
        "ACP_LOG_FILE": config.logging.acp_file,
        "MCP_LOG_FILE": config.logging.mcp_file,
        "ACP_LOG_TO_CONSOLE": config.logging.acp_to_console,
        "MCP_LOG_TO_CONSOLE": config.logging.mcp_to_console,
        "STUDY_AGENT_REWRITE_CONTAINER_HOSTS": config.network.rewrite_container_hosts,
        "STUDY_AGENT_HOST_GATEWAY": config.network.host_gateway,
        "VOCAB_SEARCH_PROVIDER": config.keeper.vocabulary.search_provider,
        "VOCAB_SEARCH_URL": config.keeper.vocabulary.search_url,
        "VOCAB_SEARCH_TIMEOUT": config.keeper.vocabulary.search_timeout_seconds,
        "VOCAB_SEARCH_QUERY_PREFIX": config.keeper.vocabulary.search_query_prefix,
        "VOCAB_SEARCH_QUERY_ID": config.keeper.vocabulary.search_query_id,
        "VOCAB_METADATA_PROVIDER": config.keeper.vocabulary.metadata_provider,
        "VOCAB_DATABASE_SCHEMA": config.keeper.vocabulary.database_schema,
        "VOCAB_CONCEPT_TABLE": config.keeper.vocabulary.concept_table,
        "PHOEBE_PROVIDER": config.keeper.phoebe.provider,
        "PHOEBE_BULK_URL": config.keeper.phoebe.bulk_url,
        "PHOEBE_TIMEOUT": config.keeper.phoebe.timeout_seconds,
        "PHOEBE_HTTP_RETRIES": config.keeper.phoebe.http_retries,
        "PHOEBE_HTTP_BACKOFF_MS": config.keeper.phoebe.http_backoff_ms,
        "PHOEBE_MAX_CONCEPTS": config.keeper.phoebe.max_concepts,
        "PHOEBE_MAX_CONCEPTS_PER_RELATIONSHIP": config.keeper.phoebe.max_concepts_per_relationship,
        "PHOEBE_RELATIONSHIP_IDS": ",".join(config.keeper.phoebe.relationship_ids)
        if config.keeper.phoebe.relationship_ids
        else None,
        "PHOEBE_DB_TABLE": config.keeper.phoebe.db_table,
        "PV_COPILOT_BASE_URL": config.pv_copilot.base_url,
        "PV_COPILOT_HOST": config.pv_copilot.host,
        "PV_COPILOT_PORT": config.pv_copilot.port,
        "PV_COPILOT_SCHEME": config.pv_copilot.scheme,
        "PV_COPILOT_API_PREFIX": config.pv_copilot.api_prefix,
        "PV_COPILOT_TIMEOUT": config.pv_copilot.timeout_seconds,
        "STUDY_AGENT_DEMO_ACP_URL": config.demo.acp_url,
        "STUDY_AGENT_DEMO_OUTPUT_DIR": config.demo.output_dir,
        "ACP_BASE_URL": config.calibration.acp_base_url,
        "TIMEOUT_CALIBRATION_RUNS": config.calibration.runs,
        "TIMEOUT_CALIBRATION_CANDIDATE_LIMITS": ",".join(
            map(str, config.calibration.candidate_limits)
        )
        if config.calibration.candidate_limits
        else None,
        "TIMEOUT_CALIBRATION_ENV_PATH": config.calibration.output_env_path,
        "TIMEOUT_CALIBRATION_JSON_PATH": config.calibration.output_json_path,
        "MCP_STDOUT": config.calibration.mcp_stdout_path,
    }
    return {
        name: _env_value(value) for name, value in values.items() if value is not None
    }


def apply_config(config: StudyAgentConfig) -> dict[str, str]:
    """Apply non-secret values with config precedence over legacy environment values."""
    values = project_to_environment(config)
    os.environ.update(values)
    return values


def redacted_diagnostics(config: StudyAgentConfig) -> dict[str, Any]:
    return {
        "version": config.version,
        "profile": config.profile,
        "config_contains_secrets": False,
        "settings": project_to_environment(config),
    }
