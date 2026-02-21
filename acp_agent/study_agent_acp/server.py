from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional

from .agent import StudyAgent
from .mcp_client import StdioMCPClient, StdioMCPClientConfig

SERVICES = [
    {"name": "phenotype_recommendation", "endpoint": "/flows/phenotype_recommendation"},
    {"name": "phenotype_improvements", "endpoint": "/flows/phenotype_improvements"},
    {"name": "concept_sets_review", "endpoint": "/flows/concept_sets_review"},
    {"name": "cohort_critique_general_design", "endpoint": "/flows/cohort_critique_general_design"},
    {"name": "phenotype_validation_review", "endpoint": "/flows/phenotype_validation_review"},
    {"name": "phenotype_recommendation_advice", "endpoint": "/flows/phenotype_recommendation_advice"},
]
SERVICE_REGISTRY_PATH = os.getenv("STUDY_AGENT_SERVICE_REGISTRY", "docs/SERVICE_REGISTRY.yaml")


def _read_json(handler: BaseHTTPRequestHandler) -> Dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    raw = handler.rfile.read(length)
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _write_json(handler: BaseHTTPRequestHandler, status: int, payload: Dict[str, Any]) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    try:
        handler.wfile.write(body)
    except BrokenPipeError:
        if getattr(handler, "debug", False):
            print("ACP response write failed: client disconnected.")


def _load_registry_services() -> tuple[list[Dict[str, Any]], list[str]]:
    warnings: list[str] = []
    try:
        import yaml
    except Exception:
        return [], ["pyyaml_not_installed"]
    if not os.path.exists(SERVICE_REGISTRY_PATH):
        return [], [f"service_registry_missing:{SERVICE_REGISTRY_PATH}"]
    try:
        with open(SERVICE_REGISTRY_PATH, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle) or {}
    except Exception as exc:
        return [], [f"service_registry_error:{exc}"]
    services = []
    for name, entry in (data.get("services") or {}).items():
        if str(name).startswith("_"):
            continue
        endpoint = entry.get("endpoint")
        if endpoint:
            services.append({"name": name, "endpoint": endpoint})
        else:
            warnings.append(f"service_registry_missing_endpoint:{name}")
    return services, warnings


