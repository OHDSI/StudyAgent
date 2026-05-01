import json
import logging
import os
import time
from typing import Any, Dict, List, Optional, Protocol

from study_agent_core.models import (
    CohortLintInput,
    ConceptSetDiffInput,
    KeeperConceptSetsGenerateInput,
    KeeperProfilesGenerateInput,
    PhenotypeIntentSplitInput,
    PhenotypeImprovementsInput,
    PhenotypeRecommendationAdviceInput,
    PhenotypeRecommendationPlanInput,
    PhenotypeRecommendationsInput,
)
from study_agent_core.tools import (
    cohort_lint,
    phenotype_intent_split,
    phenotype_improvements,
    phenotype_recommendation_advice,
    phenotype_recommendation_plan,
    phenotype_recommendations,
    propose_concept_set_diff,
)
from .llm_client import (
    LLMCallResult,
    build_intent_split_prompt,
    build_recommendation_intent_facets_prompt,
    build_advice_prompt,
    build_keeper_concept_set_prompt,
    build_improvements_prompt,
    build_keeper_prompt,
    build_lint_prompt,
    build_prompt,
    call_llm,
    coerce_llm_call_result,
    llm_result_payload,
)

logger = logging.getLogger("study_agent.acp.agent")


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
            "phenotype_recommendation_plan": phenotype_recommendation_plan,
            "phenotype_recommendations": phenotype_recommendations,
            "phenotype_recommendation_advice": phenotype_recommendation_advice,
            "phenotype_improvements": phenotype_improvements,
            "phenotype_intent_split": phenotype_intent_split,
        }

        self._schemas = {
            "propose_concept_set_diff": ConceptSetDiffInput.model_json_schema(),
            "cohort_lint": CohortLintInput.model_json_schema(),
            "phenotype_recommendation_plan": PhenotypeRecommendationPlanInput.model_json_schema(),
            "phenotype_recommendations": PhenotypeRecommendationsInput.model_json_schema(),
            "phenotype_recommendation_advice": PhenotypeRecommendationAdviceInput.model_json_schema(),
            "phenotype_improvements": PhenotypeImprovementsInput.model_json_schema(),
            "phenotype_intent_split": PhenotypeIntentSplitInput.model_json_schema(),
            "keeper_concept_sets_generate": KeeperConceptSetsGenerateInput.model_json_schema(),
            "keeper_profiles_generate": KeeperProfilesGenerateInput.model_json_schema(),
        }

    def _debug_enabled(self) -> bool:
        return os.getenv("STUDY_AGENT_DEBUG", "0") == "1"

    def _log_debug(self, message: str) -> None:
        if self._debug_enabled():
            logger.debug(message)

    def _llm_diagnostics(self, result: Optional[LLMCallResult]) -> Dict[str, Any]:
        if result is None:
            return {
                "llm_status": "disabled",
                "llm_duration_seconds": 0.0,
                "llm_error": "llm_result_missing",
                "llm_parse_stage": None,
                "llm_schema_valid": False,
            }
        diagnostics = {
            "llm_status": result.status,
            "llm_duration_seconds": result.duration_seconds,
            "llm_error": result.error,
            "llm_parse_stage": result.parse_stage,
            "llm_schema_valid": bool(result.schema_valid) if result.schema_valid is not None else result.status == "ok",
            "llm_request_mode": result.request_mode,
        }
        if result.missing_keys:
            diagnostics["llm_missing_keys"] = result.missing_keys
        if os.getenv("LLM_LOG_RESPONSE", "0") == "1":
            diagnostics["llm_raw_response"] = result.raw_response
            diagnostics["llm_content_text"] = result.content_text
        return diagnostics

    def _timed_tool_call(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        started = time.perf_counter()
        result = self.call_tool(name=name, arguments=arguments)
        duration = time.perf_counter() - started
        full_result = result.get("full_result") or {}
        count = full_result.get("count")
        if count is None and isinstance(full_result.get("concepts"), list):
            count = len(full_result.get("concepts") or [])
        logger.debug(
            "keeper tool_call name=%s seconds=%.2f status=%s result_error=%s count=%s",
            name,
            duration,
            result.get("status"),
            full_result.get("error"),
            count,
        )
        return result

    def _fallback_reason_for_llm(self, result: Optional[LLMCallResult]) -> str:
        if result is None:
            return "llm_empty_result"
        mapping = {
            "timeout": "llm_timeout",
            "http_error": "llm_http_error",
            "transport_error": "llm_transport_error",
            "json_parse_failed": "llm_json_parse_failed",
            "schema_mismatch": "llm_schema_mismatch",
            "disabled": "llm_disabled",
        }
        return mapping.get(result.status, "llm_empty_result")

    def _dedupe_concepts(self, concepts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: List[Dict[str, Any]] = []
        seen: set[Any] = set()
        for concept in concepts or []:
            concept_id = concept.get("conceptId")
            if concept_id in (None, ""):
                continue
            if concept_id in seen:
                continue
            seen.add(concept_id)
            deduped.append(concept)
        return deduped

    def _extract_keeper_concept_ids(self, result: Optional[LLMCallResult]) -> tuple[list[int], Optional[str]]:
        if result is None:
            return [], None
        parsed_any = result.parsed_content
        if isinstance(parsed_any, list):
            extracted = []
            for concept in parsed_any:
                if not isinstance(concept, dict):
                    continue
                value = concept.get("conceptId", concept.get("concept_id"))
                try:
                    extracted.append(int(value))
                except (TypeError, ValueError):
                    continue
            if extracted:
                return extracted, "top_level_array"
            return [], None
        if not isinstance(parsed_any, dict):
            return [], None
        parsed = parsed_any
        ids = parsed.get("conceptId")
        if ids not in (None, "") and not isinstance(ids, list):
            try:
                return [int(ids)], "scalar_conceptId"
            except (TypeError, ValueError):
                return [], None
        if isinstance(ids, list):
            extracted: list[int] = []
            for value in ids:
                try:
                    extracted.append(int(value))
                except (TypeError, ValueError):
                    continue
            return extracted, None

        concepts = parsed.get("concepts")
        if isinstance(concepts, list):
            extracted = []
            for concept in concepts:
                if not isinstance(concept, dict):
                    continue
                value = concept.get("conceptId", concept.get("concept_id"))
                try:
                    extracted.append(int(value))
                except (TypeError, ValueError):
                    continue
            if extracted:
                return extracted, "concepts_array"
        return [], None

    def _call_llm(self, prompt: str, required_keys: Optional[List[str]] = None) -> LLMCallResult:
        try:
            return coerce_llm_call_result(call_llm(prompt, required_keys=required_keys))
        except TypeError:
            return coerce_llm_call_result(call_llm(prompt))

    def _hydrate_phenotype_summaries(
        self,
        phenotype_ids: List[str],
        thin_candidates: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        thin_by_id = {row.get("phenotype_id"): row for row in thin_candidates if row.get("phenotype_id")}
        hydrated: List[Dict[str, Any]] = []
        for phenotype_id in phenotype_ids:
            thin = dict(thin_by_id.get(phenotype_id) or {})
            summary_result = self.call_tool(
                name="phenotype_fetch_summary",
                arguments={"phenotype_id": phenotype_id},
            )
            full = summary_result.get("full_result") or {}
            if summary_result.get("status") == "ok" and not full.get("error") and full.get("content"):
                row = dict(thin)
                row.update(full.get("content") or {})
                if not row.get("name"):
                    row["name"] = row.get("phenotype_name") or ""
                hydrated.append(row)
                continue
            if thin:
                hydrated.append(thin)
        return hydrated

    def _compact_text_value(self, value: Any, limit: int = 180) -> str:
        if value in (None, ""):
            return ""
        if isinstance(value, list):
            text = ", ".join(str(item) for item in value if item not in (None, ""))
        elif isinstance(value, dict):
            try:
                text = json.dumps(value, ensure_ascii=True, sort_keys=True)
            except TypeError:
                text = str(value)
        else:
            text = str(value)
        if len(text) > limit:
            return text[:limit] + f"... [truncated {len(text) - limit} chars]"
        return text

    def _build_compact_planning_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        compact_rows: List[Dict[str, Any]] = []
        for row in candidates:
            if not isinstance(row, dict):
                continue
            compact_rows.append(
                {
                    "phenotype_id": row.get("phenotype_id"),
                    "source_dataset": row.get("source_dataset") or "",
                    "name": row.get("name") or row.get("phenotype_name") or "",
                    "short_description": self._compact_text_value(row.get("short_description"), limit=180),
                    "primary_clinical_topic": self._compact_text_value(row.get("primary_clinical_topic"), limit=120),
                    "phenotype_role": self._compact_text_value(row.get("phenotype_role"), limit=48),
                    "care_setting_scope": self._compact_text_value(row.get("care_setting_scope"), limit=64),
                    "population_scope": self._compact_text_value(row.get("population_scope"), limit=120),
                    "target_vs_context_conditions": self._compact_text_value(row.get("target_vs_context_conditions"), limit=220),
                    "exclude_from_primary_topic_match": self._compact_text_value(row.get("exclude_from_primary_topic_match"), limit=180),
                    "recommendation_summary": self._compact_text_value(row.get("recommendation_summary"), limit=220),
                    "retrieval_keywords": (row.get("retrieval_keywords") or [])[:6],
                    "executable_definition_status": row.get("executable_definition_status") or "",
                    "execution_readiness_score": row.get("execution_readiness_score"),
                    "score": row.get("score"),
                    "score_dense": row.get("score_dense"),
                    "score_sparse": row.get("score_sparse"),
                }
            )
        return compact_rows

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
                normalized = self._normalize_result(result)
                return self._wrap_result(name, normalized, warnings=[])
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
            normalized = self._normalize_result(result)
            return self._wrap_result(name, normalized, warnings=["Used core fallback (no MCP client)."])
        except Exception as exc:
            return {
                "status": "error",
                "tool": name,
                "warnings": [f"Core tool call failed: {exc}"],
            }

    def run_phenotype_recommendation_flow(
        self,
        study_intent: str,
        top_k: Optional[int] = None,
        max_results: Optional[int] = None,
        candidate_limit: Optional[int] = None,
        candidate_offset: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not study_intent:
            return {"status": "error", "error": "missing study_intent"}
        if self._mcp_client is None:
            return {"status": "error", "error": "MCP client unavailable"}
        if top_k is None:
            top_k = int(os.getenv("LLM_RECOMMENDATION_TOP_K", "20"))
        if max_results is None:
            max_results = int(os.getenv("LLM_RECOMMENDATION_MAX_RESULTS", "3"))

        search_args = {"query": study_intent, "top_k": top_k}
        if candidate_offset is not None:
            search_args["offset"] = int(candidate_offset)

        self._log_debug(f"phenotype_recommendation: phenotype_search start top_k={top_k} offset={candidate_offset or 0}")
        search_result = self.call_tool(
            name="phenotype_search",
            arguments=search_args,
        )
        self._log_debug(f"phenotype_recommendation: phenotype_search end status={search_result.get('status')}")
        if search_result.get("status") != "ok":
            return {
                "status": "error",
                "error": "phenotype_search_failed",
                "details": search_result,
            }

        full = search_result.get("full_result") or {}
        if full.get("error"):
            payload = {
                "status": "error",
                "error": full.get("error"),
                "details": full,
            }
            if full.get("error") == "phenotype_index_unavailable":
                payload["hint"] = (
                    "Set PHENOTYPE_INDEX_DIR to the phenotype_index directory "
                    "(prefer an absolute path) and verify catalog.jsonl exists."
                )
            return payload
        if "results" not in full and full.get("content"):
            return {
                "status": "error",
                "error": "phenotype_search_failed",
                "details": full,
            }

        all_candidates = full.get("results") or []
        if candidate_limit is None:
            candidate_limit = int(os.getenv("LLM_CANDIDATE_LIMIT", "5"))
        candidate_limit = max(0, int(candidate_limit))
        pre_truncation_count = len(all_candidates)
        self._log_debug(
            "phenotype_recommendation: search candidate counts "
            f"before={pre_truncation_count} shortlist_limit={candidate_limit}"
        )

        self._log_debug("phenotype_recommendation: intent prompt bundle fetch start")
        intent_prompt_bundle = self.call_tool(
            name="phenotype_prompt_bundle",
            arguments={"task": "phenotype_recommendation_intent_facets"},
        )
        self._log_debug(
            f"phenotype_recommendation: intent prompt bundle fetch end status={intent_prompt_bundle.get('status')}"
        )
        intent_prompt_full = intent_prompt_bundle.get("full_result") or {}
        if intent_prompt_bundle.get("status") != "ok" or intent_prompt_full.get("error"):
            return {
                "status": "error",
                "error": "phenotype_prompt_bundle_failed",
                "details": intent_prompt_bundle,
            }

        intent_prompt = build_recommendation_intent_facets_prompt(
            overview=intent_prompt_full.get("overview", ""),
            spec=intent_prompt_full.get("spec", ""),
            output_schema=intent_prompt_full.get("output_schema", {}),
            study_intent=study_intent,
        )
        self._log_debug(f"phenotype_recommendation: intent llm start prompt_chars={len(intent_prompt)}")
        intent_llm_result = self._call_llm(
            intent_prompt,
            required_keys=["plan", "intent_facets", "reasoning_notes"],
        )
        self._log_debug(
            "phenotype_recommendation: intent llm end "
            f"status={intent_llm_result.status} seconds={intent_llm_result.duration_seconds:.2f} parse_stage={intent_llm_result.parse_stage}"
        )
        intent_payload = llm_result_payload(intent_llm_result) or {}
        raw_intent_facets = intent_payload.get("intent_facets")
        intent_facets = raw_intent_facets if isinstance(raw_intent_facets, dict) else {}
        raw_intent_notes = intent_payload.get("reasoning_notes")
        if isinstance(raw_intent_notes, list):
            intent_reasoning_notes = [str(note) for note in raw_intent_notes if note not in (None, "")]
        elif isinstance(raw_intent_notes, str) and raw_intent_notes.strip():
            intent_reasoning_notes = [raw_intent_notes.strip()]
        else:
            intent_reasoning_notes = []
        intent_result = {
            "plan": str(intent_payload.get("plan") or "Extract recommendation intent facets from the study intent."),
            "intent_facets": intent_facets,
            "reasoning_notes": intent_reasoning_notes,
            "mode": "llm" if intent_payload else "stub",
        }

        self._log_debug("phenotype_recommendation: plan prompt bundle fetch start")
        plan_prompt_bundle = self.call_tool(
            name="phenotype_prompt_bundle",
            arguments={"task": "phenotype_recommendation_plan"},
        )
        self._log_debug(
            f"phenotype_recommendation: plan prompt bundle fetch end status={plan_prompt_bundle.get('status')}"
        )
        plan_prompt_full = plan_prompt_bundle.get("full_result") or {}
        if plan_prompt_bundle.get("status") != "ok" or plan_prompt_full.get("error"):
            return {
                "status": "error",
                "error": "phenotype_prompt_bundle_failed",
                "details": plan_prompt_bundle,
            }

        planning_window = int(os.getenv("LLM_PLANNING_CANDIDATE_LIMIT", str(max(candidate_limit, 12))))
        planning_window = max(candidate_limit, planning_window)
        planning_window = min(max(0, planning_window), len(all_candidates))
        planning_seed_candidates = all_candidates[:planning_window]
        planning_candidate_ids = [row.get("phenotype_id") for row in planning_seed_candidates if row.get("phenotype_id")]
        planning_hydrated = self._hydrate_phenotype_summaries(planning_candidate_ids, planning_seed_candidates)
        planning_candidates = self._build_compact_planning_candidates(planning_hydrated)
        self._log_debug(
            "phenotype_recommendation: planning hydration "
            f"candidates={len(planning_candidate_ids)} hydrated={len(planning_candidates)}"
        )

        plan_prompt = build_prompt(
            overview=plan_prompt_full.get("overview", ""),
            spec=plan_prompt_full.get("spec", ""),
            output_schema=plan_prompt_full.get("output_schema", {}),
            study_intent=study_intent,
            candidates=planning_candidates,
            max_results=max_results,
            task="phenotype_recommendation_plan",
            extra_dynamic={
                "maxShortlist": candidate_limit,
                "intent_facets": intent_facets,
            },
        )
        self._log_debug(
            f"phenotype_recommendation: plan llm start prompt_chars={len(plan_prompt)} candidate_count={len(planning_candidates)}"
        )
        plan_llm_result = self._call_llm(
            plan_prompt,
            required_keys=["plan", "intent_facets", "shortlist_ids", "needs_more_search", "reasoning_notes"],
        )
        self._log_debug(
            "phenotype_recommendation: plan llm end "
            f"status={plan_llm_result.status} seconds={plan_llm_result.duration_seconds:.2f} parse_stage={plan_llm_result.parse_stage}"
        )
        plan_llm_payload = llm_result_payload(plan_llm_result)
        planning = phenotype_recommendation_plan(
            study_intent=study_intent,
            catalog_rows=planning_candidates,
            max_shortlist=candidate_limit,
            llm_result=plan_llm_payload,
        )

        shortlist_ids = planning.get("shortlist_ids") or []
        hydrated_candidates = self._hydrate_phenotype_summaries(shortlist_ids, all_candidates)
        self._log_debug(
            "phenotype_recommendation: candidate hydration "
            f"shortlist={len(shortlist_ids)} hydrated={len(hydrated_candidates)}"
        )

        self._log_debug("phenotype_recommendation: final prompt bundle fetch start")
        prompt_bundle = self.call_tool(
            name="phenotype_prompt_bundle",
            arguments={"task": "phenotype_recommendations"},
        )
        self._log_debug(f"phenotype_recommendation: final prompt bundle fetch end status={prompt_bundle.get('status')}")
        prompt_full = prompt_bundle.get("full_result") or {}
        if prompt_bundle.get("status") != "ok" or prompt_full.get("error"):
            return {
                "status": "error",
                "error": "phenotype_prompt_bundle_failed",
                "details": prompt_bundle,
            }

        final_prompt = build_prompt(
            overview=prompt_full.get("overview", ""),
            spec=prompt_full.get("spec", ""),
            output_schema=prompt_full.get("output_schema", {}),
            study_intent=study_intent,
            candidates=hydrated_candidates,
            max_results=max_results,
            task="phenotype_recommendations",
            extra_dynamic={"intent_facets": intent_facets},
        )
        self._log_debug(
            f"phenotype_recommendation: final llm start prompt_chars={len(final_prompt)} candidate_count={len(hydrated_candidates)}"
        )
        llm_result = self._call_llm(final_prompt, required_keys=["plan", "phenotype_recommendations"])
        self._log_debug(
            "phenotype_recommendation: final llm end "
            f"status={llm_result.status} seconds={llm_result.duration_seconds:.2f} parse_stage={llm_result.parse_stage}"
        )

        catalog_rows = []
        for row in hydrated_candidates:
            if not isinstance(row, dict):
                continue
            catalog_rows.append(
                {
                    "phenotype_id": row.get("phenotype_id"),
                    "phenotype_name": row.get("name") or row.get("phenotype_name") or "",
                    "name": row.get("name") or row.get("phenotype_name") or "",
                    "short_description": row.get("short_description"),
                }
            )
        llm_payload = llm_result_payload(llm_result)

        core_result = phenotype_recommendations(
            protocol_text=study_intent,
            catalog_rows=catalog_rows,
            max_results=max_results,
            llm_result=llm_payload,
        )
        llm_used = llm_payload is not None
        fallback_reason = None if llm_used else self._fallback_reason_for_llm(llm_result)
        fallback_mode = None if llm_used else core_result.get("mode")
        if fallback_reason:
            self._log_debug(f"phenotype_recommendation: fallback chosen reason={fallback_reason} mode={fallback_mode}")

        final_diagnostics = self._llm_diagnostics(llm_result)
        planning_diagnostics = self._llm_diagnostics(plan_llm_result)
        intent_diagnostics = self._llm_diagnostics(intent_llm_result)
        diagnostics = dict(final_diagnostics)
        diagnostics["intent_facets"] = intent_diagnostics
        diagnostics["planning"] = planning_diagnostics
        diagnostics["final"] = final_diagnostics

        return {
            "status": "ok",
            "search": full,
            "intent_facets": intent_result,
            "planning": planning,
            "llm_used": llm_used,
            "llm_status": llm_result.status,
            "fallback_reason": fallback_reason,
            "fallback_mode": fallback_mode,
            "candidate_limit": candidate_limit,
            "candidate_offset": candidate_offset or 0,
            "candidate_count": len(hydrated_candidates),
            "candidate_count_before_truncation": pre_truncation_count,
            "plan_prompt_length_chars": len(plan_prompt),
            "prompt_length_chars": len(final_prompt),
            "recommendations": core_result,
            "diagnostics": diagnostics,
        }

    def run_phenotype_recommendation_advice_flow(
        self,
        study_intent: str,
    ) -> Dict[str, Any]:
        if not study_intent:
            return {"status": "error", "error": "missing study_intent"}
        if self._mcp_client is None:
            return {"status": "error", "error": "MCP client unavailable"}

        prompt_bundle = self.call_tool(
            name="phenotype_recommendation_advice",
            arguments={},
        )
        prompt_full = prompt_bundle.get("full_result") or {}
        if prompt_bundle.get("status") != "ok" or prompt_full.get("error"):
            return {
                "status": "error",
                "error": "phenotype_recommendation_advice_prompt_failed",
                "details": prompt_bundle,
            }

        prompt = build_advice_prompt(
            overview=prompt_full.get("overview", ""),
            spec=prompt_full.get("spec", ""),
            output_schema=prompt_full.get("output_schema", {}),
            study_intent=study_intent,
        )
        llm_result = self._call_llm(prompt, required_keys=["advice"])
        llm_payload = llm_result_payload(llm_result)
        core_result = phenotype_recommendation_advice(
            study_intent=study_intent,
            llm_result=llm_payload,
        )

        return {
            "status": "ok",
            "llm_used": llm_payload is not None,
            "llm_status": llm_result.status,
            "fallback_reason": None if llm_payload is not None else self._fallback_reason_for_llm(llm_result),
            "fallback_mode": None if llm_payload is not None else core_result.get("mode"),
            "advice": core_result,
            "diagnostics": self._llm_diagnostics(llm_result),
        }

    def run_phenotype_intent_split_flow(
        self,
        study_intent: str,
    ) -> Dict[str, Any]:
        if not study_intent:
            return {"status": "error", "error": "missing study_intent"}
        if self._mcp_client is None:
            return {"status": "error", "error": "MCP client unavailable"}
        prompt_bundle = self.call_tool(
            name="phenotype_intent_split",
            arguments={},
        )
        prompt_full = prompt_bundle.get("full_result") or {}
        if prompt_bundle.get("status") != "ok" or prompt_full.get("error"):
            return {
                "status": "error",
                "error": "phenotype_intent_split_prompt_failed",
                "details": prompt_bundle,
            }

        prompt = build_intent_split_prompt(
            overview=prompt_full.get("overview", ""),
            spec=prompt_full.get("spec", ""),
            output_schema=prompt_full.get("output_schema", {}),
            study_intent=study_intent,
        )
        self._log_debug("phenotype_intent_split: calling LLM")
        llm_result = self._call_llm(prompt, required_keys=["target_statement", "outcome_statement", "rationale"])
        self._log_debug(
            "phenotype_intent_split: LLM returned "
            f"status={llm_result.status} parse_stage={llm_result.parse_stage}"
        )
        llm_payload = llm_result_payload(llm_result)
        if llm_payload is None:
            return {
                "status": "error",
                "error": "llm_unavailable",
                "diagnostics": self._llm_diagnostics(llm_result),
            }
        core_result = phenotype_intent_split(
            study_intent=study_intent,
            llm_result=llm_payload,
        )

        return {
            "status": "ok",
            "llm_used": True,
            "llm_status": llm_result.status,
            "intent_split": core_result,
            "diagnostics": self._llm_diagnostics(llm_result),
        }

    def run_phenotype_improvements_flow(
        self,
        protocol_text: str,
        cohorts: List[Dict[str, Any]],
        characterization_previews: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        if self._mcp_client is None:
            return {"status": "error", "error": "MCP client unavailable"}
        prompt_bundle = self.call_tool(
            name="phenotype_prompt_bundle",
            arguments={"task": "phenotype_improvements"},
        )
        prompt_full = prompt_bundle.get("full_result") or {}
        if prompt_bundle.get("status") != "ok" or prompt_full.get("error"):
            return {
                "status": "error",
                "error": "phenotype_prompt_bundle_failed",
                "details": prompt_bundle,
            }

        if len(cohorts) > 1:
            cohorts = [cohorts[0]]
        prompt = build_improvements_prompt(
            overview=prompt_full.get("overview", ""),
            spec=prompt_full.get("spec", ""),
            output_schema=prompt_full.get("output_schema", {}),
            study_intent=protocol_text,
            cohorts=cohorts,
        )
        llm_result = coerce_llm_call_result(call_llm(prompt))
        llm_payload = llm_result_payload(llm_result)

        result = self.call_tool(
            name="phenotype_improvements",
            arguments={
                "protocol_text": protocol_text,
                "cohorts": cohorts,
                "characterization_previews": characterization_previews or [],
                "llm_result": llm_payload,
            },
        )
        if isinstance(result, dict):
            result.setdefault("llm_used", llm_payload is not None)
            result.setdefault("llm_status", llm_result.status)
            result.setdefault("diagnostics", self._llm_diagnostics(llm_result))
            result.setdefault("cohort_count", len(cohorts))
        return result

    def run_concept_sets_review_flow(
        self,
        concept_set: Any,
        study_intent: str,
    ) -> Dict[str, Any]:
        if self._mcp_client is None:
            return {"status": "error", "error": "MCP client unavailable"}
        prompt_bundle = self.call_tool(
            name="lint_prompt_bundle",
            arguments={"task": "concept_sets_review"},
        )
        prompt_full = prompt_bundle.get("full_result") or {}
        if prompt_bundle.get("status") != "ok" or prompt_full.get("error"):
            return {
                "status": "error",
                "error": "lint_prompt_bundle_failed",
                "details": prompt_bundle,
            }
        prompt = build_lint_prompt(
            overview=prompt_full.get("overview", ""),
            spec=prompt_full.get("spec", ""),
            output_schema=prompt_full.get("output_schema", {}),
            task="concept-sets-review",
            payload={"concept_set": concept_set, "study_intent": study_intent},
            max_kb=15,
        )
        llm_result = coerce_llm_call_result(call_llm(prompt))
        llm_payload = llm_result_payload(llm_result)
        result = self.call_tool(
            name="propose_concept_set_diff",
            arguments={
                "concept_set": concept_set,
                "study_intent": study_intent,
                "llm_result": llm_payload,
            },
        )
        if isinstance(result, dict):
            result.setdefault("llm_used", llm_payload is not None)
            result.setdefault("llm_status", llm_result.status)
            result.setdefault("diagnostics", self._llm_diagnostics(llm_result))
        return result

    def run_cohort_critique_general_design_flow(
        self,
        cohort: Dict[str, Any],
    ) -> Dict[str, Any]:
        if self._mcp_client is None:
            return {"status": "error", "error": "MCP client unavailable"}
        prompt_bundle = self.call_tool(
            name="phenotype_prompt_bundle",
            arguments={"task": "cohort_critique_general_design"},
        )
        prompt_full = prompt_bundle.get("full_result") or {}
        if prompt_bundle.get("status") != "ok" or prompt_full.get("error"):
            return {
                "status": "error",
                "error": "phenotype_prompt_bundle_failed",
                "details": prompt_bundle,
            }
        prompt = build_lint_prompt(
            overview=prompt_full.get("overview", ""),
            spec=prompt_full.get("spec", ""),
            output_schema=prompt_full.get("output_schema", {}),
            task="cohort-critique-general-design",
            payload={"cohort": cohort},
            max_kb=15,
        )
        llm_result = coerce_llm_call_result(call_llm(prompt))
        llm_payload = llm_result_payload(llm_result)
        result = self.call_tool(
            name="cohort_lint",
            arguments={
                "cohort": cohort,
                "llm_result": llm_payload,
            },
        )
        if isinstance(result, dict):
            result.setdefault("llm_used", llm_payload is not None)
            result.setdefault("llm_status", llm_result.status)
            result.setdefault("diagnostics", self._llm_diagnostics(llm_result))
        return result

    def run_phenotype_validation_review_flow(
        self,
        keeper_row: Dict[str, Any],
        disease_name: str,
    ) -> Dict[str, Any]:
        if self._mcp_client is None:
            return {"status": "error", "error": "MCP client unavailable"}
        if not disease_name:
            return {"status": "error", "error": "missing disease_name"}

        sanitize = self.call_tool(
            name="keeper_sanitize_row",
            arguments={"row": keeper_row},
        )
        sanitize_full = sanitize.get("full_result") or {}
        if sanitize.get("status") != "ok" or sanitize_full.get("error"):
            return {
                "status": "error",
                "error": "phi_detected",
                "details": sanitize,
            }
        sanitized_row = sanitize_full.get("sanitized_row") or {}

        prompt_bundle = self.call_tool(
            name="keeper_prompt_bundle",
            arguments={"disease_name": disease_name},
        )
        prompt_full = prompt_bundle.get("full_result") or {}
        if prompt_bundle.get("status") != "ok" or prompt_full.get("error"):
            return {
                "status": "error",
                "error": "keeper_prompt_bundle_failed",
                "details": prompt_bundle,
            }

        build_prompt = self.call_tool(
            name="keeper_build_prompt",
            arguments={"disease_name": disease_name, "sanitized_row": sanitized_row},
        )
        build_full = build_prompt.get("full_result") or {}
        if build_prompt.get("status") != "ok" or build_full.get("error"):
            return {
                "status": "error",
                "error": "keeper_build_prompt_failed",
                "details": build_prompt,
            }

        system_prompt = prompt_full.get("system_prompt") or ""
        main_prompt = build_full.get("prompt") or ""
        prompt = build_keeper_prompt(
            overview=prompt_full.get("overview", ""),
            spec=prompt_full.get("spec", ""),
            output_schema=prompt_full.get("output_schema", {}),
            system_prompt=system_prompt,
            main_prompt=main_prompt,
        )
        llm_result = coerce_llm_call_result(call_llm(prompt))
        llm_payload = llm_result_payload(llm_result)

        parsed = self.call_tool(
            name="keeper_parse_response",
            arguments={"llm_output": llm_payload},
        )
        if isinstance(parsed, dict):
            parsed.setdefault("llm_used", llm_payload is not None)
            parsed.setdefault("llm_status", llm_result.status)
            parsed.setdefault("diagnostics", self._llm_diagnostics(llm_result))
        return parsed


    def _collect_case_causal_review_enrichment(
        self,
        sanitized_row: Dict[str, Any],
        source_type: str,
        adverse_event_name: str,
    ) -> Dict[str, Any]:
        tool_hints = sanitized_row.get("tool_hints") or {}
        requested = list(tool_hints.get("prefetch_expansions") or [])
        if not requested:
            return {"requested": [], "called": [], "results": {}}

        results: Dict[str, Any] = {}
        called: List[str] = []
        annotations = sanitized_row.get("annotations") or {}
        case_metadata = sanitized_row.get("case_metadata") or {}
        index_event = sanitized_row.get("index_event") or {}
        index_annotations = index_event.get("annotations") or {}
        candidate_items = list(sanitized_row.get("candidate_items") or [])
        case_id = sanitized_row.get("case_id") or ""
        report_lookup_key = (
            case_metadata.get("lookup_key")
            or case_metadata.get("report_lookup_key")
            or index_annotations.get("report_lookup_key")
            or annotations.get("report_lookup_key")
            or ""
        )
        adverse_event_meddra_id = (
            index_annotations.get("adverse_event_meddra_id")
            or index_annotations.get("meddra_id")
            or annotations.get("adverse_event_meddra_id")
            or ""
        )
        adverse_event_concept_id = (
            index_annotations.get("adverse_event_concept_id")
            or annotations.get("adverse_event_concept_id")
            or index_annotations.get("outcome_concept_id")
            or annotations.get("outcome_concept_id")
        )

        for tool_name in requested:
            if tool_name == "get_case_review_concept_set_domain":
                concept_set_id = annotations.get("concept_set_id")
                concept_set_version = annotations.get("concept_set_version")
                if not concept_set_id or concept_set_version in (None, ""):
                    continue
                domains = list(sanitized_row.get("candidate_items_by_domain") or {})[:3]
                tool_results = []
                for domain in domains:
                    tool_result = self.call_tool(
                        name=tool_name,
                        arguments={
                            "concept_set_id": concept_set_id,
                            "concept_set_version": concept_set_version,
                            "domain_name": domain,
                        },
                    )
                    tool_results.append(tool_result.get("full_result") or {})
                if tool_results:
                    results[tool_name] = tool_results
                    called.append(tool_name)
                continue

            if tool_name in {"get_case_review_drug_signal_details", "get_case_review_drug_label_details"}:
                drugs = [item for item in candidate_items if item.get("domain") == "drug_exposures"][:3]
                tool_results = []
                for item in drugs:
                    item_annotations = item.get("annotations") or {}
                    arguments: Dict[str, Any] = {
                        "source_type": source_type,
                        "adverse_event_name": adverse_event_name,
                        "source_record_id": item.get("source_record_id") or "",
                    }
                    if case_id:
                        arguments["case_id"] = case_id
                    value = (
                        item_annotations.get("report_lookup_key")
                        or report_lookup_key
                    )
                    if value not in (None, ""):
                        arguments["report_lookup_key"] = value
                    value = item_annotations.get("ingredient_concept_id")
                    if value not in (None, ""):
                        arguments["ingredient_concept_id"] = value
                    value = item_annotations.get("ingred_rxcui") or item_annotations.get("rxcui")
                    if value not in (None, ""):
                        arguments["ingred_rxcui"] = value
                    value = (
                        item_annotations.get("adverse_event_meddra_id")
                        or adverse_event_meddra_id
                    )
                    if value not in (None, ""):
                        arguments["adverse_event_meddra_id"] = value
                    value = (
                        item_annotations.get("adverse_event_concept_id")
                        or item_annotations.get("outcome_concept_id")
                        or adverse_event_concept_id
                    )
                    if value not in (None, ""):
                        arguments["adverse_event_concept_id"] = value
                    if tool_name == "get_case_review_drug_label_details":
                        value = item_annotations.get("mention_limit")
                        if value not in (None, ""):
                            arguments["mention_limit"] = value
                    tool_result = self.call_tool(name=tool_name, arguments=arguments)
                    tool_results.append(tool_result.get("full_result") or {})
                if tool_results:
                    results[tool_name] = tool_results
                    called.append(tool_name)
                continue

            if tool_name == "get_case_review_report_literature_stub":
                arguments = {
                    "source_type": source_type,
                    "case_id": case_id,
                }
                if report_lookup_key:
                    arguments["report_lookup_key"] = report_lookup_key
                tool_result = self.call_tool(name=tool_name, arguments=arguments)
                results[tool_name] = tool_result.get("full_result") or {}
                called.append(tool_name)
        return {"requested": requested, "called": called, "results": results}

    def run_case_causal_review_flow(
        self,
        adverse_event_name: str,
        case_row: Dict[str, Any],
        source_type: str,
        allowed_domains: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        if self._mcp_client is None:
            return {"status": "error", "error": "MCP client unavailable"}
        if not adverse_event_name:
            return {"status": "error", "error": "missing adverse_event_name"}
        if not isinstance(case_row, dict) or not case_row:
            return {"status": "error", "error": "missing case_row"}
        if source_type not in {"signal_validation", "patient_profile"}:
            return {"status": "error", "error": "invalid source_type"}

        sanitize = self.call_tool(
            name="case_causal_review_sanitize_row",
            arguments={"case_row": case_row, "allowed_domains": allowed_domains or []},
        )
        sanitize_full = sanitize.get("full_result") or {}
        if sanitize.get("status") != "ok" or sanitize_full.get("error"):
            return {
                "status": "error",
                "error": sanitize_full.get("error") or "case_causal_review_sanitize_row_failed",
                "details": sanitize,
            }
        sanitized_row = sanitize_full.get("sanitized_row") or {}
        enrichment = self._collect_case_causal_review_enrichment(
            sanitized_row,
            source_type=source_type,
            adverse_event_name=adverse_event_name,
        )

        prompt_bundle = self.call_tool(
            name="case_causal_review_prompt_bundle",
            arguments={"adverse_event_name": adverse_event_name, "source_type": source_type},
        )
        prompt_full = prompt_bundle.get("full_result") or {}
        if prompt_bundle.get("status") != "ok" or prompt_full.get("error"):
            return {
                "status": "error",
                "error": "case_causal_review_prompt_bundle_failed",
                "details": prompt_bundle,
            }

        build_prompt = self.call_tool(
            name="case_causal_review_build_prompt",
            arguments={
                "adverse_event_name": adverse_event_name,
                "sanitized_row": sanitized_row,
                "source_type": source_type,
                "allowed_domains": allowed_domains or [],
                "enrichment": enrichment.get("results") or {},
            },
        )
        build_full = build_prompt.get("full_result") or {}
        if build_prompt.get("status") != "ok" or build_full.get("error"):
            return {
                "status": "error",
                "error": "case_causal_review_build_prompt_failed",
                "details": build_prompt,
            }

        prompt = build_keeper_concept_set_prompt(
            overview=prompt_full.get("overview", ""),
            spec=prompt_full.get("spec", ""),
            output_schema=prompt_full.get("output_schema", {}),
            system_prompt=prompt_full.get("system_prompt", ""),
            payload=build_full.get("prompt_payload") or {},
            max_kb=18,
        )
        llm_result = self._call_llm(prompt, required_keys=["candidates_by_domain", "narrative", "mode"])
        llm_payload = llm_result_payload(llm_result)

        parsed = self.call_tool(
            name="case_causal_review_parse_response",
            arguments={
                "llm_output": llm_payload,
                "sanitized_row": sanitized_row,
                "allowed_domains": allowed_domains or [],
            },
        )
        parsed_full = parsed.get("full_result") or {}
        if parsed.get("status") != "ok" or parsed_full.get("error"):
            return {
                "status": "error",
                "error": "case_causal_review_parse_response_failed",
                "details": parsed,
            }

        diagnostics = dict(sanitize_full.get("diagnostics") or {})
        diagnostics["optional_enrichment"] = enrichment
        diagnostics.update(parsed_full.get("diagnostics") or {})
        diagnostics.update(self._llm_diagnostics(llm_result))

        return {
            "status": "ok",
            "flow_name": "case_causal_review",
            "mode": parsed_full.get("mode") or "case_causal_review",
            "candidates_by_domain": parsed_full.get("candidates_by_domain") or {},
            "narrative": parsed_full.get("narrative") or "",
            "diagnostics": diagnostics,
            "llm_used": llm_payload is not None,
            "llm_status": llm_result.status,
        }

    def run_keeper_concept_sets_generate_flow(
        self,
        phenotype: str,
        domain_keys: Optional[List[str]] = None,
        vocab_search_provider: str = "",
        phoebe_provider: str = "",
        candidate_limit: int = 50,
        min_record_count: int = 0,
        include_diagnostics: bool = True,
    ) -> Dict[str, Any]:
        if not phenotype:
            return {"status": "error", "error": "missing phenotype"}
        if self._mcp_client is None:
            return {"status": "error", "error": "MCP client unavailable"}

        bundle_result = self._timed_tool_call(
            name="keeper_concept_set_bundle",
            arguments={"phenotype": phenotype},
        )
        bundle_full = bundle_result.get("full_result") or {}
        if bundle_result.get("status") != "ok" or bundle_full.get("error"):
            return {
                "status": "error",
                "error": "keeper_concept_set_bundle_failed",
                "details": bundle_result,
            }

        domain_entries = bundle_full.get("domains") or []
        if domain_keys:
            selected = set(domain_keys)
            domain_entries = [entry for entry in domain_entries if entry.get("parameterName") in selected]
        if not domain_entries:
            return {"status": "error", "error": "no_domains_selected"}

        diagnostics: Dict[str, Any] = {
            "provider_overrides": {
                "vocab_search_provider": vocab_search_provider,
                "phoebe_provider": phoebe_provider,
            },
            "domains_requested": [entry.get("parameterName") for entry in domain_entries],
            "domain_runs": [],
        }
        concept_sets: List[Dict[str, Any]] = []
        domain_outputs: List[Dict[str, Any]] = []
        alternative_diagnosis_terms: List[str] = []

        for entry in domain_entries:
            domain_key = str(entry.get("parameterName") or "")
            logger.info("keeper_concept_sets_generate start domain=%s target=%s", domain_key, "Disease of interest")
            primary = self._run_keeper_concept_set_domain(
                phenotype=phenotype,
                domain_key=domain_key,
                target="Disease of interest",
                query_text=phenotype,
                vocab_search_provider=vocab_search_provider,
                phoebe_provider=phoebe_provider,
                candidate_limit=candidate_limit,
                min_record_count=min_record_count,
            )
            if primary.get("status") != "ok":
                return primary
            concept_sets.extend(primary.get("concepts", []))
            domain_outputs.append(primary.get("domain_output", {}))
            diagnostics["domain_runs"].append(primary.get("diagnostics", {}))
            logger.info(
                "keeper_concept_sets_generate end domain=%s target=%s concepts=%s",
                domain_key,
                "Disease of interest",
                len(primary.get("concepts", []) or []),
            )

            if domain_key == "alternativeDiagnosis":
                alternative_diagnosis_terms = primary.get("terms", []) or []
                continue

            if alternative_diagnosis_terms:
                alt_query = "\n- " + "\n- ".join(alternative_diagnosis_terms)
                logger.info("keeper_concept_sets_generate start domain=%s target=%s", domain_key, "Alternative diagnoses")
                secondary = self._run_keeper_concept_set_domain(
                    phenotype=phenotype,
                    domain_key=domain_key,
                    target="Alternative diagnoses",
                    query_text=alt_query,
                    vocab_search_provider=vocab_search_provider,
                    phoebe_provider=phoebe_provider,
                    candidate_limit=candidate_limit,
                    min_record_count=min_record_count,
                )
                if secondary.get("status") != "ok":
                    return secondary
                concept_sets.extend(secondary.get("concepts", []))
                domain_outputs.append(secondary.get("domain_output", {}))
                diagnostics["domain_runs"].append(secondary.get("diagnostics", {}))
                logger.info(
                    "keeper_concept_sets_generate end domain=%s target=%s concepts=%s",
                    domain_key,
                    "Alternative diagnoses",
                    len(secondary.get("concepts", []) or []),
                )

        result: Dict[str, Any] = {
            "status": "ok",
            "phenotype": phenotype,
            "concept_sets": concept_sets,
            "domains": domain_outputs,
            "llm_used": True,
            "mode": "llm_mcp",
        }
        if include_diagnostics:
            result["diagnostics"] = diagnostics
        return result

    def run_keeper_profiles_generate_flow(
        self,
        cohort_database_schema: str,
        cohort_table: str,
        cohort_definition_id: int,
        cdm_database_schema: str = "",
        sample_size: int = 20,
        person_ids: Optional[List[str]] = None,
        keeper_concept_sets: Optional[List[Dict[str, Any]]] = None,
        phenotype_name: str = "",
        use_descendants: bool = True,
        remove_pii: bool = True,
    ) -> Dict[str, Any]:
        if self._mcp_client is None:
            return {"status": "error", "error": "MCP client unavailable"}
        if not cohort_database_schema:
            return {"status": "error", "error": "missing cohort_database_schema"}
        if not cohort_table:
            return {"status": "error", "error": "missing cohort_table"}
        if not cohort_definition_id:
            return {"status": "error", "error": "missing cohort_definition_id"}
        if not cdm_database_schema:
            return {"status": "error", "error": "missing cdm_database_schema"}
        if not keeper_concept_sets:
            return {"status": "error", "error": "missing keeper_concept_sets"}

        extract_result = self.call_tool(
            name="keeper_profile_extract",
            arguments={
                "cdm_database_schema": cdm_database_schema,
                "cohort_database_schema": cohort_database_schema,
                "cohort_table": cohort_table,
                "cohort_definition_id": int(cohort_definition_id),
                "keeper_concept_sets": keeper_concept_sets,
                "sample_size": int(sample_size),
                "person_ids": person_ids or [],
                "phenotype_name": phenotype_name,
                "use_descendants": bool(use_descendants),
                "remove_pii": bool(remove_pii),
            },
        )
        extract_full = extract_result.get("full_result") or {}
        if extract_result.get("status") != "ok" or extract_full.get("error"):
            return {
                "status": "error",
                "error": "keeper_profile_extract_failed",
                "details": extract_result,
            }

        rows_result = self.call_tool(
            name="keeper_profile_to_rows",
            arguments={
                "profile_records": extract_full.get("profile_records") or [],
                "remove_pii": bool(remove_pii),
            },
        )
        rows_full = rows_result.get("full_result") or {}
        if rows_result.get("status") != "ok" or rows_full.get("error"):
            return {
                "status": "error",
                "error": "keeper_profile_to_rows_failed",
                "details": rows_result,
            }

        return {
            "status": "ok",
            "phenotype_name": phenotype_name,
            "rows": rows_full.get("rows") or [],
            "row_count": int(rows_full.get("row_count") or 0),
            "sample_size_requested": int(extract_full.get("sample_size_requested") or sample_size),
            "sample_size_returned": int(extract_full.get("sample_size_returned") or 0),
            "diagnostics": {
                "record_count": int(extract_full.get("record_count") or 0),
                "sampling_mode": extract_full.get("sampling_mode") or "",
            },
        }

    def _run_keeper_concept_set_domain(
        self,
        phenotype: str,
        domain_key: str,
        target: str,
        query_text: str,
        vocab_search_provider: str,
        phoebe_provider: str,
        candidate_limit: int,
        min_record_count: int,
    ) -> Dict[str, Any]:
        logger.debug(
            "keeper domain start phenotype=%s domain=%s target=%s candidate_limit=%s min_record_count=%s",
            phenotype,
            domain_key,
            target,
            candidate_limit,
            min_record_count,
        )
        bundle_result = self._timed_tool_call(
            name="keeper_concept_set_bundle",
            arguments={"phenotype": phenotype, "domain_key": domain_key, "target": target},
        )
        bundle_full = bundle_result.get("full_result") or {}
        if bundle_result.get("status") != "ok" or bundle_full.get("error"):
            return {
                "status": "error",
                "error": "keeper_concept_set_bundle_failed",
                "details": bundle_result,
            }

        domain = bundle_full.get("domain") or {}
        domains = domain.get("domains") or []
        concept_classes = domain.get("conceptClasses") or []

        terms_prompt = build_keeper_concept_set_prompt(
            overview=bundle_full.get("overview", ""),
            spec=bundle_full.get("spec_generate_terms", ""),
            output_schema=bundle_full.get("output_schema_generate_terms", {}),
            system_prompt=bundle_full.get("term_generation_prompt", ""),
            payload={
                "phenotype": phenotype,
                "query_text": query_text,
                "domain_key": domain_key,
                "target": target,
            },
            max_kb=8,
        )
        terms_result = self._call_llm(terms_prompt, required_keys=["terms"])
        if terms_result.status != "ok":
            return {
                "status": "error",
                "error": "keeper_generate_terms_failed",
                "domain_key": domain_key,
                "target": target,
                "diagnostics": self._llm_diagnostics(terms_result),
            }
        terms_payload = llm_result_payload(terms_result) or {}
        terms = [str(term).strip() for term in (terms_payload.get("terms") or []) if str(term).strip()]
        logger.debug("keeper domain=%s target=%s generated_terms=%s vocab_search_provider=%s", domain_key, target, len(terms), vocab_search_provider)

        search_candidates: List[Dict[str, Any]] = []
        search_errors: List[Dict[str, Any]] = []
        for term in terms:
            search_result = self._timed_tool_call(
                name="vocab_search_standard",
                arguments={
                    "query": term,
                    "domains": domains,
                    "concept_classes": concept_classes,
                    "limit": candidate_limit,
                    "provider": vocab_search_provider,
                },
            )
            search_full = search_result.get("full_result") or {}
            if search_result.get("status") != "ok":
                return {
                    "status": "error",
                    "error": "vocab_search_standard_failed",
                    "domain_key": domain_key,
                    "target": target,
                    "details": search_result,
                }
            if search_full.get("error"):
                search_errors.append({"term": term, "error": search_full.get("error")})
                continue
            for concept in search_full.get("concepts") or []:
                enriched = dict(concept)
                enriched.setdefault("sourceTerm", term)
                enriched.setdefault("sourceStage", "vector_search")
                search_candidates.append(enriched)

        filtered_candidates = [
            concept
            for concept in search_candidates
            if concept.get("recordCount") is None or int(concept.get("recordCount") or 0) >= min_record_count
        ]
        logger.debug(
            "keeper domain=%s target=%s search_candidates=%s filtered_candidates=%s search_errors=%s",
            domain_key,
            target,
            len(search_candidates),
            len(filtered_candidates),
            len(search_errors),
        )
        standard_result = self._timed_tool_call(
            name="vocab_filter_standard_concepts",
            arguments={
                "concepts": filtered_candidates,
                "domains": domains,
                "concept_classes": concept_classes,
                "provider": "db" if vocab_search_provider == "generic_search_api" else "",
            },
        )
        standard_full = standard_result.get("full_result") or {}
        if standard_result.get("status") != "ok" or standard_full.get("error"):
            return {
                "status": "error",
                "error": "vocab_filter_standard_concepts_failed",
                "domain_key": domain_key,
                "target": target,
                "details": standard_result,
            }
        candidate_concepts = self._dedupe_concepts(standard_full.get("concepts") or [])
        logger.debug("keeper domain=%s target=%s standard_candidates=%s", domain_key, target, len(candidate_concepts))

        filter_prompt = build_keeper_concept_set_prompt(
            overview=bundle_full.get("overview", ""),
            spec=bundle_full.get("spec_filter_concepts", ""),
            output_schema=bundle_full.get("output_schema_filter_concepts", {}),
            system_prompt=bundle_full.get("concept_filter_prompt", ""),
            payload={
                "phenotype": phenotype,
                "query_text": query_text,
                "domain_key": domain_key,
                "target": target,
                "candidate_concepts": candidate_concepts,
            },
            max_kb=16,
        )
        filter_result = self._call_llm(filter_prompt, required_keys=["conceptId"])
        selected_ids, filter_salvage_mode = self._extract_keeper_concept_ids(filter_result)
        if filter_result.status != "ok" and not selected_ids:
            return {
                "status": "error",
                "error": "keeper_filter_concepts_failed",
                "domain_key": domain_key,
                "target": target,
                "diagnostics": self._llm_diagnostics(filter_result),
            }

        selected_result = self._timed_tool_call(
            name="vocab_fetch_concepts",
            arguments={
                "concept_ids": selected_ids,
                "concepts": candidate_concepts,
                "provider": "db" if vocab_search_provider == "generic_search_api" else "",
            },
        )
        selected_full = selected_result.get("full_result") or {}
        if selected_result.get("status") != "ok" or selected_full.get("error"):
            return {
                "status": "error",
                "error": "vocab_fetch_concepts_failed",
                "domain_key": domain_key,
                "target": target,
                "details": selected_result,
            }
        selected_concepts = self._dedupe_concepts(selected_full.get("concepts") or [])
        logger.debug("keeper domain=%s target=%s selected_initial=%s", domain_key, target, len(selected_concepts))

        pruned_initial = self._timed_tool_call(
            name="vocab_remove_descendants",
            arguments={"concepts": selected_concepts},
        )
        pruned_initial_full = pruned_initial.get("full_result") or {}
        if pruned_initial.get("status") != "ok" or pruned_initial_full.get("error"):
            return {
                "status": "error",
                "error": "vocab_remove_descendants_failed",
                "domain_key": domain_key,
                "target": target,
                "details": pruned_initial,
            }
        concepts_after_first_prune = self._dedupe_concepts(pruned_initial_full.get("concepts") or [])
        logger.debug(
            "keeper domain=%s target=%s after_first_prune=%s",
            domain_key,
            target,
            len(concepts_after_first_prune),
        )

        phoebe_result = self._timed_tool_call(
            name="phoebe_related_concepts",
            arguments={
                "concept_ids": [concept.get("conceptId") for concept in concepts_after_first_prune if concept.get("conceptId")],
                "provider": phoebe_provider,
            },
        )
        phoebe_full = phoebe_result.get("full_result") or {}
        if phoebe_result.get("status") != "ok":
            return {
                "status": "error",
                "error": "phoebe_related_concepts_failed",
                "domain_key": domain_key,
                "target": target,
                "details": phoebe_result,
            }
        related_concepts = phoebe_full.get("concepts") or []
        if not phoebe_full.get("error"):
            logger.debug(
                "keeper domain=%s target=%s phoebe_raw_related=%s phoebe_provider=%s",
                domain_key,
                target,
                len(related_concepts),
                phoebe_full.get("provider") or phoebe_provider or "",
            )
            filtered_related = self._timed_tool_call(
                name="vocab_filter_standard_concepts",
                arguments={
                    "concepts": related_concepts,
                    "domains": domains,
                    "concept_classes": concept_classes,
                    "provider": "db" if vocab_search_provider == "generic_search_api" else "",
                },
            )
            filtered_related_full = filtered_related.get("full_result") or {}
            if filtered_related.get("status") != "ok" or filtered_related_full.get("error"):
                return {
                    "status": "error",
                    "error": "vocab_filter_standard_concepts_failed",
                    "domain_key": domain_key,
                    "target": target,
                    "details": filtered_related,
                }
            filtered_related_concepts = filtered_related_full.get("concepts") or []
            related_concepts = self._dedupe_concepts([
                concept
                for concept in filtered_related_concepts
                if concept.get("recordCount") is None or int(concept.get("recordCount") or 0) >= min_record_count
            ])
            logger.debug(
                "keeper domain=%s target=%s phoebe_standard_related=%s phoebe_after_record_count=%s",
                domain_key,
                target,
                len(filtered_related_concepts),
                len(related_concepts),
            )
        else:
            related_concepts = []
        logger.debug("keeper domain=%s target=%s related_concepts=%s", domain_key, target, len(related_concepts))

        merged_result = self._timed_tool_call(
            name="vocab_add_nonchildren",
            arguments={"concepts": concepts_after_first_prune, "new_concepts": related_concepts},
        )
        merged_full = merged_result.get("full_result") or {}
        if merged_result.get("status") != "ok" or merged_full.get("error"):
            return {
                "status": "error",
                "error": "vocab_add_nonchildren_failed",
                "domain_key": domain_key,
                "target": target,
                "details": merged_result,
            }
        final_candidates = self._dedupe_concepts(merged_full.get("concepts") or [])
        logger.debug("keeper domain=%s target=%s merged_candidates=%s", domain_key, target, len(final_candidates))

        second_filter_prompt = build_keeper_concept_set_prompt(
            overview=bundle_full.get("overview", ""),
            spec=bundle_full.get("spec_filter_concepts", ""),
            output_schema=bundle_full.get("output_schema_filter_concepts", {}),
            system_prompt=bundle_full.get("concept_filter_prompt", ""),
            payload={
                "phenotype": phenotype,
                "query_text": query_text,
                "domain_key": domain_key,
                "target": target,
                "candidate_concepts": final_candidates,
                "stage": "post_phoebe_filter",
            },
            max_kb=16,
        )
        second_filter_result = self._call_llm(second_filter_prompt, required_keys=["conceptId"])
        final_ids, second_filter_salvage_mode = self._extract_keeper_concept_ids(second_filter_result)
        if second_filter_result.status != "ok" and not final_ids:
            return {
                "status": "error",
                "error": "keeper_filter_concepts_failed",
                "domain_key": domain_key,
                "target": target,
                "diagnostics": self._llm_diagnostics(second_filter_result),
            }

        final_fetch = self._timed_tool_call(
            name="vocab_fetch_concepts",
            arguments={
                "concept_ids": final_ids,
                "concepts": final_candidates,
                "provider": "db" if vocab_search_provider == "generic_search_api" else "",
            },
        )
        final_fetch_full = final_fetch.get("full_result") or {}
        if final_fetch.get("status") != "ok" or final_fetch_full.get("error"):
            return {
                "status": "error",
                "error": "vocab_fetch_concepts_failed",
                "domain_key": domain_key,
                "target": target,
                "details": final_fetch,
            }
        final_pruned = self._timed_tool_call(
            name="vocab_remove_descendants",
            arguments={"concepts": final_fetch_full.get("concepts") or []},
        )
        final_pruned_full = final_pruned.get("full_result") or {}
        if final_pruned.get("status") != "ok" or final_pruned_full.get("error"):
            return {
                "status": "error",
                "error": "vocab_remove_descendants_failed",
                "domain_key": domain_key,
                "target": target,
                "details": final_pruned,
            }
        final_concepts = []
        for concept in self._dedupe_concepts(final_pruned_full.get("concepts") or []):
            enriched = dict(concept)
            enriched["conceptSetName"] = domain_key
            enriched["target"] = target
            final_concepts.append(enriched)
        logger.info(
            "keeper domain complete phenotype=%s domain=%s target=%s final_concepts=%s",
            phenotype,
            domain_key,
            target,
            len(final_concepts),
        )

        diagnostics = {
            "domain_key": domain_key,
            "target": target,
            "llm_generate_terms": self._llm_diagnostics(terms_result),
            "llm_filter_initial": self._llm_diagnostics(filter_result),
            "llm_filter_final": self._llm_diagnostics(second_filter_result),
            "llm_filter_initial_salvage_mode": filter_salvage_mode,
            "llm_filter_final_salvage_mode": second_filter_salvage_mode,
            "search_errors": search_errors,
            "step_counts": [
                {"step": "generate_terms", "count": len(terms)},
                {"step": "vector_search_candidates", "count": len(search_candidates)},
                {"step": "standard_candidates", "count": len(candidate_concepts)},
                {"step": "selected_after_initial_filter", "count": len(selected_concepts)},
                {"step": "selected_after_first_prune", "count": len(concepts_after_first_prune)},
                {"step": "phoebe_related", "count": len(related_concepts)},
                {"step": "merged_candidates", "count": len(final_candidates)},
                {"step": "final_concepts", "count": len(final_concepts)},
            ],
        }
        domain_output = {
            "domain_key": domain_key,
            "target": target,
            "terms": terms,
            "concepts": final_concepts,
            "diagnostics": diagnostics["step_counts"],
        }
        return {
            "status": "ok",
            "terms": terms,
            "concepts": final_concepts,
            "domain_output": domain_output,
            "diagnostics": diagnostics,
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

    def _normalize_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        if isinstance(result, dict) and "result" in result and isinstance(result["result"], dict):
            return result["result"]
        return result

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
