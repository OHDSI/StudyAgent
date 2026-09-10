"""Live readiness check for the isolated Groundworkers MCP pilot.

The smoke starts no ACP process and performs no database writes. It uses the
same one-shot streamable-HTTP client ACP will construct from
STUDY_AGENT_GROUNDWORKERS_MCP_URL.
"""

from __future__ import annotations

import os
from typing import Any

from acp_agent.study_agent_acp.mcp_client import HttpMCPClient, HttpMCPClientConfig

MCP_URL = os.getenv("GROUNDWORKERS_MCP_URL", "").strip()
MCP_TOKEN = os.getenv("STUDY_AGENT_GROUNDWORKERS_MCP_TOKEN")
TIMEOUT_SECONDS = int(os.getenv("GROUNDWORKERS_SMOKE_TIMEOUT", "30"))
QUERY = "type 2 diabetes mellitus"


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise AssertionError(f"{label}: expected an object response")
    return value


def main() -> int:
    if not MCP_URL:
        raise RuntimeError("GROUNDWORKERS_MCP_URL must be supplied by the doit task.")

    client = HttpMCPClient(
        HttpMCPClientConfig(url=MCP_URL, token=MCP_TOKEN, timeout=TIMEOUT_SECONDS)
    )
    tool_names = {str(tool.get("name", "")) for tool in client.list_tools()}
    if "concept_ground" not in tool_names:
        raise AssertionError("Groundworkers MCP did not advertise concept_ground.")
    if "system_status" not in tool_names:
        raise AssertionError("Groundworkers MCP did not advertise system_status.")

    status = _require_mapping(client.call_tool("system_status", {}), "system_status")
    graph_status = _require_mapping(
        (status.get("components") or {}).get("omop_graph"),
        "system_status.components.omop_graph",
    )
    if graph_status.get("db_connected") is not True:
        raise AssertionError(
            "Groundworkers can be reached but its OMOP graph database connection "
            "is not ready. Check the read-only TOML configuration and grants."
        )

    response = _require_mapping(
        client.call_tool(
            "concept_ground",
            {
                "query": QUERY,
                "domain": "Condition",
                "standard_only": True,
                "active_only": True,
                "include_embedding": False,
                "limit": 5,
            },
        ),
        "concept_ground",
    )
    results = response.get("results")
    if not isinstance(results, list) or not results:
        raise AssertionError(
            "concept_ground returned no lexical candidates for the fixed non-PHI "
            "Condition query. Check vocabulary visibility and derived relationship tables."
        )
    if not any(
        isinstance(item, dict)
        and str(item.get("concept_name", "")).casefold() == QUERY
        and int(item.get("concept_id") or 0) > 0
        for item in results
    ):
        raise AssertionError(
            "concept_ground did not return the expected exact standard Condition "
            "candidate for the fixed non-PHI query."
        )

    print(
        "Groundworkers readiness smoke passed: streamable HTTP MCP, OMOP graph "
        "connection, and bounded lexical concept grounding are ready for ACP."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
