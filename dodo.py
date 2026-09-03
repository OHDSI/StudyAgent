from __future__ import annotations

import json
import os
import socket
import sys
import subprocess
import time
from pathlib import Path
import urllib.error
import urllib.request
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parent


def _yaml_environment() -> dict[str, str]:
    """Load non-secret settings from config.yaml without requiring it."""
    from study_agent_core.config import load_config, project_to_environment

    config = load_config(cwd=REPO_ROOT)
    return project_to_environment(config) if config is not None else {}


def _secret_environment() -> dict[str, str]:
    """Load wizard-generated secrets.env without exposing its values."""
    from study_agent_core.config import load_secret_environment

    return load_secret_environment(cwd=REPO_ROOT)


# Environment-only setups remain supported; config.yaml values take precedence.
CONFIG_ENV = _yaml_environment()
DEFAULT_ENV = {
    "PHENOTYPE_INDEX_DIR": "data/phenotype_index",
    "PHENOTYPE_DENSE_WEIGHT": "0.9",
    "PHENOTYPE_SPARSE_WEIGHT": "0.1",
    "EMBED_URL": "http://localhost:3000/ollama/api/embed",
    "EMBED_MODEL": "qwen3-embedding:4b",
    "LLM_API_URL": "http://localhost:3000/api/chat/completions",
    "LLM_MODEL": "gemma3:4b",
    "LLM_TIMEOUT": "240",
    "LLM_LOG": "1",
    "LLM_LOG_PROMPT": "0",
    "LLM_LOG_RESPONSE": "0",
    "LLM_LOG_JSON": "0",
    "LLM_DRY_RUN": "0",
    "LLM_USE_RESPONSES": "0",
    "LLM_CANDIDATE_LIMIT": "5",
    "LLM_RECOMMENDATION_MAX_RESULTS": "3",
    "LLM_RECOMMENDATION_TOP_K": "20",
    "EMBED_TIMEOUT": "120",
    "STUDY_AGENT_MCP_TIMEOUT": "240",
    "ACP_TIMEOUT": "360",
    "STUDY_AGENT_HOST": "127.0.0.1",
    "STUDY_AGENT_PORT": "8765",
}


LOCAL_SMOKE_TASKS = [
    "smoke_phenotype_recommend_flow",
    "smoke_phenotype_intent_split_flow",
    "smoke_phenotype_recommendation_advice_flow",
    "smoke_phenotype_improvements_flow",
    "smoke_concept_sets_review_flow",
    "smoke_cohort_critique_flow",
    "smoke_case_causal_review_flow",
    "smoke_cohort_methods_intent_split_flow",
    "smoke_cohort_methods_specs_recommend_flow",
    "smoke_phenotype_validation_review_flow",
    "smoke_keeper_concept_sets_generate_flow",
    "smoke_phenotype_make_computable_flow",
    "smoke_phenotype_make_computable_proposal_flow",
]


def _runtime_env() -> dict[str, str]:
    env = _secret_environment()
    # Explicit shell/service-manager values override secrets.env.
    env.update(os.environ)
    for key, value in DEFAULT_ENV.items():
        env.setdefault(key, value)
    env.update(CONFIG_ENV)
    return env



def _require_llm_api_key(env: dict[str, str]) -> None:
    if env.get("LLM_AUTHENTICATION", "required").strip().lower() == "none":
        return
    if not env.get("LLM_API_KEY"):
        raise RuntimeError(
            "LLM_API_KEY is required for this smoke task. Set it in the process "
            "environment or repository-local secrets.env before running the task."
        )

def _runtime_dir(env: dict[str, str]) -> Path:
    path = Path(env.get("STUDY_AGENT_RUNTIME_DIR", REPO_ROOT / ".study-agent-runtime"))
    path.mkdir(parents=True, exist_ok=True)
    return path


def _runtime_file(env: dict[str, str], env_name: str, filename: str) -> Path:
    configured = env.get(env_name)
    return Path(configured) if configured else _runtime_dir(env) / filename


def _acp_base_url(env: dict[str, str]) -> str:
    return env.get(
        "ACP_BASE_URL", f"http://{env['STUDY_AGENT_HOST']}:{env['STUDY_AGENT_PORT']}"
    ).rstrip("/")


def _health_url(env: dict[str, str]) -> str:
    return f"{_acp_base_url(env)}/health"


def _flow_url(env: dict[str, str], flow: str) -> str:
    return f"{_acp_base_url(env)}/flows/{flow}"


def _pytest_cmd(marker: str | None = None) -> str:
    opts = os.getenv("PYTEST_OPTS", "")
    base = "pytest"
    if marker:
        base = f'{base} -m "{marker}"'
    if opts:
        return f"{base} {opts}"
    return base


