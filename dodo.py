from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.request

## NOTE: you also need LLM_API_KEY
DEFAULT_ENV = {
    "PHENOTYPE_INDEX_DIR": os.getenv("PHENOTYPE_INDEX_DIR", "data/phenotype_index"),
    "PHENOTYPE_DENSE_WEIGHT": os.getenv("PHENOTYPE_DENSE_WEIGHT", "0.9"),
    "PHENOTYPE_SPARSE_WEIGHT": os.getenv("PHENOTYPE_SPARSE_WEIGHT", "0.1"),
    "EMBED_URL": os.getenv("EMBED_URL", "http://localhost:3000/ollama/api/embed"),
    "EMBED_MODEL": os.getenv("EMBED_MODEL", "qwen3-embedding:4b"),
    "LLM_API_URL": os.getenv("LLM_API_URL", "http://localhost:3000/api/chat/completions"),
    "LLM_MODEL": os.getenv("LLM_MODEL", "gemma3:4b"),
    "LLM_TIMEOUT": os.getenv("LLM_TIMEOUT", "240"),
    "LLM_LOG": os.getenv("LLM_LOG", "1"),
    "LLM_DRY_RUN": os.getenv("LLM_DRY_RUN", "0"),
    "LLM_USE_RESPONSES": os.getenv("LLM_USE_RESPONSES", "0"),
    "LLM_CANDIDATE_LIMIT": os.getenv("LLM_CANDIDATE_LIMIT", "10"),
    "ACP_URL": os.getenv("ACP_URL", "http://127.0.0.1:8765/flows/phenotype_recommendation"),
    "ACP_TIMEOUT": os.getenv("ACP_TIMEOUT", "180"),
    "STUDY_AGENT_HOST": os.getenv("STUDY_AGENT_HOST", "127.0.0.1"),
    "STUDY_AGENT_PORT": os.getenv("STUDY_AGENT_PORT", "8765"),
}


def _pytest_cmd(marker: str | None = None) -> str:
    opts = os.getenv("PYTEST_OPTS", "")
    base = "pytest"
    if marker:
        base = f"{base} -m {marker}"
    if opts:
        return f"{base} {opts}"
    return base


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
    return {
        "actions": [_pytest_cmd()],
        "verbosity": 2,
    }


def task_run_all():
    return {
        "actions": None,
        "task_dep": ["test_all","smoke_phenotype_recommend_flow", "smoke_phenotype_improvements_flow", "smoke_concept_sets_review_flow", "smoke_cohort_critique_flow"],
    }


def task_check_llm_connectivity():
    def _run_check() -> None:
        env = os.environ.copy()
        if not env.get("LLM_API_KEY"):
            print("Missing LLM_API_KEY in environment. Set it before running this task.")
            return
        for key, value in DEFAULT_ENV.items():
            env.setdefault(key, value)

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
            "-H",
            f"Authorization: Bearer {env['LLM_API_KEY']}",
            "-d",
            payload,
        ]
        print("Running LLM connectivity check...")
        subprocess.run(cmd, check=True)

    return {
        "actions": [_run_check],
        "verbosity": 2,
    }


def task_list_services():
    def _run_list() -> None:
        env = os.environ.copy()
        host = env.get("STUDY_AGENT_HOST", DEFAULT_ENV["STUDY_AGENT_HOST"])
        port = env.get("STUDY_AGENT_PORT", DEFAULT_ENV["STUDY_AGENT_PORT"])
        url = env.get("ACP_BASE_URL", f"http://{host}:{port}")
        if url.endswith("/"):
            url = url[:-1]
        req = urllib.request.Request(f"{url}/services")
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
        print(body)

    return {
        "actions": [_run_list],
        "verbosity": 2,
    }


def task_smoke_phenotype_recommend_flow():
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
        env.setdefault("LLM_LOG", "1")
        
        acp_stdout = env.get("ACP_STDOUT", "/tmp/study_agent_acp_stdout.log")
        acp_stderr = env.get("ACP_STDERR", "/tmp/study_agent_acp_stderr.log")
        print("Starting ACP (will spawn MCP via stdio)...")
        with open(acp_stdout, "w", encoding="utf-8") as out, open(acp_stderr, "w", encoding="utf-8") as err:
            acp_proc = subprocess.Popen(["study-agent-acp"], env=env, stdout=out, stderr=err)
        try:
            print("Waiting for ACP health endpoint...")
            _wait_for_acp("http://127.0.0.1:8765/health", timeout_s=30)
            print("Running phenotype flow smoke test...")
            subprocess.run(["python", "tests/phenotype_flow_smoke_test.py"], check=True, env=env)
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


