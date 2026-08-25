from __future__ import annotations

import json
import logging
import os
from urllib.parse import parse_qs, urlsplit
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
from typing import Any, Dict, Optional

from study_agent_core.logging_utils import configure_service_logger

from .agent import StudyAgent
from .mcp_client import HttpMCPClient, HttpMCPClientConfig, StdioMCPClient, StdioMCPClientConfig

SERVICES = [
    {"name": "phenotype_recommendation", "endpoint": "/flows/phenotype_recommendation"},
    {"name": "phenotype_definition", "endpoint": "/flows/phenotype_definition"},
    {"name": "phenotype_make_computable", "endpoint": "/flows/phenotype_make_computable"},
    {"name": "phenotype_improvements", "endpoint": "/flows/phenotype_improvements"},
    {"name": "concept_sets_review", "endpoint": "/flows/concept_sets_review"},
    {"name": "cohort_critique_general_design", "endpoint": "/flows/cohort_critique_general_design"},
    {"name": "phenotype_validation_review", "endpoint": "/flows/phenotype_validation_review"},
    {"name": "case_causal_review", "endpoint": "/flows/case_causal_review"},
    {"name": "keeper_concept_sets_generate", "endpoint": "/flows/keeper_concept_sets_generate"},
    {"name": "keeper_profiles_generate", "endpoint": "/flows/keeper_profiles_generate"},
    {"name": "phenotype_recommendation_advice", "endpoint": "/flows/phenotype_recommendation_advice"},
    {"name": "phenotype_intent_split", "endpoint": "/flows/phenotype_intent_split"},
    {"name": "cohort_methods_intent_split", "endpoint": "/flows/cohort_methods_intent_split"},
    {"name": "cohort_methods_specifications_recommendation", "endpoint": "/flows/cohort_methods_specifications_recommendation"},
    {"name": "workflow_context_dialogue", "endpoint": "/flows/workflow_context_dialogue"},
]
SERVICE_REGISTRY_PATH = os.getenv("STUDY_AGENT_SERVICE_REGISTRY", "docs/SERVICE_REGISTRY.yaml")
logger = logging.getLogger("study_agent.acp")
ACP_API_VERSION = 1
ACP_SERVICE_VERSION = "0.1.0"