def _start_mcp_http_if_needed(env: dict) -> subprocess.Popen | None:
    url = env.get("STUDY_AGENT_MCP_URL")
    if not url:
        return None
    if env.get("STUDY_AGENT_MCP_MANAGED", "1") != "1":
        return None
    parsed = urlparse(url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8790
    path = parsed.path or "/mcp"
    env.setdefault("MCP_TRANSPORT", "http")
    env.setdefault("MCP_HOST", host)
    env.setdefault("MCP_PORT", str(port))
    env.setdefault("MCP_PATH", path)
    mcp_stdout = _runtime_file(env, "MCP_STDOUT", "study_agent_mcp_stdout.log")
    mcp_stderr = _runtime_file(env, "MCP_STDERR", "study_agent_mcp_stderr.log")
    print(f"Starting MCP over HTTP at {host}:{port}{path}...")
    with (
        open(mcp_stdout, "w", encoding="utf-8") as out,
        open(mcp_stderr, "w", encoding="utf-8") as err,
    ):
        proc = subprocess.Popen(["study-agent-mcp"], env=env, stdout=out, stderr=err)
    timeout_s = int(env.get("MCP_START_TIMEOUT", "10"))
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=1):
                time.sleep(0.5)
                if proc.poll() is not None:
                    raise RuntimeError(
                        f"MCP exited during startup; inspect {mcp_stdout} and {mcp_stderr}. "
                        "The requested MCP port may already be in use."
                    )
                return proc
        except OSError:
            time.sleep(0.5)
    print(f"Warning: MCP did not open {host}:{port} within {timeout_s}s")
    return proc


def _wait_for_acp(url: str, timeout_s: int = 30, require_mcp: bool = False) -> None:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    if not require_mcp:
                        return
                    body = json.loads(response.read().decode("utf-8"))
                    mcp_ok = (
                        isinstance(body.get("mcp"), dict)
                        and body.get("mcp", {}).get("ok") is True
                    )
                    if mcp_ok:
                        return
        except Exception:
            time.sleep(0.5)
    raise RuntimeError(f"ACP did not become ready at {url}")


def task_install():
    return {
        "actions": ["pip install -e ."],
        "verbosity": 2,
    }


def task_test_core():
    return {
        "actions": [_pytest_cmd("core")],
        "verbosity": 2,
    }


def task_test_acp():
    return {
        "actions": [_pytest_cmd("acp")],
        "verbosity": 2,
    }


def task_test_mcp():
    return {
        "actions": [_pytest_cmd("mcp")],
        "verbosity": 2,
    }


def task_test_unit():
    return {
        "actions": None,
        "task_dep": ["test_core", "test_acp", "test_mcp"],
    }


def task_test_all():
    """Run the native Python ACP/MCP test gate, excluding R packages."""
    return {
        "actions": [_pytest_cmd("not r_client_compatibility")],
        "verbosity": 2,
    }


def task_test_r_client_compatibility():
    """Check external companion R-client packages in the configured R library."""
    return {
        "actions": [_pytest_cmd("r_client_compatibility")],
        "verbosity": 2,
    }


def task_run_all():
    return {
        "actions": None,
        "task_dep": ["test_all"],
    }


def task_run_smoke_suite():
    """Run all configured local ACP/MCP smoke flows."""
    return {
        "actions": None,
        "task_dep": LOCAL_SMOKE_TASKS,
    }


def task_run_external_smoke_suite():
    """Run the local smoke suite plus opt-in external integrations."""
    return {
        "actions": None,
        "task_dep": ["run_smoke_suite", "smoke_hecate_phoebe_bulk_endpoint"],
    }


def task_calibrate_timeouts():
    def _run_calibration() -> None:
        env = _runtime_env()
        _require_llm_api_key(env)
        if not env.get("STUDY_AGENT_MCP_URL"):
            env.setdefault("STUDY_AGENT_MCP_COMMAND", "study-agent-mcp")
            env.setdefault("STUDY_AGENT_MCP_ARGS", "")
        env.setdefault("LLM_LOG", "1")
        env.setdefault("LLM_LOG_PROMPT", "0")
        env.setdefault("LLM_LOG_RESPONSE", "0")
        env.setdefault("STUDY_AGENT_DEBUG", "1")
        env.setdefault("EMBED_LOG", "1")
        env.setdefault("TIMEOUT_CALIBRATION_RUNS", "3")
        env.setdefault("TIMEOUT_CALIBRATION_CANDIDATE_LIMITS", "3,5,8")
        env.setdefault(
            "TIMEOUT_CALIBRATION_ENV_PATH",
            str(
                _runtime_file(
                    env, "TIMEOUT_CALIBRATION_ENV_PATH", "timeout_recommendations.env"
                )
            ),
        )
        env.setdefault(
            "TIMEOUT_CALIBRATION_JSON_PATH",
            str(
                _runtime_file(
                    env, "TIMEOUT_CALIBRATION_JSON_PATH", "timeout_recommendations.json"
                )
            ),
        )

        acp_stdout = _runtime_file(env, "ACP_STDOUT", "study_agent_acp_stdout.log")
        acp_stderr = _runtime_file(env, "ACP_STDERR", "study_agent_acp_stderr.log")
        mcp_proc = _start_mcp_http_if_needed(env)
        print("Starting ACP for timeout calibration...")
        with (
            open(acp_stdout, "w", encoding="utf-8") as out,
            open(acp_stderr, "w", encoding="utf-8") as err,
        ):
            acp_proc = subprocess.Popen(
                ["study-agent-acp"], env=env, stdout=out, stderr=err
            )
        try:
            print("Waiting for ACP health endpoint...")
            require_mcp = bool(
                env.get("STUDY_AGENT_MCP_URL") or env.get("STUDY_AGENT_MCP_COMMAND")
            )
            _wait_for_acp(_health_url(env), timeout_s=30, require_mcp=require_mcp)
            print("Running timeout calibration...")
            subprocess.run(
                [sys.executable, "scripts/calibrate_timeouts.py"], check=True, env=env
            )
            print(f"ACP logs: {acp_stdout} {acp_stderr}")
            print(f"Recommended env: {env['TIMEOUT_CALIBRATION_ENV_PATH']}")
            print(f"Calibration details: {env['TIMEOUT_CALIBRATION_JSON_PATH']}")
        finally:
            print("Stopping ACP...")
            acp_proc.terminate()
            try:
                acp_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                acp_proc.kill()
            if mcp_proc is not None:
                print("Stopping MCP...")
                mcp_proc.terminate()
                try:
                    mcp_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    mcp_proc.kill()

    return {
        "actions": [_run_calibration],
        "verbosity": 2,
    }