def task_smoke_phenotype_improvements_flow():
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
            print("Running phenotype improvements flow smoke test...")
            payload = json.dumps(
                {
                    "protocol_path": "demo/protocol.md",
                    "cohort_paths": [
                        "demo/demo/test_git_event_cohort.json"
                    ],
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                "http://127.0.0.1:8765/flows/phenotype_improvements",
                data=payload,
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=int(env.get("ACP_TIMEOUT", "180"))) as response:
                    body = response.read().decode("utf-8")
                    print(body)
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8")
                print(body)
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


def task_smoke_concept_sets_review_flow():
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
        env.setdefault("LLM_LOG", "1")

        acp_stdout = env.get("ACP_STDOUT", "/tmp/study_agent_acp_stdout.log")
        acp_stderr = env.get("ACP_STDERR", "/tmp/study_agent_acp_stderr.log")
        print("Starting ACP (will spawn MCP via stdio)...")
        with open(acp_stdout, "w", encoding="utf-8") as out, open(acp_stderr, "w", encoding="utf-8") as err:
            acp_proc = subprocess.Popen(["study-agent-acp"], env=env, stdout=out, stderr=err)
        try:
            print("Waiting for ACP health endpoint...")
            _wait_for_acp("http://127.0.0.1:8765/health", timeout_s=30)
            print("Running concept sets review flow smoke test...")
            payload = json.dumps(
                {
                    "concept_set_path": "demo/concept_set.json",
                    "study_intent": "Identify clinical risk factors for older adult patients who experience an adverse event of acute gastro-intenstinal (GI) bleeding. The GI bleed has to be detected in the hospital setting. Risk factors can include concomitant medications or chronic and acute conditions.",
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                "http://127.0.0.1:8765/flows/concept_sets_review",
                data=payload,
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            try:
                with urllib.request.urlopen(req, timeout=int(env.get("ACP_TIMEOUT", "180"))) as response:
                    body = response.read().decode("utf-8")
                    print(body)
            except urllib.error.HTTPError as exc:
                body = exc.read().decode("utf-8")
                print(body)
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


def task_smoke_cohort_critique_flow():
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
        env.setdefault("LLM_LOG", "1")

        acp_stdout = env.get("ACP_STDOUT", "/tmp/study_agent_acp_stdout.log")
        acp_stderr = env.get("ACP_STDERR", "/tmp/study_agent_acp_stderr.log")
        print("Starting ACP (will spawn MCP via stdio)...")
        with open(acp_stdout, "w", encoding="utf-8") as out, open(acp_stderr, "w", encoding="utf-8") as err:
            acp_proc = subprocess.Popen(["study-agent-acp"], env=env, stdout=out, stderr=err)
        try:
            print("Waiting for ACP health endpoint...")
            _wait_for_acp("http://127.0.0.1:8765/health", timeout_s=30)
            print("Running cohort critique flow smoke test...")
            payload = json.dumps(
                {
                    "cohort_path": "demo/cohort_definition.json",
                }
            ).encode("utf-8")
            req = urllib.request.Request(
                "http://127.0.0.1:8765/flows/cohort_critique_general_design",
                data=payload,
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=int(env.get("ACP_TIMEOUT", "180"))) as response:
                body = response.read().decode("utf-8")
                print(body)
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


def task_smoke_phenotype_validation_review_flow():
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
        env.setdefault("LLM_LOG", "1")

        acp_stdout = env.get("ACP_STDOUT", "/tmp/study_agent_acp_stdout.log")
        acp_stderr = env.get("ACP_STDERR", "/tmp/study_agent_acp_stderr.log")
        print("Starting ACP (will spawn MCP via stdio)...")
        with open(acp_stdout, "w", encoding="utf-8") as out, open(acp_stderr, "w", encoding="utf-8") as err:
            acp_proc = subprocess.Popen(["study-agent-acp"], env=env, stdout=out, stderr=err)
        try:
            print("Waiting for ACP health endpoint...")
            _wait_for_acp("http://127.0.0.1:8765/health", timeout_s=30)
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
                "http://127.0.0.1:8765/flows/phenotype_validation_review",
                data=payload,
                method="POST",
            )
            req.add_header("Content-Type", "application/json")
            with urllib.request.urlopen(req, timeout=int(env.get("ACP_TIMEOUT", "180"))) as response:
                body = response.read().decode("utf-8")
                print(body)
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
