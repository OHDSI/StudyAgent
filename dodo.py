from __future__ import annotations

import os
import subprocess
import time
import urllib.request

## NOTE: you also need LLM_API_KEY
DEFAULT_ENV = {
    "PHENOTYPE_INDEX_DIR": os.getenv("PHENOTYPE_INDEX_DIR", "data/phenotype_index"),
    "PHENOTYPE_DENSE_WEIGHT": os.getenv("PHENOTYPE_DENSE_WEIGHT", "0.9"),
    "PHENOTYPE_SPARSE_WEIGHT": os.getenv("PHENOTYPE_SPARSE_WEIGHT", "0.1"),
    "OLLAMA_EMBED_URL": os.getenv("OLLAMA_EMBED_URL", "http://localhost:3000/ollama/api/embed"),
    "OLLAMA_EMBED_MODEL": os.getenv("OLLAMA_EMBED_MODEL", "qwen3-embedding:4b"),
    "LLM_API_URL": os.getenv("LLM_API_URL", "http://localhost:3000/api/chat/completions"),
    "LLM_MODEL": os.getenv("LLM_MODEL", "gemma3:4b"),
    "LLM_TIMEOUT": os.getenv("LLM_TIMEOUT", "240"),
    "LLM_LOG": os.getenv("LLM_LOG", "1"),
    "LLM_DRY_RUN": os.getenv("LLM_DRY_RUN", "0"),
    "LLM_USE_RESPONSES": os.getenv("LLM_USE_RESPONSES", "0"),
    "LLM_CANDIDATE_LIMIT": os.getenv("LLM_CANDIDATE_LIMIT", "10"),
    "ACP_URL": os.getenv("ACP_URL", "http://127.0.0.1:8765/flows/phenotype_recommendation"),
    "ACP_TIMEOUT": os.getenv("ACP_TIMEOUT", "180"),
}


def task_install():
    return {
        "actions": ["pip install -e ."],
        "verbosity": 2,
    }


def task_test_core():
    return {
        "actions": ["pytest -m core"],
        "verbosity": 2,
    }


def task_test_acp():
    return {
        "actions": ["pytest -m acp"],
        "verbosity": 2,
    }


def task_test_mcp():
    return {
        "actions": ["pytest -m mcp"],
        "verbosity": 2,
    }


def task_test_unit():
    return {
        "actions": None,
        "task_dep": ["test_core", "test_acp", "test_mcp"],
    }


def task_test_all():
    return {
        "actions": ["pytest"],
        "verbosity": 2,
    }


def task_smoke_phenotype_flow():
    def _wait_for_acp(url: str, timeout_s: int = 30) -> None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(url, timeout=2) as response:
                    if response.status == 200:
                        return
            except Exception:
                time.sleep(0.5)
        raise RuntimeError(f"ACP did not become ready at {url}")

    def _run_smoke() -> None:
        env = os.environ.copy()
        if not env.get("LLM_API_KEY"):
            print("Missing LLM_API_KEY in environment. Set it before running this task.")
            return
        for key, value in DEFAULT_ENV.items():
            env.setdefault(key, value)
        env.setdefault("STUDY_AGENT_MCP_COMMAND", "study-agent-mcp")
        env.setdefault("STUDY_AGENT_MCP_ARGS", "")
        
        acp_stdout = env.get("ACP_STDOUT", "/tmp/study_agent_acp_stdout.log")
        acp_stderr = env.get("ACP_STDERR", "/tmp/study_agent_acp_stderr.log")
        print("Starting ACP (will spawn MCP via stdio)...")
        with open(acp_stdout, "w", encoding="utf-8") as out, open(acp_stderr, "w", encoding="utf-8") as err:
            acp_proc = subprocess.Popen(["study-agent-acp"], env=env, stdout=out, stderr=err)
        try:
            print("Waiting for ACP health endpoint...")
            _wait_for_acp("http://127.0.0.1:8765/health", timeout_s=30)
            print("Running phenotype flow smoke test...")
            subprocess.run(["python", "demo/phenotype_flow_smoke_test.py"], check=True, env=env)
            print(f"ACP logs: {acp_stdout} {acp_stderr}")
        finally:
            print("Stopping ACP...")
            acp_proc.terminate()
            try:
                acp_proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                acp_proc.kill()

    return {
        "actions": [_run_smoke],
        "verbosity": 2,
    }
