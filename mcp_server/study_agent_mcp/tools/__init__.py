"""MCP tool registry and auto-registration."""

from __future__ import annotations

import importlib
from typing import Iterable

TOOL_MODULES: list[str] = [
    "study_agent_mcp.tools.concept_set_diff",
    "study_agent_mcp.tools.cohort_lint",
    "study_agent_mcp.tools.phenotype_recommendations",
    "study_agent_mcp.tools.phenotype_improvements",
    "study_agent_mcp.tools.phenotype_search",
    "study_agent_mcp.tools.phenotype_fetch_summary",
    "study_agent_mcp.tools.phenotype_fetch_definition",
    "study_agent_mcp.tools.phenotype_list_similar",
    "study_agent_mcp.tools.phenotype_reindex",
    "study_agent_mcp.tools.phenotype_prompt_bundle",
    "study_agent_mcp.tools.lint_prompt_bundle",
]


def iter_tool_modules() -> Iterable[str]:
    return TOOL_MODULES


def register_all(mcp: object) -> None:
    for module_name in iter_tool_modules():
        module = importlib.import_module(module_name)
        register = getattr(module, "register", None)
        if register is None:
            raise RuntimeError(f"Tool module {module_name} missing register(mcp)")
        register(mcp)


__all__ = ["iter_tool_modules", "register_all", "TOOL_MODULES"]
