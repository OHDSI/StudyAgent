"""Study Agent MCP package.

The server module is deliberately not imported here: configuration must be loaded
before FastMCP is constructed at module import time.
"""

from __future__ import annotations

from typing import Any

__all__ = ["mcp", "main"]


def __getattr__(name: str) -> Any:
    if name in __all__:
        from .server import main, mcp
        return {"main": main, "mcp": mcp}[name]
    raise AttributeError(name)
