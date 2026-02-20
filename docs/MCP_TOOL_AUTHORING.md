# MCP Tool Authoring Guide

This repo uses a simple in-repo modularization pattern for MCP tools. Each tool lives in its own module under `mcp_server/study_agent_mcp/tools/` and exposes a `register(mcp)` function. The MCP server auto-registers all tools listed in the manifest.

## Quick Start

1) Add a new module under `mcp_server/study_agent_mcp/tools/`.
2) Implement `register(mcp)` and define your `@mcp.tool` there.
3) Add the module to `TOOL_MODULES` in `mcp_server/study_agent_mcp/tools/__init__.py`.
4) Re-run your MCP smoke test.

## Minimal Template

```python
from __future__ import annotations

from typing import Any, Dict, Optional

from study_agent_core.models import YourInputModel
from study_agent_core.tools import your_tool_function

from ._common import with_meta


def register(mcp: object) -> None:
    @mcp.tool(name="your_tool_name")
    def your_tool_name_tool(
        payload: Dict[str, Any],
        llm_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        validated = YourInputModel(payload=payload, llm_result=llm_result)
        result = your_tool_function(
            payload=validated.payload,
            llm_result=validated.llm_result,
        )
        return with_meta(result, "your_tool_name")

    return None
```

## Expectations

- **Inputs/outputs:** Use Pydantic models from `core/study_agent_core/models.py` or define local models if needed.
- **Return shape:** Must be JSON-serializable `dict` and include `_meta` (use `with_meta`).
- **Safety:** Tools should not touch local files or governed datasets unless explicitly designed and documented.
- **Naming:** Tool name should match the public MCP name used by clients.

## Manifest

Add your module to the manifest list in `mcp_server/study_agent_mcp/tools/__init__.py`:

```python
TOOL_MODULES = [
    "study_agent_mcp.tools.concept_set_diff",
    "study_agent_mcp.tools.cohort_lint",
    "study_agent_mcp.tools.phenotype_recommendations",
    "study_agent_mcp.tools.phenotype_improvements",
    "study_agent_mcp.tools.your_new_tool",
]
```

## Smoke Test

From the repo root:

```bash
python -c "import study_agent_mcp; print('mcp import ok')"
```

If you need to validate tool schemas or behavior, add or extend tests in `tests/`.
