from __future__ import annotations

from contextlib import AsyncExitStack
from dataclasses import dataclass
from threading import Lock
from typing import Any, Dict, List, Optional

import anyio
from anyio.from_thread import start_blocking_portal
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
        self._lock = Lock()
        self._portal = None
        self._session: ClientSession | None = None
        self._exit_stack: AsyncExitStack | None = None

    def list_tools(self) -> List[Dict[str, Any]]:
        self._ensure_session()
        assert self._portal is not None
        return self._portal.call(self._list_tools)

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        self._ensure_session()
        assert self._portal is not None
        return self._portal.call(self._call_tool, name, arguments)

    def health_check(self) -> Dict[str, Any]:
        try:
            self._ensure_session()
            assert self._portal is not None
            return self._portal.call(self._ping)
        except Exception as exc:
            return {"ok": False, "error": str(exc)}

    async def _list_tools(self) -> List[Dict[str, Any]]:
        assert self._session is not None
        result = await self._session.list_tools()
        return [tool.model_dump() for tool in result.tools]

    async def _call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        assert self._session is not None
        result = await self._session.call_tool(name=name, arguments=arguments)
        if result.structuredContent is not None:
            return result.structuredContent
        return {"content": [c.model_dump() for c in result.content or []]}

    async def _ping(self) -> Dict[str, Any]:
        assert self._session is not None
        await self._session.send_ping()
        return {"ok": True}

    def _ensure_session(self) -> None:
        if self._session is not None:
            return
        with self._lock:
            if self._session is not None:
                return
            self._portal = start_blocking_portal()
            assert self._portal is not None
            self._portal.call(self._async_init)

    async def _async_init(self) -> None:
        server = StdioServerParameters(
            command=self._config.command,
            args=self._config.args,
            env=self._config.env,
            cwd=self._config.cwd,
        )
        self._exit_stack = AsyncExitStack()
        read_stream, write_stream = await self._exit_stack.enter_async_context(stdio_client(server))
        session = ClientSession(read_stream, write_stream)
        await self._exit_stack.enter_async_context(session)
        await session.initialize()
        self._session = session

    def close(self) -> None:
        if self._portal is None:
            return
        try:
            self._portal.call(self._async_close)
        finally:
            self._portal.stop()
            self._portal = None

    async def _async_close(self) -> None:
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
        self._exit_stack = None
        self._session = None
