from __future__ import annotations

from typing import Any, Dict, Optional

from study_agent_core.models import CohortLintInput
from study_agent_core.tools import cohort_lint

from ._common import with_meta


def register(mcp: object) -> None:
    @mcp.tool(name="cohort_lint")
    def cohort_lint_tool(
        cohort: Dict[str, Any],
        llm_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        validated = CohortLintInput(cohort=cohort, llm_result=llm_result)
        result = cohort_lint(cohort=validated.cohort, llm_result=validated.llm_result)
        return with_meta(result, "cohort_lint")

    return None
