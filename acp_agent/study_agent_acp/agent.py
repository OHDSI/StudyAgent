from typing import Any, Dict, List, Optional, Protocol

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


class MCPClient(Protocol):
    def list_tools(self) -> List[Dict[str, Any]]:
        ...

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        ...


class StudyAgent:
    def __init__(
        self,
        mcp_client: Optional[MCPClient] = None,
        allow_core_fallback: bool = True,
        confirmation_required_tools: Optional[List[str]] = None,
    ) -> None:
        self._mcp_client = mcp_client
        self._allow_core_fallback = allow_core_fallback
        self._confirmation_required = set(confirmation_required_tools or [])

        self._core_tools = {
            "propose_concept_set_diff": propose_concept_set_diff,
            "cohort_lint": cohort_lint,
            "phenotype_recommendations": phenotype_recommendations,
            "phenotype_improvements": phenotype_improvements,
        }

        self._schemas = {
            "propose_concept_set_diff": ConceptSetDiffInput.model_json_schema(),
            "cohort_lint": CohortLintInput.model_json_schema(),
            "phenotype_recommendations": PhenotypeRecommendationsInput.model_json_schema(),
            "phenotype_improvements": PhenotypeImprovementsInput.model_json_schema(),
        }

    def list_tools(self) -> List[Dict[str, Any]]:
        if self._mcp_client is not None:
            return self._mcp_client.list_tools()

        return [
            {
                "name": name,
                "description": "Core tool (fallback when MCP is unavailable).",
                "input_schema": schema,
            }
            for name, schema in self._schemas.items()
        ]

    def call_tool(self, name: str, arguments: Dict[str, Any], confirm: bool = False) -> Dict[str, Any]:
        if name in self._confirmation_required and not confirm:
            return {
                "status": "needs_confirmation",
                "tool": name,
                "warnings": ["Tool execution requires confirmation."],
            }

        if self._mcp_client is not None:
            try:
                result = self._mcp_client.call_tool(name, arguments)
                return self._wrap_result(name, result, warnings=[])
            except Exception as exc:
                return {
                    "status": "error",
                    "tool": name,
                    "warnings": [f"MCP tool call failed: {exc}"],
                }

        if not self._allow_core_fallback:
            return {
                "status": "error",
                "tool": name,
                "warnings": ["MCP client unavailable and core fallback disabled."],
            }

        if name not in self._core_tools:
            return {
                "status": "error",
                "tool": name,
                "warnings": ["Unknown tool name."],
            }

        try:
            result = self._core_tools[name](**arguments)
            return self._wrap_result(name, result, warnings=["Used core fallback (no MCP client)."])
        except Exception as exc:
            return {
                "status": "error",
                "tool": name,
                "warnings": [f"Core tool call failed: {exc}"],
            }

    def _wrap_result(self, name: str, result: Dict[str, Any], warnings: List[str]) -> Dict[str, Any]:
        safe_summary = self._safe_summary(result)
        return {
            "status": "ok",
            "tool": name,
            "warnings": warnings,
            "safe_summary": safe_summary,
            "full_result": result,
        }

    def _safe_summary(self, result: Dict[str, Any]) -> Dict[str, Any]:
        if "error" in result:
            return {"error": result.get("error")}

        summary = {"plan": result.get("plan")}
        for key in (
            "findings",
            "patches",
            "actions",
            "risk_notes",
            "phenotype_recommendations",
            "phenotype_improvements",
        ):
            if isinstance(result.get(key), list):
                summary[f"{key}_count"] = len(result.get(key) or [])
        return summary
