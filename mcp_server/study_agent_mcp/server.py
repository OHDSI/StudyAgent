import os

from mcp.server.fastmcp import FastMCP

from study_agent_mcp.tools import register_all

mcp = FastMCP("study-agent")
register_all(mcp)


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()

    if transport in ("sse", "http"):
        host = os.getenv("MCP_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_PORT", "3000"))
        path = os.getenv("MCP_PATH", "/sse")
        mcp.run(transport="streamable-http", host=host, port=port, path=path)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
