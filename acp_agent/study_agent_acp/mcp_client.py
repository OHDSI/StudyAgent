from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import anyio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


@dataclass
class StdioMCPClientConfig:
    command: str
    args: List[str]
    env: Optional[Dict[str, str]] = None
    cwd: Optional[str] = None


class StdioMCPClient:
    def __init__(self, config: StdioMCPClientConfig) -> None:
        self._config = config

    def list_tools(self) -> List[Dict[str, Any]]:
        return anyio.run(self._list_tools)

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        return anyio.run(self._call_tool, name, arguments)

    async def _list_tools(self) -> List[Dict[str, Any]]:
        server = StdioServerParameters(
            command=self._config.command,
            args=self._config.args,
            env=self._config.env,
            cwd=self._config.cwd,
        )
        async with stdio_client(server) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.list_tools()
                return [tool.model_dump() for tool in result.tools]

    async def _call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        server = StdioServerParameters(
            command=self._config.command,
            args=self._config.args,
            env=self._config.env,
            cwd=self._config.cwd,
        )
        async with stdio_client(server) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(name=name, arguments=arguments)
                if result.structuredContent is not None:
                    return result.structuredContent
                return {"content": [c.model_dump() for c in result.content or []]}