def task_check_llm_connectivity():
    def _run_check() -> None:
        env = _runtime_env()
        _require_llm_api_key(env)

        url = env["LLM_API_URL"]
        model = env["LLM_MODEL"]
        use_responses = env.get("LLM_USE_RESPONSES", "0") == "1"

        if use_responses:
            payload = json.dumps(
                {
                    "model": model,
                    "input": "What we have here is a failure to communicate!.",
                    "temperature": 0,
                }
            )
        else:
            payload = json.dumps(
                {
                    "model": model,
                    "messages": [{"role": "user", "content": "Tau Ceti here we ."}],
                    "temperature": 0,
                }
            )

        cmd = [
            "curl",
            "-sS",
            "-X",
            "POST",
            url,
            "-H",
            "Content-Type: application/json",
        ]
        if env.get("LLM_AUTHENTICATION", "required").strip().lower() != "none":
            cmd.extend(["-H", f"Authorization: Bearer {env['LLM_API_KEY']}"])
        cmd.extend(["-d", payload])
        print("Running LLM connectivity check...")
        subprocess.run(cmd, check=True)

    return {
        "actions": [_run_check],
        "verbosity": 2,
    }


def task_list_services():
    def _run_list() -> None:
        env = _runtime_env()
        host = env.get("STUDY_AGENT_HOST", DEFAULT_ENV["STUDY_AGENT_HOST"])
        port = env.get("STUDY_AGENT_PORT", DEFAULT_ENV["STUDY_AGENT_PORT"])
        url = env.get("ACP_BASE_URL", f"http://{host}:{port}")
        if url.endswith("/"):
            url = url[:-1]

        acp_proc = None
        mcp_proc = None
        try:
            try:
                _wait_for_acp(f"{url}/health", timeout_s=3)
            except Exception:
                if not env.get("STUDY_AGENT_MCP_URL"):
                    env.setdefault("STUDY_AGENT_MCP_COMMAND", "study-agent-mcp")
                    env.setdefault("STUDY_AGENT_MCP_ARGS", "")
                mcp_proc = _start_mcp_http_if_needed(env)
                acp_stdout = _runtime_file(
                    env, "ACP_STDOUT", "study_agent_acp_stdout.log"
                )
                acp_stderr = _runtime_file(
                    env, "ACP_STDERR", "study_agent_acp_stderr.log"
                )
                print("Starting ACP to list services...")
                with (
                    open(acp_stdout, "w", encoding="utf-8") as out,
                    open(acp_stderr, "w", encoding="utf-8") as err,
                ):
                    acp_proc = subprocess.Popen(
                        ["study-agent-acp"], env=env, stdout=out, stderr=err
                    )
                require_mcp = bool(
                    env.get("STUDY_AGENT_MCP_URL") or env.get("STUDY_AGENT_MCP_COMMAND")
                )
                _wait_for_acp(f"{url}/health", timeout_s=15, require_mcp=require_mcp)

            req = urllib.request.Request(f"{url}/services")
            with urllib.request.urlopen(req, timeout=10) as response:
                body = response.read().decode("utf-8")
            print(body)
        finally:
            if acp_proc is not None:
                print("Stopping ACP...")
                acp_proc.terminate()
                try:
                    acp_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    acp_proc.kill()
            if mcp_proc is not None:
                print("Stopping MCP...")
                mcp_proc.terminate()
                try:
                    mcp_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    mcp_proc.kill()

    return {
        "actions": [_run_list],
        "verbosity": 2,
    }


def task_smoke_phenotype_recommend_flow():
    def _run_smoke() -> None:
        env = _runtime_env()
        _require_llm_api_key(env)
        if not env.get("STUDY_AGENT_MCP_URL"):
            env.setdefault("STUDY_AGENT_MCP_COMMAND", "study-agent-mcp")
            env.setdefault("STUDY_AGENT_MCP_ARGS", "")
        env.setdefault("LLM_LOG", "1")
        env.setdefault("LLM_LOG_PROMPT", "1")
        env.setdefault("LLM_LOG_RESPONSE", "1")
        env["ACP_URL"] = _flow_url(env, "phenotype_recommendation")

        acp_stdout = _runtime_file(env, "ACP_STDOUT", "study_agent_acp_stdout.log")
        acp_stderr = _runtime_file(env, "ACP_STDERR", "study_agent_acp_stderr.log")
        mcp_proc = _start_mcp_http_if_needed(env)
        print("Starting ACP...")
        with (
            open(acp_stdout, "w", encoding="utf-8") as out,
            open(acp_stderr, "w", encoding="utf-8") as err,
        ):
            acp_proc = subprocess.Popen(
                ["study-agent-acp"], env=env, stdout=out, stderr=err
            )
        try:
            print("Waiting for ACP health endpoint...")
            require_mcp = bool(
                env.get("STUDY_AGENT_MCP_URL") or env.get("STUDY_AGENT_MCP_COMMAND")
            )
            _wait_for_acp(_health_url(env), timeout_s=30, require_mcp=require_mcp)
            print("Running phenotype flow smoke test...")
            subprocess.run(
                [sys.executable, "tests/smoke_phenotype_flow.py"], check=True, env=env
            )
            print(f"ACP logs: {acp_stdout} {acp_stderr}")
        finally:
            print("Stopping ACP...")
            acp_proc.terminate()
            try:
                acp_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                acp_proc.kill()
            if mcp_proc is not None:
                print("Stopping MCP...")
                mcp_proc.terminate()
                try:
                    mcp_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    mcp_proc.kill()

    return {
        "actions": [_run_smoke],
        "verbosity": 2,
    }


