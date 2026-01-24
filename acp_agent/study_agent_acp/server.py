from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any, Dict, Optional

from .agent import StudyAgent
from .mcp_client import StdioMCPClient, StdioMCPClientConfig


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
    handler.wfile.write(body)


class ACPRequestHandler(BaseHTTPRequestHandler):
    agent: StudyAgent
    mcp_client: Optional[StdioMCPClient]

    def log_message(self, format: str, *args: Any) -> None:
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
        _write_json(self, 404, {"error": "not_found"})

    def do_POST(self) -> None:
        if self.path != "/tools/call":
            _write_json(self, 404, {"error": "not_found"})
            return
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

        result = self.agent.call_tool(name=name, arguments=arguments, confirm=confirm)
        status = 200 if result.get("status") != "error" else 500
        _write_json(self, status, result)


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


def main(host: str = "127.0.0.1", port: int = 8765) -> None:
    import os

    mcp_command = os.getenv("STUDY_AGENT_MCP_COMMAND")
    mcp_args = os.getenv("STUDY_AGENT_MCP_ARGS", "")
    allow_core_fallback = os.getenv("STUDY_AGENT_ALLOW_CORE_FALLBACK", "1") == "1"

    args_list = [arg for arg in mcp_args.split(" ") if arg]
    agent, mcp_client = _build_agent(mcp_command, args_list, allow_core_fallback)

    class Handler(ACPRequestHandler):
        agent = None
        mcp_client = None

    Handler.agent = agent
    Handler.mcp_client = mcp_client
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
