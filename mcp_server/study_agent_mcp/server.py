import os
import sys

from mcp.server.fastmcp import FastMCP

from study_agent_mcp.tools import register_all
from study_agent_mcp.retrieval import index_status

mcp = FastMCP("study-agent")
register_all(mcp)

def _log(level: str, message: str) -> None:
    configured = os.getenv("MCP_LOG_LEVEL", "INFO").upper()
    levels = {"DEBUG": 10, "INFO": 20, "WARN": 30, "WARNING": 30, "ERROR": 40, "OFF": 100}
    if levels.get(level, 20) < levels.get(configured, 20):
        return
    if levels.get(configured, 20) >= levels["OFF"]:
        return
    print(f"MCP {level} > {message}", file=sys.stderr)


def _preflight() -> None:
    status = index_status()
    if os.getenv("PHENOTYPE_INDEX_DIR") is None:
        _log(
            "WARN",
            f"PHENOTYPE_INDEX_DIR not set; using default {status['index_dir']}",
        )
    if not status["exists"]:
        _log("ERROR", f"Phenotype index directory missing: {status['index_dir']}")
    catalog = status["files"].get("catalog") or {}
    if not catalog.get("exists"):
        _log("ERROR", f"Phenotype catalog missing: {catalog.get('path')}")
    embed_url = os.getenv("EMBED_URL")
    embed_model = os.getenv("EMBED_MODEL")
    if not embed_url:
        _log("WARN", "EMBED_URL not set; default OpenWebUI embed endpoint will be used.")
    if not embed_model:
        _log("WARN", "EMBED_MODEL not set; default embedding model will be used.")


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    _preflight()

    if transport in ("sse", "http"):
        host = os.getenv("MCP_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_PORT", "3000"))
        path = os.getenv("MCP_PATH", "/mcp")
        mcp.settings.host = host
        mcp.settings.port = port
        mcp.settings.streamable_http_path = path
        if os.getenv("MCP_LOG_LEVEL"):
            mcp.settings.log_level = os.getenv("MCP_LOG_LEVEL", "INFO").upper()
        mcp.run(transport="streamable-http")
    else:
        mcp.run()


if __name__ == "__main__":
    main()
