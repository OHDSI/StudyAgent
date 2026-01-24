import os
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP

from study_agent_core.models import (
    CohortLintInput,
    ConceptSetDiffInput,
    PhenotypeImprovementsInput,
    PhenotypeRecommendationsInput,
)
from study_agent_core.tools import (
    cohort_lint,
    phenotype_improvements,
    phenotype_recommendations,
    propose_concept_set_diff,
)

mcp = FastMCP("study-agent")


def _with_meta(payload: Dict[str, Any], tool_name: str) -> Dict[str, Any]:
    if "_meta" not in payload:
        payload["_meta"] = {"tool": tool_name}
    return payload


@mcp.tool()
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
    return _with_meta(result, "propose_concept_set_diff")


@mcp.tool()
def cohort_lint_tool(
    cohort: Dict[str, Any],
    llm_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    validated = CohortLintInput(cohort=cohort, llm_result=llm_result)
    result = cohort_lint(cohort=validated.cohort, llm_result=validated.llm_result)
    return _with_meta(result, "cohort_lint")


@mcp.tool()
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
    return _with_meta(result, "phenotype_recommendations")


@mcp.tool()
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
    return _with_meta(result, "phenotype_improvements")


def main() -> None:
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()

    if transport in ("sse", "http"):
        host = os.getenv("MCP_HOST", "0.0.0.0")
        port = int(os.getenv("MCP_PORT", "3000"))
        path = os.getenv("MCP_PATH", "/sse")
        mcp.run(transport="streamable-http", host=host, port=port, path=path)
    else:
        mcp.run()


if __name__ == "__main__":
    main()