def task_smoke_phenotype_make_computable_flow():
    """Exercise ACP routing, MCP transport, Capr emission, and R/Circe validation."""

    def _run_smoke() -> None:
        env = _runtime_env()
        if not env.get("STUDY_AGENT_MCP_URL"):
            env.setdefault("STUDY_AGENT_MCP_COMMAND", "study-agent-mcp")
            env.setdefault("STUDY_AGENT_MCP_ARGS", "")
        env["ACP_URL"] = _flow_url(env, "phenotype_make_computable")

        acp_stdout = _runtime_file(env, "ACP_STDOUT", "study_agent_acp_stdout.log")
        acp_stderr = _runtime_file(env, "ACP_STDERR", "study_agent_acp_stderr.log")
        mcp_proc = _start_mcp_http_if_needed(env)
        print("Starting ACP...")
        with (
            open(acp_stdout, "w", encoding="utf-8") as out,
            open(acp_stderr, "w", encoding="utf-8") as err,
        ):
            acp_proc = subprocess.Popen(
                ["study-agent-acp"], env=env, stdout=out, stderr=err
            )
        try:
            print("Waiting for ACP health endpoint...")
            require_mcp = bool(
                env.get("STUDY_AGENT_MCP_URL") or env.get("STUDY_AGENT_MCP_COMMAND")
            )
            _wait_for_acp(_health_url(env), timeout_s=30, require_mcp=require_mcp)
            print("Running computable phenotype workflow smoke test...")
            subprocess.run(
                [sys.executable, "tests/smoke_phenotype_make_computable_flow.py"],
                check=True,
                env=env,
            )
            print(f"ACP logs: {acp_stdout} {acp_stderr}")
        finally:
            print("Stopping ACP...")
            acp_proc.terminate()
            try:
                acp_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                acp_proc.kill()
            if mcp_proc is not None:
                print("Stopping MCP...")
                mcp_proc.terminate()
                try:
                    mcp_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    mcp_proc.kill()

    return {
        "actions": [_run_smoke],
        "verbosity": 2,
    }



def task_smoke_phenotype_make_computable_proposal_flow():
    """Exercise vocabulary retrieval and the live LLM proposal contract."""

    def _run_smoke() -> None:
        env = _runtime_env()
        _require_llm_api_key(env)
        if not env.get("STUDY_AGENT_MCP_URL"):
            env.setdefault("STUDY_AGENT_MCP_COMMAND", "study-agent-mcp")
            env.setdefault("STUDY_AGENT_MCP_ARGS", "")
        env["ACP_URL"] = _flow_url(env, "phenotype_make_computable")

        acp_stdout = _runtime_file(env, "ACP_STDOUT", "study_agent_acp_stdout.log")
        acp_stderr = _runtime_file(env, "ACP_STDERR", "study_agent_acp_stderr.log")
        mcp_proc = _start_mcp_http_if_needed(env)
        print("Starting ACP...")
        with (
            open(acp_stdout, "w", encoding="utf-8") as out,
            open(acp_stderr, "w", encoding="utf-8") as err,
        ):
            acp_proc = subprocess.Popen(
                ["study-agent-acp"], env=env, stdout=out, stderr=err
            )
        try:
            print("Waiting for ACP health endpoint...")
            require_mcp = bool(
                env.get("STUDY_AGENT_MCP_URL") or env.get("STUDY_AGENT_MCP_COMMAND")
            )
            _wait_for_acp(_health_url(env), timeout_s=30, require_mcp=require_mcp)
            print("Running computable phenotype proposal smoke test...")
            time.sleep(0.5)
            if acp_proc.poll() is not None:
                raise RuntimeError(
                    f"ACP exited during startup; inspect {acp_stdout} and {acp_stderr}. "
                    "The requested ACP port may already be in use."
                )
            subprocess.run(
                [sys.executable, "tests/smoke_phenotype_make_computable_proposal_flow.py"],
                check=True,
                env=env,
            )
            print(f"ACP logs: {acp_stdout} {acp_stderr}")
        finally:
            print("Stopping ACP...")
            acp_proc.terminate()
            try:
                acp_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                acp_proc.kill()
            if mcp_proc is not None:
                print("Stopping MCP...")
                mcp_proc.terminate()
                try:
                    mcp_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    mcp_proc.kill()
            print(f"ACP logs: {acp_stdout} {acp_stderr}")
            if mcp_proc is not None:
                print(
                    "MCP logs: "
                    f"{_runtime_file(env, 'MCP_STDOUT', 'study_agent_mcp_stdout.log')} "
                    f"{_runtime_file(env, 'MCP_STDERR', 'study_agent_mcp_stderr.log')}"
                )

    return {
        "actions": [_run_smoke],
        "verbosity": 2,
    }



