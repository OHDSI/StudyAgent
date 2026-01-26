from __future__ import annotations

from typing import Any, Dict, Optional

from study_agent_core.models import ConceptSetDiffInput
from study_agent_core.tools import propose_concept_set_diff

from ._common import with_meta


def register(mcp: object) -> None:
    @mcp.tool(name="propose_concept_set_diff")
    def propose_concept_set_diff_tool(
        concept_set: Any,
        study_intent: str = "",
        llm_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        validated = ConceptSetDiffInput(
            concept_set=concept_set,
            study_intent=study_intent,
            llm_result=llm_result,
        )
        result = propose_concept_set_diff(
            concept_set=validated.concept_set,
            study_intent=validated.study_intent,
            llm_result=validated.llm_result,
        )
        return with_meta(result, "propose_concept_set_diff")

    return None