def _sanitize_config_value(name: str, value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    upper = name.upper()
    if "KEY" in upper or "TOKEN" in upper or "SECRET" in upper:
        return "***"
    return value


def _log_startup_config() -> None:
    config_names = [
        "LLM_API_URL",
        "LLM_MODEL",
        "LLM_AUTHENTICATION",
        "LLM_USE_RESPONSES",
        "LLM_TIMEOUT",
        "STUDY_AGENT_MCP_TIMEOUT",
        "LLM_CANDIDATE_LIMIT",
        "LLM_RECOMMENDATION_MAX_RESULTS",
        "LLM_RECOMMENDATION_TOP_K",
        "EMBED_TIMEOUT",
        "ACP_TIMEOUT",
    ]
    items = []
    for name in config_names:
        items.append(f"{name}={_sanitize_config_value(name, os.getenv(name))}")
    logger.info("config %s", " ".join(items))


def _reject_local_path_input(field_name: str) -> Dict[str, str]:
    return {
        "error": f"local_path_inputs_not_supported:{field_name}",
        "detail": (
            "ACP flow handlers no longer read local filesystem paths from request bodies. "
            "Load the artifact in the client and send inline payloads, or upload/stage the "
            "artifact before calling the flow."
        ),
    }


def _warn_on_inconsistent_llm_config() -> None:
    api_url = os.getenv("LLM_API_URL", "")
    use_responses = os.getenv("LLM_USE_RESPONSES", "0")
    if "/api/chat/completions" in api_url and use_responses == "1":
        logger.warning(
            "LLM_API_URL targets /api/chat/completions while LLM_USE_RESPONSES=1. "
            "Set LLM_USE_RESPONSES=0 for chat-completions compatibility."
        )


def _resolve_mcp_url_from_env() -> Optional[str]:
    explicit = os.getenv("STUDY_AGENT_MCP_URL")
    if explicit:
        return explicit

    transport = (os.getenv("MCP_TRANSPORT") or "").strip().lower()
    if transport != "http":
        return None

    host = (os.getenv("MCP_HOST") or "").strip()
    port = (os.getenv("MCP_PORT") or "").strip()
    path = (os.getenv("MCP_PATH") or "/mcp").strip() or "/mcp"
    if not host or not port:
        return None
    if not path.startswith("/"):
        path = f"/{path}"
    return f"http://{host}:{port}{path}"


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
            logger.debug("response write failed: client disconnected")


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


def _call_mcp_tool_with_retry(mcp_client: object, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    try:
        return mcp_client.call_tool(name, arguments)
    except Exception as exc:
        message = str(exc)
        if "cancel scope" not in message.lower():
            raise
        close = getattr(mcp_client, "close", None)
        if callable(close):
            try:
                close()
            except Exception:
                pass
        return mcp_client.call_tool(name, arguments)



class ACPRequestHandler(BaseHTTPRequestHandler):
    agent: StudyAgent
    mcp_client: Optional[object]
    debug: bool = False

    def log_message(self, format: str, *args: Any) -> None:
        if self.debug:
            logger.info("http %s", format % args)
            return None
        return None

    def do_GET(self) -> None:
        if self.debug:
            content_type = self.headers.get("Content-Type")
            logger.debug("GET path=%s content_type=%s", self.path, content_type)

        parsed = urlsplit(self.path)

        if parsed.path == "/health":
            payload = {
                "status": "ok",
                "api_version": ACP_API_VERSION,
                "service_version": ACP_SERVICE_VERSION,
            }
            if self.mcp_client is not None:
                payload["mcp"] = self.mcp_client.health_check()
                params = parse_qs(parsed.query)
                deep = (
                    params.get("deep", ["0"])[0] == "1"
                    or os.getenv("STUDY_AGENT_HEALTH_DEEP", "0") == "1"
                )
                payload["mcp_index"] = {"skipped": not deep}
                if deep and payload["mcp"].get("ok"):
                    try:
                        payload["mcp_index"] = _call_mcp_tool_with_retry(
                            self.mcp_client,
                            "phenotype_index_status",
                            {},
                        )
                    except Exception as exc:
                        payload["mcp_index"] = {"error": str(exc)}
            else:
                payload["mcp"] = {"ok": False, "configured": False, "error": "mcp_not_configured"}
                payload["mcp_index"] = {"skipped": True, "reason": "mcp_not_configured"}

            _write_json(self, 200, payload)
            return

        if parsed.path == "/tools":
            _write_json(self, 200, {"tools": self.agent.list_tools()})
            return

        if parsed.path == "/services":
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
        if self.debug:
            length = int(self.headers.get("Content-Length", "0"))
            content_type = self.headers.get("Content-Type")
            logger.debug("POST path=%s length=%s content_type=%s", self.path, length, content_type)
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
                    logger.exception("tool_call_failed name=%s", name)
                _write_json(self, 500, {"error": "tool_call_failed", "detail": str(exc) if self.debug else None})
                return
            status = 200 if result.get("status") != "error" else 500
            _write_json(self, status, result)
            return

        if self.path == "/flows/phenotype_make_computable":
            try:
                from study_agent_core.models import PhenotypeMakeComputableInput
                payload = PhenotypeMakeComputableInput(**_read_json(self))
            except Exception as exc:
                _write_json(self, 422, {"error": f"invalid_payload: {exc}"})
                return
            result = self.agent.run_phenotype_make_computable_flow(**payload.model_dump())
            _write_json(self, 200 if result.get("status") != "error" else 400, result)
            return
        if self.path == "/flows/phenotype_definition":
            try:
                body = _read_json(self)
            except Exception as exc:
                _write_json(self, 400, {"error": f"invalid_json: {exc}"})
                return
            phenotype_id = body.get("phenotype_id") or ""
            try:
                result = self.agent.run_phenotype_definition_flow(phenotype_id=phenotype_id)
            except Exception as exc:
                if self.debug:
                    logger.exception("flow_failed name=phenotype_definition")
                _write_json(self, 500, {"error": "flow_failed", "detail": str(exc) if self.debug else None})
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
            recommendation_role = str(body.get("recommendation_role") or "").strip() or None
            workflow_type = str(body.get("workflow_type") or "").strip() or None
            exclude_metadata = body.get("exclude_metadata")
            if not isinstance(exclude_metadata, dict):
                exclude_metadata = None
            try:
                result = self.agent.run_phenotype_recommendation_flow(
                    study_intent=study_intent,
                    top_k=top_k,
                    max_results=max_results,
                    candidate_limit=candidate_limit,
                    candidate_offset=candidate_offset,
                    recommendation_role=recommendation_role,
                    workflow_type=workflow_type,
                    exclude_metadata=exclude_metadata,
                )
            except Exception as exc:
                if self.debug:
                    logger.exception("flow_failed name=phenotype_recommendation")
                _write_json(self, 500, {"error": "flow_failed", "detail": str(exc) if self.debug else None})
                return
            status = 200 if result.get("status") != "error" else 500
            _write_json(self, status, result)
            return

        if self.path == "/flows/workflow_context_dialogue":
            try:
                body = _read_json(self)
            except Exception as exc:
                _write_json(self, 400, {"error": f"invalid_json: {exc}"})
                return
            user_prompt = str(body.get("user_prompt") or body.get("prompt") or "").strip()
            study_intent = str(body.get("study_intent") or "").strip()
            workflow_type = str(body.get("workflow_type") or "").strip()
            current_step = str(body.get("current_step") or "").strip()
            current_role = str(body.get("current_role") or "").strip()
            current_context = body.get("current_context")
            if not isinstance(current_context, dict):
                current_context = {}
            try:
                result = self.agent.run_workflow_context_dialogue_flow(
                    user_prompt=user_prompt,
                    study_intent=study_intent,
                    workflow_type=workflow_type,
                    current_step=current_step,
                    current_role=current_role,
                    current_context=current_context,
                )
            except Exception as exc:
                if self.debug:
                    logger.exception("flow_failed name=workflow_context_dialogue")
                _write_json(self, 500, {"error": "flow_failed", "detail": str(exc) if self.debug else None})
                return
            status = 200 if result.get("status") != "error" else 500
            _write_json(self, status, result)
            return

        if self.path == "/flows/cohort_methods_specifications_recommendation":
            try:
                body = _read_json(self)
            except Exception as exc:
                _write_json(self, 400, {"error": f"invalid_json: {exc}"})
                return
            try:
                from study_agent_core.models import CohortMethodSpecsRecommendationInput
                payload = CohortMethodSpecsRecommendationInput(**body)
            except Exception as exc:
                _write_json(self, 422, {"error": f"invalid_payload: {exc}"})
                return
            try:
                result = self.agent.run_cohort_methods_specs_recommendation_flow(
                    analytic_settings_description=payload.analytic_settings_description,
                    study_intent=payload.study_intent or "",
                )
            except Exception as exc:
                if self.debug:
                    logger.exception("flow_failed name=cohort_methods_specifications_recommendation")
                _write_json(self, 500, {"error": "flow_failed", "detail": str(exc) if self.debug else None})
                return
            _write_json(self, 200, result)
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
                _write_json(self, 400, _reject_local_path_input("protocol_path"))
                return
            cohorts = body.get("cohorts") or []
            cohort_paths = body.get("cohort_paths") or []
            if cohort_paths and not cohorts:
                _write_json(self, 400, _reject_local_path_input("cohort_paths"))
                return
            cohorts = _ensure_cohort_ids(cohorts)
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
                    logger.exception("flow_failed name=phenotype_improvements")
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
                _write_json(self, 400, _reject_local_path_input("concept_set_path"))
                return
            study_intent = body.get("study_intent") or ""
            try:
                result = self.agent.run_concept_sets_review_flow(
                    concept_set=concept_set,
                    study_intent=study_intent,
                )
            except Exception as exc:
                if self.debug:
                    logger.exception("flow_failed name=concept_sets_review")
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
                _write_json(self, 400, _reject_local_path_input("cohort_path"))
                return
            try:
                result = self.agent.run_cohort_critique_general_design_flow(cohort=cohort)
            except Exception as exc:
                if self.debug:
                    logger.exception("flow_failed name=cohort_critique_general_design")
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
                _write_json(self, 400, _reject_local_path_input("keeper_row_path"))
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
                    logger.exception("flow_failed name=phenotype_validation_review")
                _write_json(self, 500, {"error": "flow_failed", "detail": str(exc) if self.debug else None})
                return
            status = 200 if result.get("status") != "error" else 500
            _write_json(self, status, result)
            return


        if self.path == "/flows/case_causal_review":
            try:
                body = _read_json(self)
            except Exception as exc:
                _write_json(self, 400, {"error": f"invalid_json: {exc}"})
                return
            adverse_event_name = body.get("adverse_event_name") or ""
            case_row = body.get("case_row")
            source_type = body.get("source_type") or ""
            allowed_domains = body.get("allowed_domains") or []
            if not isinstance(case_row, dict):
                _write_json(self, 400, {"error": "case_row must be a JSON object"})
                return
            if source_type not in {"signal_validation", "patient_profile"}:
                _write_json(self, 400, {"error": "source_type must be signal_validation or patient_profile"})
                return
            if not isinstance(allowed_domains, list):
                _write_json(self, 400, {"error": "allowed_domains must be an array when provided"})
                return
            try:
                result = self.agent.run_case_causal_review_flow(
                    adverse_event_name=adverse_event_name,
                    case_row=case_row,
                    source_type=source_type,
                    allowed_domains=allowed_domains,
                )
            except Exception as exc:
                if self.debug:
                    logger.exception("flow_failed name=case_causal_review")
                _write_json(self, 500, {"error": "flow_failed", "detail": str(exc) if self.debug else None})
                return
            status = 200 if result.get("status") != "error" else 500
            _write_json(self, status, result)
            return

        if self.path == "/flows/keeper_concept_sets_generate":
            try:
                body = _read_json(self)
            except Exception as exc:
                _write_json(self, 400, {"error": f"invalid_json: {exc}"})
                return
            phenotype = body.get("phenotype") or ""
            domain_keys = body.get("domain_keys") or []
            vocab_search_provider = body.get("vocab_search_provider") or ""
            phoebe_provider = body.get("phoebe_provider") or ""
            candidate_limit = int(body.get("candidate_limit", 50))
            min_record_count = int(body.get("min_record_count", 0))
            include_diagnostics = bool(body.get("include_diagnostics", True))
            try:
                result = self.agent.run_keeper_concept_sets_generate_flow(
                    phenotype=phenotype,
                    domain_keys=domain_keys,
                    vocab_search_provider=vocab_search_provider,
                    phoebe_provider=phoebe_provider,
                    candidate_limit=candidate_limit,
                    min_record_count=min_record_count,
                    include_diagnostics=include_diagnostics,
                )
            except Exception as exc:
                if self.debug:
                    logger.exception("flow_failed name=keeper_concept_sets_generate")
                _write_json(self, 500, {"error": "flow_failed", "detail": str(exc) if self.debug else None})
                return
            status = 200 if result.get("status") != "error" else 500
            _write_json(self, status, result)
            return

        if self.path == "/flows/keeper_profiles_generate":
            try:
                body = _read_json(self)
            except Exception as exc:
                _write_json(self, 400, {"error": f"invalid_json: {exc}"})
                return
            try:
                keeper_concept_sets = body.get("keeper_concept_sets") or []
                if not keeper_concept_sets and body.get("keeper_concept_sets_path"):
                    _write_json(self, 400, _reject_local_path_input("keeper_concept_sets_path"))
                    return
                result = self.agent.run_keeper_profiles_generate_flow(
                    cohort_database_schema=body.get("cohort_database_schema") or "",
                    cohort_table=body.get("cohort_table") or "",
                    cohort_definition_id=int(body.get("cohort_definition_id", 0)),
                    cdm_database_schema=body.get("cdm_database_schema") or "",
                    sample_size=int(body.get("sample_size", 20)),
                    person_ids=body.get("person_ids") or [],
                    keeper_concept_sets=keeper_concept_sets,
                    phenotype_name=body.get("phenotype_name") or "",
                    use_descendants=bool(body.get("use_descendants", True)),
                    remove_pii=bool(body.get("remove_pii", True)),
                )
            except Exception as exc:
                if self.debug:
                    logger.exception("flow_failed name=keeper_profiles_generate")
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
                    logger.exception("flow_failed name=phenotype_recommendation_advice")
                _write_json(self, 500, {"error": "flow_failed", "detail": str(exc) if self.debug else None})
                return
            status = 200 if result.get("status") != "error" else 500
            _write_json(self, status, result)
            return

        if self.path == "/flows/phenotype_intent_split":
            try:
                body = _read_json(self)
            except Exception as exc:
                _write_json(self, 400, {"error": f"invalid_json: {exc}"})
                return
            study_intent = body.get("study_intent") or body.get("query") or ""
            try:
                result = self.agent.run_phenotype_intent_split_flow(
                    study_intent=study_intent,
                )
            except Exception as exc:
                if self.debug:
                    logger.exception("flow_failed name=phenotype_intent_split")
                _write_json(self, 500, {"error": "flow_failed", "detail": str(exc) if self.debug else None})
                return
            status = 200 if result.get("status") != "error" else 500
            _write_json(self, status, result)
            return

        if self.path == "/flows/cohort_methods_intent_split":
            try:
                body = _read_json(self)
            except Exception as exc:
                _write_json(self, 400, {"error": f"invalid_json: {exc}"})
                return
            study_intent = body.get("study_intent") or body.get("query") or ""
            try:
                result = self.agent.run_cohort_methods_intent_split_flow(
                    study_intent=study_intent,
                )
            except Exception as exc:
                if self.debug:
                    logger.exception("flow_failed name=cohort_methods_intent_split")
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
    mcp_cwd: Optional[str],
    mcp_url: Optional[str],
    mcp_token: Optional[str],
    mcp_timeout: int,
) -> tuple[StudyAgent, Optional[object]]:
    mcp_client = None
    if mcp_url:
        mcp_client = HttpMCPClient(HttpMCPClientConfig(url=mcp_url, token=mcp_token, timeout=mcp_timeout))
    elif mcp_command:
        mcp_client = StdioMCPClient(
            StdioMCPClientConfig(command=mcp_command, args=mcp_args or [], cwd=mcp_cwd),
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


def _ensure_cohort_ids(cohorts: Any) -> list[dict[str, Any]]:
    if not isinstance(cohorts, list):
        return []
    patched = []
    for idx, cohort in enumerate(cohorts):
        if not isinstance(cohort, dict):
            continue
        cid = cohort.get("id") or cohort.get("cohortId") or cohort.get("CohortId")
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
    import signal
    import threading

    configure_service_logger(
        "ACP",
        "study_agent.acp",
        default_level="INFO",
        stream="stderr",
        default_filename="study-agent-acp.log",
    )

    host = os.getenv("STUDY_AGENT_HOST", host)
    port = int(os.getenv("STUDY_AGENT_PORT", str(port)))
    mcp_command = os.getenv("STUDY_AGENT_MCP_COMMAND")
    mcp_args = os.getenv("STUDY_AGENT_MCP_ARGS", "")
    allow_core_fallback = os.getenv("STUDY_AGENT_ALLOW_CORE_FALLBACK", "1") == "1"
    debug = os.getenv("STUDY_AGENT_DEBUG", "0") == "1"
    threaded = os.getenv("STUDY_AGENT_THREADING", "1") == "1"
    mcp_cwd = os.getenv("STUDY_AGENT_MCP_CWD") or os.getcwd()
    mcp_url = _resolve_mcp_url_from_env()
    mcp_token = os.getenv("STUDY_AGENT_MCP_TOKEN")
    mcp_timeout = int(os.getenv("STUDY_AGENT_MCP_TIMEOUT", "240"))
    _log_startup_config()
    _warn_on_inconsistent_llm_config()

    if mcp_url:
        if "://" in mcp_url and ":" not in mcp_url.split("://", 1)[1]:
            raise RuntimeError("STUDY_AGENT_MCP_URL missing port (e.g., http://127.0.0.1:8790/mcp).")
        logger.info("MCP url=%s", mcp_url)
    elif mcp_command:
        if os.getenv("PHENOTYPE_INDEX_DIR") is None:
            logger.warning("PHENOTYPE_INDEX_DIR not set; MCP will use its default.")
        if os.getenv("EMBED_URL") is None:
            logger.warning("EMBED_URL not set; MCP will use its default.")
        if os.getenv("EMBED_MODEL") is None:
            logger.warning("EMBED_MODEL not set; MCP will use its default.")
        logger.info("MCP cwd=%s", mcp_cwd)

    args_list = [arg for arg in mcp_args.split(" ") if arg]
    agent, mcp_client = _build_agent(
        mcp_command,
        args_list,
        allow_core_fallback,
        mcp_cwd,
        mcp_url,
        mcp_token,
        mcp_timeout,
    )

    class Handler(ACPRequestHandler):
        agent = None
        mcp_client = None
        debug = False

    Handler.agent = agent
    Handler.mcp_client = mcp_client
    Handler.debug = debug
    server_cls = ThreadingHTTPServer if threaded else HTTPServer
    server = server_cls((host, port), Handler)
    logger.info("ACP listening host=%s port=%s threaded=%s debug=%s", host, port, threaded, debug)

    shutdown_lock = threading.Lock()
    shutdown_once = {"done": False}

    def _shutdown(signum, frame) -> None:
        with shutdown_lock:
            if shutdown_once["done"]:
                return
            shutdown_once["done"] = True
        # HTTPServer.shutdown() must run from a different thread than serve_forever().
        # We defer MCP cleanup to _serve() so signal handling stays responsive.
        def _shutdown_server() -> None:
            try:
                server.shutdown()
            except Exception:
                pass

        threading.Thread(target=_shutdown_server, name="acp-shutdown", daemon=True).start()

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    _serve(server, mcp_client)


def _serve(server: HTTPServer, mcp_client: Optional[object]) -> None:
    try:
        server.serve_forever()
    finally:
        try:
            close = getattr(server, "server_close", None)
            if callable(close):
                close()
        finally:
            if mcp_client is not None:
                try:
                    mcp_client.close()
                except Exception:
                    pass


if __name__ == "__main__":
    main()