def task_smoke_cohort_methods_specs_recommend_flow():
    def _run_smoke() -> None:
        env = _runtime_env()
        _require_llm_api_key(env)
        if not env.get("STUDY_AGENT_MCP_URL"):
            env.setdefault("STUDY_AGENT_MCP_COMMAND", "study-agent-mcp")
            env.setdefault("STUDY_AGENT_MCP_ARGS", "")
        env.setdefault("LLM_LOG", "1")
        env.setdefault("LLM_LOG_PROMPT", "1")
        env.setdefault("LLM_LOG_RESPONSE", "1")
        env["ACP_URL"] = _flow_url(env, "cohort_methods_specifications_recommendation")

        acp_stdout = _runtime_file(env, "ACP_STDOUT", "study_agent_acp_stdout.log")
        acp_stderr = _runtime_file(env, "ACP_STDERR", "study_agent_acp_stderr.log")
        mcp_proc = _start_mcp_http_if_needed(env)
        print("Starting ACP...")
        with (
            open(acp_stdout, "w", encoding="utf-8") as out,
            open(acp_stderr, "w", encoding="utf-8") as err,
        ):
            acp_proc = subprocess.Popen(
                ["study-agent-acp"], env=env, stdout=out, stderr=err
            )
        try:
            print("Waiting for ACP health endpoint...")
            require_mcp = bool(
                env.get("STUDY_AGENT_MCP_URL") or env.get("STUDY_AGENT_MCP_COMMAND")
            )
            _wait_for_acp(_health_url(env), timeout_s=30, require_mcp=require_mcp)
            print("Running cohort-methods-specs flow smoke test...")
            subprocess.run(
                [sys.executable, "tests/smoke_cohort_methods_specs_flow.py"],
                check=True,
                env=env,
            )
            print(f"ACP logs: {acp_stdout} {acp_stderr}")
        finally:
            print("Stopping ACP...")
            acp_proc.terminate()
            try:
                acp_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                acp_proc.kill()
            if mcp_proc is not None:
                print("Stopping MCP...")
                mcp_proc.terminate()
                try:
                    mcp_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    mcp_proc.kill()

    return {
        "actions": [_run_smoke],
        "verbosity": 2,
    }


def task_smoke_phenotype_intent_split_flow():
    def _run_smoke() -> None:
        env = _runtime_env()
        _require_llm_api_key(env)
        if not env.get("STUDY_AGENT_MCP_URL"):
            env.setdefault("STUDY_AGENT_MCP_COMMAND", "study-agent-mcp")
            env.setdefault("STUDY_AGENT_MCP_ARGS", "")
        env.setdefault("LLM_LOG", "1")
        env.setdefault("LLM_LOG_PROMPT", "1")
        env.setdefault("LLM_LOG_RESPONSE", "1")
        env["ACP_URL"] = _flow_url(env, "phenotype_intent_split")

        acp_stdout = _runtime_file(env, "ACP_STDOUT", "study_agent_acp_stdout.log")
        acp_stderr = _runtime_file(env, "ACP_STDERR", "study_agent_acp_stderr.log")
        mcp_proc = _start_mcp_http_if_needed(env)
        print("Starting ACP...")
        with (
            open(acp_stdout, "w", encoding="utf-8") as out,
            open(acp_stderr, "w", encoding="utf-8") as err,
        ):
            acp_proc = subprocess.Popen(
                ["study-agent-acp"], env=env, stdout=out, stderr=err
            )
        try:
            print("Waiting for ACP health endpoint...")
            require_mcp = bool(
                env.get("STUDY_AGENT_MCP_URL") or env.get("STUDY_AGENT_MCP_COMMAND")
            )
            _wait_for_acp(_health_url(env), timeout_s=30, require_mcp=require_mcp)
            print("Running phenotype intent split flow smoke test...")
            subprocess.run(
                [sys.executable, "tests/smoke_phenotype_intent_split.py"],
                check=True,
                env=env,
            )
            print(f"ACP logs: {acp_stdout} {acp_stderr}")
        finally:
            print("Stopping ACP...")
            acp_proc.terminate()
            try:
                acp_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                acp_proc.kill()
            if mcp_proc is not None:
                print("Stopping MCP...")
                mcp_proc.terminate()
                try:
                    mcp_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    mcp_proc.kill()

    return {
        "actions": [_run_smoke],
        "verbosity": 2,
    }


def task_smoke_cohort_methods_intent_split_flow():
    def _run_smoke() -> None:
        env = _runtime_env()
        _require_llm_api_key(env)
        if not env.get("STUDY_AGENT_MCP_URL"):
            env.setdefault("STUDY_AGENT_MCP_COMMAND", "study-agent-mcp")
            env.setdefault("STUDY_AGENT_MCP_ARGS", "")
        env.setdefault("LLM_LOG", "1")
        env.setdefault("LLM_LOG_PROMPT", "1")
        env.setdefault("LLM_LOG_RESPONSE", "1")
        env["ACP_URL"] = _flow_url(env, "cohort_methods_intent_split")

        acp_stdout = _runtime_file(env, "ACP_STDOUT", "study_agent_acp_stdout.log")
        acp_stderr = _runtime_file(env, "ACP_STDERR", "study_agent_acp_stderr.log")
        mcp_proc = _start_mcp_http_if_needed(env)
        print("Starting ACP...")
        with (
            open(acp_stdout, "w", encoding="utf-8") as out,
            open(acp_stderr, "w", encoding="utf-8") as err,
        ):
            acp_proc = subprocess.Popen(
                ["study-agent-acp"], env=env, stdout=out, stderr=err
            )
        try:
            print("Waiting for ACP health endpoint...")
            require_mcp = bool(
                env.get("STUDY_AGENT_MCP_URL") or env.get("STUDY_AGENT_MCP_COMMAND")
            )
            _wait_for_acp(_health_url(env), timeout_s=30, require_mcp=require_mcp)
            print("Running cohort methods intent split flow smoke test...")
            subprocess.run(
                [sys.executable, "tests/smoke_cohort_methods_intent_split.py"],
                check=True,
                env=env,
            )
            print(f"ACP logs: {acp_stdout} {acp_stderr}")
        finally:
            print("Stopping ACP...")
            acp_proc.terminate()
            try:
                acp_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                acp_proc.kill()
            if mcp_proc is not None:
                print("Stopping MCP...")
                mcp_proc.terminate()
                try:
                    mcp_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    mcp_proc.kill()

    return {
        "actions": [_run_smoke],
        "verbosity": 2,
    }


