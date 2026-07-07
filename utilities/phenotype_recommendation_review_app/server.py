from http.server import BaseHTTPRequestHandler, HTTPServer
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, unquote, urlsplit
from urllib.request import Request, urlopen


HOST = "127.0.0.1"
PORT = 8010
ACP_RECOMMENDATION_URL = "http://127.0.0.1:8765/flows/phenotype_recommendation"
ACP_DEFINITION_URL = "http://127.0.0.1:8765/flows/phenotype_definition"
APP_DIR = Path(__file__).resolve().parent
DEFAULT_TOP_K = 20
DEFAULT_MAX_RESULTS = 3
DEFAULT_CANDIDATE_LIMIT = 10
DEFAULT_CANDIDATE_OFFSET = 0


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: object) -> None:
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _post_json(url: str, payload: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=120) as response:
        body = response.read().decode("utf-8")
        return json.loads(body)


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _normalize_exclude_metadata(payload: object) -> dict[str, list[str]]:
    if not isinstance(payload, dict):
        return {}
    normalized: dict[str, list[str]] = {}
    for key, raw_values in payload.items():
        key_text = str(key or "").strip()
        if not key_text:
            continue
        if isinstance(raw_values, list):
            values = [str(item or "").strip() for item in raw_values]
        else:
            values = [part.strip() for part in str(raw_values or "").split(",")]
        clean_values = [value for value in values if value]
        if clean_values:
            normalized[key_text] = clean_values
    return normalized


def _positive_int(value: object, *, field_name: str, default: int) -> int:
    if value is None or str(value).strip() == "":
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a positive integer.") from None
    if parsed < 1:
        raise ValueError(f"{field_name} must be a positive integer.")
    return parsed


def _non_negative_int(value: object, *, field_name: str, default: int) -> int:
    if value is None or str(value).strip() == "":
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be a non-negative integer.") from None
    if parsed < 0:
        raise ValueError(f"{field_name} must be a non-negative integer.")
    return parsed


def _build_recommendation_payload(payload: dict) -> tuple[dict | None, str | None]:
    study_intent = str(payload.get("study_intent") or "").strip()
    if not study_intent:
        return None, "study_intent is required."

    try:
        top_k = _positive_int(payload.get("top_k"), field_name="top_k", default=DEFAULT_TOP_K)
        candidate_offset = _non_negative_int(
            payload.get("candidate_offset"),
            field_name="candidate_offset",
            default=DEFAULT_CANDIDATE_OFFSET,
        )
        max_results = _positive_int(payload.get("max_results"), field_name="max_results", default=DEFAULT_MAX_RESULTS)
        candidate_limit = _positive_int(
            payload.get("candidate_limit"),
            field_name="candidate_limit",
            default=DEFAULT_CANDIDATE_LIMIT,
        )
    except ValueError as exc:
        return None, str(exc)

    acp_payload = {
        "study_intent": study_intent,
        "top_k": top_k,
        "max_results": max_results,
        "candidate_limit": candidate_limit,
    }
    if payload.get("candidate_offset") is not None and str(payload.get("candidate_offset")).strip() != "":
        acp_payload["candidate_offset"] = candidate_offset
    recommendation_role = _optional_text(payload.get("recommendation_role"))
    workflow_type = _optional_text(payload.get("workflow_type"))
    exclude_metadata = _normalize_exclude_metadata(payload.get("exclude_metadata"))
    if recommendation_role:
        acp_payload["recommendation_role"] = recommendation_role
    if workflow_type:
        acp_payload["workflow_type"] = workflow_type
    if exclude_metadata:
        acp_payload["exclude_metadata"] = exclude_metadata
    return acp_payload, None


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urlsplit(self.path)
        if parsed.path in ("/", "/index.html"):
            self._serve_file("index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/phenotype.html":
            self._serve_file("phenotype.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/app.js":
            self._serve_file("app.js", "application/javascript; charset=utf-8")
            return
        if parsed.path == "/phenotype.js":
            self._serve_file("phenotype.js", "application/javascript; charset=utf-8")
            return
        if parsed.path == "/styles.css":
            self._serve_file("styles.css", "text/css; charset=utf-8")
            return
        if parsed.path.startswith("/api/phenotype/"):
            phenotype_id = unquote(parsed.path.removeprefix("/api/phenotype/"))
            params = parse_qs(parsed.query)
            view = (params.get("view") or ["assembled"])[0]
            self._serve_phenotype_payload(phenotype_id=phenotype_id, view=view)
            return
        self.send_error(404, "Not found")

    def do_POST(self) -> None:
        if self.path != "/api/recommend":
            self.send_error(404, "Not found")
            return
        length = int(self.headers.get("Content-Length", "0"))
        raw_body = self.rfile.read(length)
        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            _json_response(self, 400, {"error": "invalid_request", "detail": "Request body must be valid JSON."})
            return

        acp_payload, validation_error = _build_recommendation_payload(payload)
        if validation_error:
            _json_response(self, 400, {"error": "invalid_request", "detail": validation_error})
            return

        try:
            result = _post_json(ACP_RECOMMENDATION_URL, acp_payload)
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            _json_response(
                self,
                502,
                {
                    "error": "acp_http_error",
                    "detail": f"ACP returned HTTP {exc.code}.",
                    "acp_response_text": detail,
                },
            )
            return
        except URLError as exc:
            _json_response(
                self,
                502,
                {"error": "acp_unreachable", "detail": f"Could not reach ACP at {ACP_RECOMMENDATION_URL}: {exc.reason}"},
            )
            return
        except TimeoutError:
            _json_response(self, 504, {"error": "acp_timeout", "detail": "ACP request timed out."})
            return
        except json.JSONDecodeError:
            _json_response(self, 502, {"error": "invalid_acp_response", "detail": "ACP returned non-JSON output."})
            return

        _json_response(self, 200, result)

    def log_message(self, format: str, *args) -> None:
        return

    def _serve_file(self, name: str, content_type: str) -> None:
        path = APP_DIR / name
        if not path.exists():
            self.send_error(404, "Not found")
            return
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _serve_phenotype_payload(self, phenotype_id: str, view: str) -> None:
        phenotype_id = str(phenotype_id or "").strip()
        if not phenotype_id:
            _json_response(self, 400, {"error": "invalid_request", "detail": "phenotype_id is required."})
            return
        try:
            result = _post_json(ACP_DEFINITION_URL, {"phenotype_id": phenotype_id})
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            _json_response(
                self,
                502,
                {
                    "error": "acp_http_error",
                    "detail": f"ACP returned HTTP {exc.code}.",
                    "acp_response_text": detail,
                },
            )
            return
        except URLError as exc:
            _json_response(
                self,
                502,
                {"error": "acp_unreachable", "detail": f"Could not reach ACP at {ACP_DEFINITION_URL}: {exc.reason}"},
            )
            return
        except TimeoutError:
            _json_response(self, 504, {"error": "acp_timeout", "detail": "ACP request timed out."})
            return
        except json.JSONDecodeError:
            _json_response(self, 502, {"error": "invalid_acp_response", "detail": "ACP returned non-JSON output."})
            return

        if result.get("status") == "error":
            _json_response(self, 502, result)
            return

        document = result.get("document") or {}
        if view == "assembled":
            payload = document
        elif view == "source":
            payload = document.get("definition") or {}
        else:
            _json_response(self, 400, {"error": "invalid_request", "detail": "view must be assembled or source."})
            return
        _json_response(self, 200, payload)


if __name__ == "__main__":
    server = HTTPServer((HOST, PORT), AppHandler)
    print(f"Serving phenotype review app at http://{HOST}:{PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
