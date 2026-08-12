# Current Sprint Plan

1. Define the configuration contract

  Create a versioned schema and a checked-in config.example.yaml. Keep generated config.yaml ignored, because it will be deployment-specific even though it contains no secrets.

  Use config-relative paths. For example, data/phenotype_index resolves relative to the configuration file, not the process working directory. This is the key Windows/Linux
  portability improvement.

  Separate ACP’s bind address from its public URL, and MCP’s bind address from ACP’s MCP URL. Docker needs internal service names, while host users need loopback URLs.

  2. Build a shared Python configuration layer

  Add core/study_agent_core/config.py that:

  - Locates the configuration through --config, then an optional STUDY_AGENT_CONFIG bootstrap variable, then ./config.yaml.
  - Validates YAML with Pydantic models.
  - Resolves relative paths safely.
  - Rejects secret values and unknown keys.
  - Provides redacted diagnostic output.
  - Supports native and docker profiles or explicit profile overlays.

  The configuration path is the one acceptable non-secret environment/bootstrap value during migration; a CLI --config flag is preferred where practical.

  3. Use startup wrappers before importing service modules

  This is an important implementation detail. MCP currently constructs FastMCP at module import time, so configuration must be loaded before importing study_agent_mcp.server.

  Introduce thin CLI entrypoint wrappers for ACP and MCP that parse --config and --profile, load configuration, and then import/start the service. The MCP package’s current import
  side effect should be made lazy to permit that ordering.

  For the first compatibility release, the loader can project validated non-secret YAML values into the existing legacy environment names before service imports. That avoids a risky
  simultaneous refactor of every configuration read.

  Precedence should be:

  1. Explicit CLI values
  2. config.yaml
  3. Secret environment variables
  4. Legacy non-secret environment variables, only as a documented compatibility fallback
  5. Built-in defaults

  When config.yaml is present, it should win over legacy non-secret variables so a stale shell environment cannot silently override deployment configuration.

  4. Migrate call sites incrementally

  Refactor Python modules from os.getenv() to the shared typed configuration object by area:

  - ACP and MCP startup/connection modes
  - LLM and retrieval configuration
  - Logging and network rewriting
  - Keeper, vocabulary, PHOEBE, and external-service endpoints
  - Demo shell and indexing scripts
  - Test/calibration tools, where CLI flags should replace one-off operational variables

  Keep secret retrieval isolated in a small secrets adapter rather than distributing direct environment reads throughout the codebase.

  5. Update Docker Compose and the setup wizard

  Compose should mount the YAML file read-only, for example at /app/config.yaml, and invoke service CLI wrappers with that path and the docker profile.

  Move .env to a secret-only compatibility file—or rename it to secrets.env to make its role unambiguous. Docker Compose may still use it as an env_file; it simply must not carry
  ordinary deployment settings anymore.

  Update study-agent-setup to write:

  - config.yaml containing only ordinary configuration
  - optionally secrets.env, with hidden-input secrets and restrictive permissions

  Add an explicit migration option for existing .env files. It should classify known keys, move only non-secrets into YAML, preserve secret values without displaying them, and require
  confirmation before replacing files.

  6. Test and deprecate safely

  Add tests for:

  - Schema validation, defaults, profiles, and path resolution
  - YAML never serializing secret values
  - Python startup with --config in HTTP and stdio MCP modes
  - ACP-to-managed-MCP configuration propagation
  - Docker mount/profile behavior
  - Native Windows CI coverage for path behavior
  - Legacy environment-only startup remaining functional

  Deprecation should be gradual:

  - Release 1: YAML supported; legacy environment configuration works unchanged.
  - Release 2: warn when non-secret legacy variables configure a service.
  - Release 3: remove legacy non-secret configuration only after deployments have migrated.

  The largest technical risk is startup ordering, especially MCP’s module-level initialization, plus keeping Python and R interpretation of paths/profiles identical. A shared schema,
  configuration-relative paths, CLI-first loading, and a temporary compatibility adapter keep that risk controlled.