class ACPRequestHandler(BaseHTTPRequestHandler):
    agent: StudyAgent
    mcp_client: Optional[StdioMCPClient]
    debug: bool = False

    def log_message(self, format: str, *args: Any) -> None:
        if self.debug:
            return super().log_message(format, *args)
        return None

    def do_GET(self) -> None:
        if self.path == "/health":
            payload = {"status": "ok"}
            if self.mcp_client is not None:
                payload["mcp"] = self.mcp_client.health_check()
            _write_json(self, 200, payload)
            return
        if self.path == "/tools":
            _write_json(self, 200, {"tools": self.agent.list_tools()})
            return
        if self.path == "/services":
            registry_services, warnings = _load_registry_services()
            registry_map = {svc["endpoint"]: svc for svc in registry_services}
            runtime_map = {svc["endpoint"]: svc for svc in SERVICES}

            services = []
            for endpoint, svc in registry_map.items():
                merged = dict(svc)
                merged["implemented"] = endpoint in runtime_map
                services.append(merged)
            for endpoint, svc in runtime_map.items():
                if endpoint not in registry_map:
                    services.append({**svc, "implemented": True, "source": "acp"})
                    warnings.append(f"service_missing_in_registry:{endpoint}")

            _write_json(self, 200, {"services": services, "warnings": warnings})
            return
        _write_json(self, 404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path == "/tools/call":
            try:
                body = _read_json(self)
            except Exception as exc:
                _write_json(self, 400, {"error": f"invalid_json: {exc}"})
                return

            name = body.get("name")
            arguments = body.get("arguments") or {}
            confirm = bool(body.get("confirm", False))
            if not name:
                _write_json(self, 400, {"error": "missing tool name"})
                return

            try:
                result = self.agent.call_tool(name=name, arguments=arguments, confirm=confirm)
            except Exception as exc:
                if self.debug:
                    import traceback

                    traceback.print_exc()
                _write_json(self, 500, {"error": "tool_call_failed", "detail": str(exc) if self.debug else None})
                return
            status = 200 if result.get("status") != "error" else 500
            _write_json(self, status, result)
            return

        if self.path == "/flows/phenotype_recommendation":
            try:
                body = _read_json(self)
            except Exception as exc:
                _write_json(self, 400, {"error": f"invalid_json: {exc}"})
                return
            study_intent = body.get("study_intent") or body.get("query") or ""
            top_k = int(body.get("top_k", 20))
            max_results = int(body.get("max_results", 10))
            candidate_limit = body.get("candidate_limit")
            if candidate_limit is not None:
                candidate_limit = int(candidate_limit)
            candidate_offset = body.get("candidate_offset")
            if candidate_offset is not None:
                candidate_offset = int(candidate_offset)
            try:
                result = self.agent.run_phenotype_recommendation_flow(
                    study_intent=study_intent,
                    top_k=top_k,
                    max_results=max_results,
                    candidate_limit=candidate_limit,
                    candidate_offset=candidate_offset,
                )
            except Exception as exc:
                if self.debug:
                    import traceback

                    traceback.print_exc()
                _write_json(self, 500, {"error": "flow_failed", "detail": str(exc) if self.debug else None})
                return
            status = 200 if result.get("status") != "error" else 500
            _write_json(self, status, result)
            return

        if self.path == "/flows/phenotype_improvements":
            try:
                body = _read_json(self)
            except Exception as exc:
                _write_json(self, 400, {"error": f"invalid_json: {exc}"})
                return
            protocol_text = body.get("protocol_text") or ""
            protocol_path = body.get("protocol_path")
            if not protocol_text and protocol_path:
                try:
                    with open(protocol_path, "r", encoding="utf-8") as handle:
                        protocol_text = handle.read()
                except Exception as exc:
                    _write_json(self, 400, {"error": f"invalid_protocol_path: {exc}"})
                    return
            cohorts = body.get("cohorts") or []
            cohort_paths = body.get("cohort_paths") or []
            if cohort_paths and not cohorts:
                loaded = []
                for path in cohort_paths:
                    try:
                        with open(path, "r", encoding="utf-8") as handle:
                            loaded.append(json.load(handle))
                    except Exception as exc:
                        _write_json(self, 400, {"error": f"invalid_cohort_path: {exc}"})
                        return
                cohorts = loaded
            cohorts = _ensure_cohort_ids(cohorts, cohort_paths)
            if len(cohorts) > 1:
                cohorts = [cohorts[0]]
            characterization_previews = body.get("characterization_previews") or []
            try:
                result = self.agent.run_phenotype_improvements_flow(
                    protocol_text=protocol_text,
                    cohorts=cohorts,
                    characterization_previews=characterization_previews,
                )
            except Exception as exc:
                if self.debug:
                    import traceback

                    traceback.print_exc()
                _write_json(self, 500, {"error": "flow_failed", "detail": str(exc) if self.debug else None})
                return
            status = 200 if result.get("status") != "error" else 500
            _write_json(self, status, result)
            return

        if self.path == "/flows/concept_sets_review":
            try:
                body = _read_json(self)
            except Exception as exc:
                _write_json(self, 400, {"error": f"invalid_json: {exc}"})
                return
            concept_set = body.get("concept_set")
            concept_set_path = body.get("concept_set_path")
            if concept_set is None and concept_set_path:
                try:
                    with open(concept_set_path, "r", encoding="utf-8") as handle:
                        concept_set = json.load(handle)
                except Exception as exc:
                    _write_json(self, 400, {"error": f"invalid_concept_set_path: {exc}"})
                    return
            study_intent = body.get("study_intent") or ""
            try:
                result = self.agent.run_concept_sets_review_flow(
                    concept_set=concept_set,
                    study_intent=study_intent,
                )
            except Exception as exc:
                if self.debug:
                    import traceback

                    traceback.print_exc()
                _write_json(self, 500, {"error": "flow_failed", "detail": str(exc) if self.debug else None})
                return
            status = 200 if result.get("status") != "error" else 500
            _write_json(self, status, result)
            return

        if self.path == "/flows/cohort_critique_general_design":
            try:
                body = _read_json(self)
            except Exception as exc:
                _write_json(self, 400, {"error": f"invalid_json: {exc}"})
                return
            cohort = body.get("cohort") or {}
            cohort_path = body.get("cohort_path")
            if (not cohort or cohort == {}) and cohort_path:
                try:
                    with open(cohort_path, "r", encoding="utf-8") as handle:
                        cohort = json.load(handle)
                except Exception as exc:
                    _write_json(self, 400, {"error": f"invalid_cohort_path: {exc}"})
                    return
            try:
                result = self.agent.run_cohort_critique_general_design_flow(cohort=cohort)
            except Exception as exc:
                if self.debug:
                    import traceback

                    traceback.print_exc()
                _write_json(self, 500, {"error": "flow_failed", "detail": str(exc) if self.debug else None})
                return
            status = 200 if result.get("status") != "error" else 500
            _write_json(self, status, result)
            return

        if self.path == "/flows/phenotype_validation_review":
            try:
                body = _read_json(self)
            except Exception as exc:
                _write_json(self, 400, {"error": f"invalid_json: {exc}"})
                return
            disease_name = body.get("disease_name") or ""
            keeper_row = body.get("keeper_row")
            keeper_row_path = body.get("keeper_row_path")
            if keeper_row is None and keeper_row_path:
                try:
                    if keeper_row_path.endswith(".csv"):
                        import csv

                        with open(keeper_row_path, "r", encoding="utf-8") as handle:
                            reader = csv.DictReader(handle)
                            keeper_row = next(reader, None)
                    else:
                        with open(keeper_row_path, "r", encoding="utf-8") as handle:
                            keeper_row = json.load(handle)
                except Exception as exc:
                    _write_json(self, 400, {"error": f"invalid_keeper_row_path: {exc}"})
                    return
            if not isinstance(keeper_row, dict):
                _write_json(self, 400, {"error": "keeper_row must be a JSON object"})
                return
            try:
                result = self.agent.run_phenotype_validation_review_flow(
                    keeper_row=keeper_row,
                    disease_name=disease_name,
                )
            except Exception as exc:
                if self.debug:
                    import traceback

                    traceback.print_exc()
                _write_json(self, 500, {"error": "flow_failed", "detail": str(exc) if self.debug else None})
                return
            status = 200 if result.get("status") != "error" else 500
            _write_json(self, status, result)
            return

        if self.path == "/flows/phenotype_recommendation_advice":
            try:
                body = _read_json(self)
            except Exception as exc:
                _write_json(self, 400, {"error": f"invalid_json: {exc}"})
                return
            study_intent = body.get("study_intent") or body.get("query") or ""
            try:
                result = self.agent.run_phenotype_recommendation_advice_flow(
                    study_intent=study_intent,
                )
            except Exception as exc:
                if self.debug:
                    import traceback

                    traceback.print_exc()
                _write_json(self, 500, {"error": "flow_failed", "detail": str(exc) if self.debug else None})
                return
            status = 200 if result.get("status") != "error" else 500
            _write_json(self, status, result)
            return

        _write_json(self, 404, {"error": "not_found"})


def _build_agent(
    mcp_command: Optional[str],
    mcp_args: Optional[list[str]],
    allow_core_fallback: bool,
) -> tuple[StudyAgent, Optional[StdioMCPClient]]:
    mcp_client = None
    if mcp_command:
        mcp_client = StdioMCPClient(
            StdioMCPClientConfig(command=mcp_command, args=mcp_args or []),
        )
    return StudyAgent(mcp_client=mcp_client, allow_core_fallback=allow_core_fallback), mcp_client


def _cohort_id_from_path(path: str) -> Optional[int]:
    base = os.path.basename(path or "")
    if not base:
        return None
    digits = []
    for ch in base:
        if ch.isdigit():
            digits.append(ch)
        else:
            if digits:
                break
    if digits:
        try:
            return int("".join(digits))
        except ValueError:
            return None
    return None


def _ensure_cohort_ids(cohorts: Any, cohort_paths: list[str]) -> list[dict[str, Any]]:
    if not isinstance(cohorts, list):
        return []
    ids_from_paths = []
    for path in cohort_paths or []:
        ids_from_paths.append(_cohort_id_from_path(path))
    patched = []
    for idx, cohort in enumerate(cohorts):
        if not isinstance(cohort, dict):
            continue
        cid = cohort.get("id") or cohort.get("cohortId") or cohort.get("CohortId")
        if cid is None and idx < len(ids_from_paths):
            cid = ids_from_paths[idx]
        if cid is None:
            cid = _cohort_id_from_path(cohort.get("name") or "")
        if cid is None:
            cid = _cohort_id_from_path(cohort.get("Name") or "")
        if cid is None:
            cid = _cohort_id_from_path(cohort.get("cohortName") or "")
        if cid is None:
            cid = cohort.get("id") or cohort.get("Id")
        if cid is not None:
            try:
                cohort["id"] = int(cid)
            except (TypeError, ValueError):
                pass
        else:
            cohort["id"] = idx + 1
            cohort["_synthetic_id"] = True
        patched.append(cohort)
    return patched


def main(host: str = "127.0.0.1", port: int = 8765) -> None:
    import os

    host = os.getenv("STUDY_AGENT_HOST", host)
    port = int(os.getenv("STUDY_AGENT_PORT", str(port)))
    mcp_command = os.getenv("STUDY_AGENT_MCP_COMMAND")
    mcp_args = os.getenv("STUDY_AGENT_MCP_ARGS", "")
    allow_core_fallback = os.getenv("STUDY_AGENT_ALLOW_CORE_FALLBACK", "1") == "1"
    debug = os.getenv("STUDY_AGENT_DEBUG", "0") == "1"

    args_list = [arg for arg in mcp_args.split(" ") if arg]
    agent, mcp_client = _build_agent(mcp_command, args_list, allow_core_fallback)

    class Handler(ACPRequestHandler):
        agent = None
        mcp_client = None
        debug = False

    Handler.agent = agent
    Handler.mcp_client = mcp_client
    Handler.debug = debug
    server = HTTPServer((host, port), Handler)
    _serve(server, mcp_client)


def _serve(server: HTTPServer, mcp_client: Optional[StdioMCPClient]) -> None:
    try:
        server.serve_forever()
    finally:
        if mcp_client is not None:
            mcp_client.close()


if __name__ == "__main__":
    main()
