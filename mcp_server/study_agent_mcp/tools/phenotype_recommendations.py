from __future__ import annotations

from typing import Any, Dict, List, Optional

from study_agent_core.models import PhenotypeRecommendationsInput
from study_agent_core.tools import phenotype_recommendations

from ._common import with_meta


def register(mcp: object) -> None:
    @mcp.tool(name="phenotype_recommendations")
    def phenotype_recommendations_tool(
        protocol_text: str,
        catalog_rows: List[Dict[str, Any]],
        max_results: int = 5,
        llm_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        validated = PhenotypeRecommendationsInput(
            protocol_text=protocol_text,
            catalog_rows=catalog_rows,
            max_results=max_results,
            llm_result=llm_result,
        )
        result = phenotype_recommendations(
            protocol_text=validated.protocol_text,
            catalog_rows=validated.catalog_rows,
            max_results=validated.max_results,
            llm_result=validated.llm_result,
        )
        return with_meta(result, "phenotype_recommendations")

    return None
