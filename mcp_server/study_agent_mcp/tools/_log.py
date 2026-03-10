from __future__ import annotations

import os
import sys
from typing import Any


def _level_enabled(level: str) -> bool:
    configured = os.getenv("MCP_LOG_LEVEL", "INFO").upper()
    levels = {"DEBUG": 10, "INFO": 20, "WARN": 30, "WARNING": 30, "ERROR": 40, "OFF": 100}
    if levels.get(level, 20) < levels.get(configured, 20):
        return False
    if levels.get(configured, 20) >= levels["OFF"]:
        return False
    return True


def log_debug(message: str, **fields: Any) -> None:
    if not _level_enabled("DEBUG"):
        return
    extras = ""
    if fields:
        extras = " " + " ".join([f"{k}={v}" for k, v in fields.items()])
    print(f"MCP DEBUG > {message}{extras}", file=sys.stderr)
