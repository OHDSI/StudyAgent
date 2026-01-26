from __future__ import annotations

from typing import Any, Dict, List, Optional

from study_agent_core.models import PhenotypeImprovementsInput
from study_agent_core.tools import phenotype_improvements

from ._common import with_meta


def register(mcp: object) -> None:
    @mcp.tool(name="phenotype_improvements")
    def phenotype_improvements_tool(
        protocol_text: str,
        cohorts: List[Dict[str, Any]],
        characterization_previews: Optional[List[Dict[str, Any]]] = None,
        llm_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        validated = PhenotypeImprovementsInput(
            protocol_text=protocol_text,
            cohorts=cohorts,
            characterization_previews=characterization_previews or [],
            llm_result=llm_result,
        )
        result = phenotype_improvements(
            protocol_text=validated.protocol_text,
            cohorts=validated.cohorts,
            characterization_previews=validated.characterization_previews,
            llm_result=validated.llm_result,
        )
        return with_meta(result, "phenotype_improvements")

    return None