def task_smoke_phenotype_improvements_flow():
    def _run_smoke() -> None:
        env = _runtime_env()
        _require_llm_api_key(env)
        if not env.get("STUDY_AGENT_MCP_URL"):
            env.setdefault("STUDY_AGENT_MCP_COMMAND", "study-agent-mcp")
            env.setdefault("STUDY_AGENT_MCP_ARGS", "")

        acp_stdout = _runtime_file(env, "ACP_STDOUT", "study_agent_acp_stdout.log")
        acp_stderr = _runtime_file(env, "ACP_STDERR", "study_agent_acp_stderr.log")
        mcp_proc = _start_mcp_http_if_needed(env)
        print("Starting ACP...")
        with (
            open(acp_stdout, "w", encoding="utf-8") as out,
            open(acp_stderr, "w", encoding="utf-8") as err,
        ):
            acp_proc = subprocess.Popen(
                ["study-agent-acp"], env=env, stdout=out, stderr=err
            )
        try:
            print("Waiting for ACP health endpoint...")
            require_mcp = bool(
                env.get("STUDY_AGENT_MCP_URL") or env.get("STUDY_AGENT_MCP_COMMAND")
            )
            _wait_for_acp(_health_url(env), timeout_s=30, require_mcp=require_mcp)
            print("Running phenotype improvements flow smoke test...")
            protocol_text = (REPO_ROOT / "tests" / "demo-data" / "protocol.md").read_text(
                encoding="utf-8"
            )
            cohort = json.loads(
                (REPO_ROOT / "tests" / "demo-data" / "test_git_event_cohort.json").read_text(
                    encoding="utf-8"
                )
            )
            payload = json.dumps(
                {
                    "protocol_text": protocol_text,
                    "cohorts": [cohort],
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                _flow_url(env, "phenotype_improvements"),
                data=payload,
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(
                    req, timeout=int(env.get("ACP_TIMEOUT", "180"))
                ) as response:
                    body = response.read().decode("utf-8")
                    print(body)
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8")
                print(body)
                raise
            print(f"ACP logs: {acp_stdout} {acp_stderr}")
        finally:
            print("Stopping ACP...")
            acp_proc.terminate()
            try:
                acp_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                acp_proc.kill()
            if mcp_proc is not None:
                print("Stopping MCP...")
                mcp_proc.terminate()
                try:
                    mcp_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    mcp_proc.kill()

    return {
        "actions": [_run_smoke],
        "verbosity": 2,
    }


def task_smoke_phenotype_recommendation_advice_flow():
    def _run_smoke() -> None:
        env = _runtime_env()
        _require_llm_api_key(env)
        if not env.get("STUDY_AGENT_MCP_URL"):
            env.setdefault("STUDY_AGENT_MCP_COMMAND", "study-agent-mcp")
            env.setdefault("STUDY_AGENT_MCP_ARGS", "")
        env.setdefault("LLM_LOG", "1")

        acp_stdout = _runtime_file(env, "ACP_STDOUT", "study_agent_acp_stdout.log")
        acp_stderr = _runtime_file(env, "ACP_STDERR", "study_agent_acp_stderr.log")
        mcp_proc = _start_mcp_http_if_needed(env)
        print("Starting ACP...")
        with (
            open(acp_stdout, "w", encoding="utf-8") as out,
            open(acp_stderr, "w", encoding="utf-8") as err,
        ):
            acp_proc = subprocess.Popen(
                ["study-agent-acp"], env=env, stdout=out, stderr=err
            )
        try:
            print("Waiting for ACP health endpoint...")
            require_mcp = bool(
                env.get("STUDY_AGENT_MCP_URL") or env.get("STUDY_AGENT_MCP_COMMAND")
            )
            _wait_for_acp(_health_url(env), timeout_s=30, require_mcp=require_mcp)
            print("Running phenotype recommendation advice flow smoke test...")
            subprocess.run(
                [sys.executable, "tests/smoke_phenotype_recommendation_advice.py"],
                check=True,
                env=env,
            )
        finally:
            print("Stopping ACP...")
            acp_proc.terminate()
            try:
                acp_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                acp_proc.kill()
            if mcp_proc is not None:
                print("Stopping MCP...")
                mcp_proc.terminate()
                try:
                    mcp_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    mcp_proc.kill()

    return {
        "actions": [_run_smoke],
        "verbosity": 2,
    }


def task_smoke_concept_sets_review_flow():
    def _run_smoke() -> None:
        env = _runtime_env()
        _require_llm_api_key(env)
        if not env.get("STUDY_AGENT_MCP_URL"):
            env.setdefault("STUDY_AGENT_MCP_COMMAND", "study-agent-mcp")
            env.setdefault("STUDY_AGENT_MCP_ARGS", "")
        env.setdefault("LLM_LOG", "1")

        acp_stdout = _runtime_file(env, "ACP_STDOUT", "study_agent_acp_stdout.log")
        acp_stderr = _runtime_file(env, "ACP_STDERR", "study_agent_acp_stderr.log")
        mcp_proc = _start_mcp_http_if_needed(env)
        print("Starting ACP...")
        with (
            open(acp_stdout, "w", encoding="utf-8") as out,
            open(acp_stderr, "w", encoding="utf-8") as err,
        ):
            acp_proc = subprocess.Popen(
                ["study-agent-acp"], env=env, stdout=out, stderr=err
            )
        try:
            print("Waiting for ACP health endpoint...")
            require_mcp = bool(
                env.get("STUDY_AGENT_MCP_URL") or env.get("STUDY_AGENT_MCP_COMMAND")
            )
            _wait_for_acp(_health_url(env), timeout_s=30, require_mcp=require_mcp)
            print("Running concept sets review flow smoke test...")
            concept_set = json.loads(
                (REPO_ROOT / "tests" / "demo-data" / "concept_set.json").read_text(
                    encoding="utf-8"
                )
            )
            payload = json.dumps(
                {
                    "concept_set": concept_set,
                    "study_intent": "Identify clinical risk factors for older adult patients who experience an adverse event of acute gastro-intenstinal (GI) bleeding. The GI bleed has to be detected in the hospital setting. Risk factors can include concomitant medications or chronic and acute conditions.",
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                _flow_url(env, "concept_sets_review"),
                data=payload,
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(
                    req, timeout=int(env.get("ACP_TIMEOUT", "180"))
                ) as response:
                    body = response.read().decode("utf-8")
                    print(body)
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8")
                print(body)
                raise
            print(f"ACP logs: {acp_stdout} {acp_stderr}")
        finally:
            print("Stopping ACP...")
            acp_proc.terminate()
            try:
                acp_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                acp_proc.kill()
            if mcp_proc is not None:
                print("Stopping MCP...")
                mcp_proc.terminate()
                try:
                    mcp_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    mcp_proc.kill()

    return {
        "actions": [_run_smoke],
        "verbosity": 2,
    }


def task_smoke_cohort_critique_flow():
    def _run_smoke() -> None:
        env = _runtime_env()
        _require_llm_api_key(env)
        if not env.get("STUDY_AGENT_MCP_URL"):
            env.setdefault("STUDY_AGENT_MCP_COMMAND", "study-agent-mcp")
            env.setdefault("STUDY_AGENT_MCP_ARGS", "")
        env.setdefault("LLM_LOG", "1")

        acp_stdout = _runtime_file(env, "ACP_STDOUT", "study_agent_acp_stdout.log")
        acp_stderr = _runtime_file(env, "ACP_STDERR", "study_agent_acp_stderr.log")
        mcp_proc = _start_mcp_http_if_needed(env)
        print("Starting ACP...")
        with (
            open(acp_stdout, "w", encoding="utf-8") as out,
            open(acp_stderr, "w", encoding="utf-8") as err,
        ):
            acp_proc = subprocess.Popen(
                ["study-agent-acp"], env=env, stdout=out, stderr=err
            )
        try:
            print("Waiting for ACP health endpoint...")
            require_mcp = bool(
                env.get("STUDY_AGENT_MCP_URL") or env.get("STUDY_AGENT_MCP_COMMAND")
            )
            _wait_for_acp(_health_url(env), timeout_s=30, require_mcp=require_mcp)
            print("Running cohort critique flow smoke test...")
            cohort_path = REPO_ROOT / "scripts" / "cohort_definition.json"
            with cohort_path.open("r", encoding="utf-8") as handle:
                cohort = json.load(handle)
            payload = json.dumps(
                {
                    "cohort": cohort,
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                _flow_url(env, "cohort_critique_general_design"),
                data=payload,
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(
                    req, timeout=int(env.get("ACP_TIMEOUT", "180"))
                ) as response:
                    body = response.read().decode("utf-8")
                    print(body)
            except urllib.error.HTTPError as exc:
                error_body = exc.read().decode("utf-8", errors="replace")
                print(error_body)
                raise
            print(f"ACP logs: {acp_stdout} {acp_stderr}")
        finally:
            print("Stopping ACP...")
            acp_proc.terminate()
            try:
                acp_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                acp_proc.kill()
            if mcp_proc is not None:
                print("Stopping MCP...")
                mcp_proc.terminate()
                try:
                    mcp_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    mcp_proc.kill()

    return {
        "actions": [_run_smoke],
        "verbosity": 2,
    }


def task_smoke_phenotype_validation_review_flow():
    def _run_smoke() -> None:
        env = _runtime_env()
        _require_llm_api_key(env)
        if not env.get("STUDY_AGENT_MCP_URL"):
            env.setdefault("STUDY_AGENT_MCP_COMMAND", "study-agent-mcp")
            env.setdefault("STUDY_AGENT_MCP_ARGS", "")
        env.setdefault("LLM_LOG", "1")

        acp_stdout = _runtime_file(env, "ACP_STDOUT", "study_agent_acp_stdout.log")
        acp_stderr = _runtime_file(env, "ACP_STDERR", "study_agent_acp_stderr.log")
        mcp_proc = _start_mcp_http_if_needed(env)
        print("Starting ACP...")
        with (
            open(acp_stdout, "w", encoding="utf-8") as out,
            open(acp_stderr, "w", encoding="utf-8") as err,
        ):
            acp_proc = subprocess.Popen(
                ["study-agent-acp"], env=env, stdout=out, stderr=err
            )
        try:
            print("Waiting for ACP health endpoint...")
            require_mcp = bool(
                env.get("STUDY_AGENT_MCP_URL") or env.get("STUDY_AGENT_MCP_COMMAND")
            )
            _wait_for_acp(_health_url(env), timeout_s=30, require_mcp=require_mcp)
            print("Running phenotype validation review flow smoke test...")
            payload = json.dumps(
                {
                    "disease_name": "Gastrointestinal bleeding",
                    "keeper_row": {
                        "age": 44,
                        "gender": "Male",
                        "visitContext": "Inpatient Visit",
                        "presentation": "Gastrointestinal hemorrhage",
                        "priorDisease": "Peptic ulcer",
                        "symptoms": "",
                        "comorbidities": "",
                        "priorDrugs": "celecoxib",
                        "priorTreatmentProcedures": "",
                        "diagnosticProcedures": "",
                        "measurements": "",
                        "alternativeDiagnosis": "",
                        "afterDisease": "",
                        "afterDrugs": "Naproxen",
                        "afterTreatmentProcedures": "",
                    },
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                _flow_url(env, "phenotype_validation_review"),
                data=payload,
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(
                req, timeout=int(env.get("ACP_TIMEOUT", "180"))
            ) as response:
                body = response.read().decode("utf-8")
                print(body)
                raise
            print(f"ACP logs: {acp_stdout} {acp_stderr}")
        finally:
            print("Stopping ACP...")
            acp_proc.terminate()
            try:
                acp_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                acp_proc.kill()
            if mcp_proc is not None:
                print("Stopping MCP...")
                mcp_proc.terminate()
                try:
                    mcp_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    mcp_proc.kill()

    return {
        "actions": [_run_smoke],
        "verbosity": 2,
    }


def task_smoke_keeper_concept_sets_generate_flow():
    def _run_smoke() -> None:
        env = _runtime_env()
        _require_llm_api_key(env)
        if not env.get("STUDY_AGENT_MCP_URL"):
            env.setdefault("STUDY_AGENT_MCP_COMMAND", "study-agent-mcp")
            env.setdefault("STUDY_AGENT_MCP_ARGS", "")
        env.setdefault("LLM_LOG", "1")

        acp_stdout = _runtime_file(env, "ACP_STDOUT", "study_agent_acp_stdout.log")
        acp_stderr = _runtime_file(env, "ACP_STDERR", "study_agent_acp_stderr.log")
        mcp_proc = _start_mcp_http_if_needed(env)
        print("Starting ACP...")
        with (
            open(acp_stdout, "w", encoding="utf-8") as out,
            open(acp_stderr, "w", encoding="utf-8") as err,
        ):
            acp_proc = subprocess.Popen(
                ["study-agent-acp"], env=env, stdout=out, stderr=err
            )
        try:
            print("Waiting for ACP health endpoint...")
            require_mcp = bool(
                env.get("STUDY_AGENT_MCP_URL") or env.get("STUDY_AGENT_MCP_COMMAND")
            )
            _wait_for_acp(_health_url(env), timeout_s=30, require_mcp=require_mcp)
            print("Running keeper concept sets generate flow smoke test...")
            payload = json.dumps(
                {
                    "phenotype": "Gastrointestinal bleeding",
                    "domain_keys": [
                        "doi"
                    ],  # could also add/change to "alternativeDiagnosis", "symptoms", "drugs", "treatmentProcedures", "diagnosticProcedures", "measurements"
                    "candidate_limit": 10,
                    "include_diagnostics": True,
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                _flow_url(env, "keeper_concept_sets_generate"),
                data=payload,
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(
                req, timeout=int(env.get("ACP_TIMEOUT", "180"))
            ) as response:
                body = response.read().decode("utf-8")
                print(body)
                raise
            print(f"ACP logs: {acp_stdout} {acp_stderr}")
        finally:
            print("Stopping ACP...")
            acp_proc.terminate()
            try:
                acp_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                acp_proc.kill()
            if mcp_proc is not None:
                print("Stopping MCP...")
                mcp_proc.terminate()
                try:
                    mcp_proc.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    mcp_proc.kill()

    return {
        "actions": [_run_smoke],
        "verbosity": 2,
    }


def task_smoke_hecate_phoebe_bulk_endpoint():
    def _run_smoke() -> None:
        env = _runtime_env()
        bulk_url = (env.get("PHOEBE_BULK_URL", "") or "").strip()
        if not bulk_url:
            raise RuntimeError(
                "PHOEBE_BULK_URL must be set before running smoke_hecate_phoebe_bulk_endpoint"
            )
        env["PHOEBE_PROVIDER"] = "hecate_api"
        print(f"Running real Hecate PHOEBE bulk smoke test against {bulk_url}...")
        subprocess.run(
            [sys.executable, "tests/smoke_hecate_phoebe_bulk.py"], check=True, env=env
        )

    return {
        "actions": [_run_smoke],
        "verbosity": 2,
    }


def task_smoke_case_causal_review_flow():
    def _run_smoke() -> None:
        print("Running case causal review flow smoke test...")
        subprocess.run(
            [sys.executable, "tests/smoke_case_causal_review_flow.py"], check=True
        )

    return {
        "actions": [_run_smoke],
        "verbosity": 2,
    }
