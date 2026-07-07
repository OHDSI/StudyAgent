import json
import os
import re
from typing import Any, Dict, List, Optional

_TOPIC_TOKEN_RE = re.compile(r"[a-z0-9]+")


class PhenotypeRecommendationMixin:
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

    def _topic_tokens(self, value: Any) -> set[str]:
        if value in (None, ""):
            return set()
        if isinstance(value, dict):
            text = " ".join(str(part) for part in value.values() if part not in (None, ""))
        elif isinstance(value, list):
            text = " ".join(str(part) for part in value if part not in (None, ""))
        else:
            text = str(value)
        return {token for token in _TOPIC_TOKEN_RE.findall(text.lower()) if len(token) > 1}

    def _flatten_text(self, value: Any) -> str:
        if value in (None, ""):
            return ""
        if isinstance(value, dict):
            return " ".join(self._flatten_text(part) for part in value.values())
        if isinstance(value, list):
            return " ".join(self._flatten_text(part) for part in value)
        return str(value).strip().lower()

    def _topic_overlap_score(self, query_tokens: set[str], candidate_tokens: set[str]) -> float:
        if not query_tokens or not candidate_tokens:
            return 0.0
        overlap = query_tokens & candidate_tokens
        if not overlap:
            return 0.0
        coverage = len(overlap) / max(1, len(query_tokens))
        precision = len(overlap) / max(1, len(candidate_tokens))
        return (coverage * 2.0) + precision

    def _normalize_clinical_topic_aliases(self, study_intent: str, aliases: Any) -> List[str]:
        if not isinstance(aliases, list):
            return []
        original_text = self._flatten_text(study_intent)
        original_tokens = self._topic_tokens(study_intent)
        normalized: List[str] = []
        seen: set[str] = set()
        for value in aliases:
            alias = self._flatten_text(value)
            if not alias or alias in seen or alias == original_text:
                continue
            alias_tokens = self._topic_tokens(alias)
            if len(alias_tokens) < 1 or len(alias_tokens) > 8:
                continue
            if alias in {"disease", "condition", "diagnosis", "bleeding", "infection", "disorder", "event"}:
                continue
            if len(alias) > 80:
                continue
            if original_tokens and alias_tokens and alias_tokens == original_tokens:
                continue
            normalized.append(alias)
            seen.add(alias)
            if len(normalized) >= 5:
                break
        return normalized

    def _best_alias_overlap(
        self,
        alias_tokens_list: List[tuple[str, set[str]]],
        candidate_tokens: set[str],
    ) -> tuple[float, str]:
        best_score = 0.0
        best_alias = ""
        for alias, alias_tokens in alias_tokens_list:
            score = self._topic_overlap_score(alias_tokens, candidate_tokens)
            if score > best_score:
                best_score = score
                best_alias = alias
        return best_score, best_alias

    def _effective_intent_facets(self, study_intent: str, intent_facets: Dict[str, Any]) -> Dict[str, Any]:
        effective = dict(intent_facets or {})
        text = self._flatten_text(study_intent)
        role_cues_list = [self._flatten_text(item) for item in (effective.get("role_cues") or []) if item not in (None, "")]
        care_setting_cues_list = [self._flatten_text(item) for item in (effective.get("care_setting_cues") or []) if item not in (None, "")]
        population_cues_list = [self._flatten_text(item) for item in (effective.get("population_cues") or []) if item not in (None, "")]

        phenotype_role = self._flatten_text(effective.get("phenotype_role"))
        if phenotype_role in {"", "unknown"}:
            if any(cue in {"medication", "drug", "medication_based", "drug_based"} for cue in role_cues_list):
                effective["phenotype_role"] = "medication_based"
            elif any(cue == "procedure" for cue in role_cues_list):
                effective["phenotype_role"] = "procedure"
            elif any(cue == "diagnosis" for cue in role_cues_list):
                effective["phenotype_role"] = "diagnosis"

        care_setting = self._flatten_text(effective.get("care_setting"))
        if care_setting in {"", "unknown", "any"}:
            if any(cue == "outpatient" for cue in care_setting_cues_list):
                effective["care_setting"] = "outpatient"
            elif any(cue == "inpatient" for cue in care_setting_cues_list):
                effective["care_setting"] = "inpatient"
            elif any(cue in {"ed", "emergency"} for cue in care_setting_cues_list):
                effective["care_setting"] = "ed"

        if any(phrase in text for phrase in ("medication-based", "drug-based", "based on medication", "based on medications", "based on a medication", "based on drug", "based on drugs")):
            effective["phenotype_role"] = "medication_based"
        if any(phrase in text for phrase in ("outpatient", "ambulatory", "clinic", "office visit")):
            effective["care_setting"] = "outpatient"
        elif any(phrase in text for phrase in ("inpatient", "hospitalized", "hospitalisation", "hospitalization", "admission", "hospital stay")):
            effective["care_setting"] = "inpatient"
        elif any(phrase in text for phrase in ("emergency department", "urgent care")):
            effective["care_setting"] = "ed"

        population_cue = self._flatten_text(effective.get("population_cue"))
        if any(cue == "veterans" or cue == "veteran" for cue in population_cues_list) and "veteran" not in population_cue:
            effective["population_cue"] = (effective.get("population_cue") or "").strip() + ("; veterans" if effective.get("population_cue") else "veterans")
        if any(cue == "va" for cue in population_cues_list) and "va" not in population_cue:
            effective["population_cue"] = (effective.get("population_cue") or "").strip() + ("; va" if effective.get("population_cue") else "va")
        if any(token in text for token in ("veteran", "veterans")) and "veteran" not in population_cue:
            effective["population_cue"] = (effective.get("population_cue") or "").strip() + ("; veterans" if effective.get("population_cue") else "veterans")
        if " va " in f" {text} " and "va" not in population_cue:
            effective["population_cue"] = (effective.get("population_cue") or "").strip() + ("; va" if effective.get("population_cue") else "va")
        if any(token in self._flatten_text(effective.get("population_cue")) for token in ("veteran", "va")):
            effective["geography_coding_preference"] = effective.get("geography_coding_preference") or "va"

        raw_aliases = (
            effective.get("clinical_topic_aliases")
            or effective.get("condition_aliases")
            or effective.get("topic_aliases")
            or []
        )
        effective["clinical_topic_aliases"] = self._normalize_clinical_topic_aliases(
            study_intent=study_intent,
            aliases=raw_aliases,
        )

        return effective

    def _is_explicit_procedure_intent(self, study_intent: str, intent_facets: Dict[str, Any]) -> bool:
        text = self._flatten_text(study_intent)
        inferred_role = self._flatten_text(intent_facets.get("phenotype_role"))
        if inferred_role == "procedure":
            return True
        return any(token in text for token in ("repair", "surgery", "surgical", "procedure", "bypass", "post op", "post-op", "postoperative"))

    def _is_explicit_hospitalization_intent(self, study_intent: str, intent_facets: Dict[str, Any]) -> bool:
        text = self._flatten_text(study_intent)
        care_setting = self._flatten_text(intent_facets.get("care_setting"))
        if care_setting == "inpatient":
            return True
        return any(token in text for token in ("hospitalized", "hospitalisation", "hospitalization", "rehospitalization", "rehospitalisation", "inpatient", "admission", "hospital stay"))

    def _shortlist_target_count(self, max_results: int, max_shortlist: int) -> int:
        return max(1, min(max_shortlist, max(max_results, 3)))

    def _resolve_recommendation_budget(
        self,
        *,
        max_results: int,
        candidate_limit: int,
        available_candidates: int,
        ranked_count: Optional[int] = None,
    ) -> Dict[str, int]:
        shortlist_target_count = self._shortlist_target_count(
            max_results=max_results,
            max_shortlist=candidate_limit,
        )
        planning_window = int(os.getenv("LLM_PLANNING_CANDIDATE_LIMIT", str(max(candidate_limit, 12))))
        planning_window = max(candidate_limit, planning_window)
        planning_window = min(max(0, planning_window), available_candidates)

        budget = {
            "candidate_limit": candidate_limit,
            "shortlist_target_count": shortlist_target_count,
            "planning_window": planning_window,
        }
        if ranked_count is None:
            return budget

        planning_top_band = int(os.getenv("LLM_PLANNING_TOP_BAND", str(max(max_results + 2, 5))))
        planning_top_band = max(1, min(planning_top_band, ranked_count)) if ranked_count else 0
        strict_top_k = min(ranked_count, max(shortlist_target_count + 1, min(candidate_limit, 5)))
        budget["planning_top_band"] = planning_top_band
        budget["strict_top_k"] = strict_top_k
        return budget

    def _shortlist_candidate_block_reason(
        self,
        row: Dict[str, Any],
        intent_facets: Dict[str, Any],
        study_intent: str,
    ) -> Optional[str]:
        intent_role = self._flatten_text(intent_facets.get("phenotype_role"))
        name_text = self._flatten_text(row.get("name") or row.get("phenotype_name"))
        topic_text = self._flatten_text(row.get("primary_clinical_topic"))
        role_text = self._flatten_text(row.get("phenotype_role"))
        signals_text = self._flatten_text(row.get("signals"))
        combined = " ".join(part for part in (name_text, topic_text, role_text, signals_text) if part)

        if "withdrawn" in combined or "[w]" in name_text:
            return "withdrawn"

        if intent_role == "diagnosis":
            if (not self._is_explicit_procedure_intent(study_intent=study_intent, intent_facets=intent_facets)) and any(
                token in combined for token in ("repair", "surgery", "surgical", "bypass", "post op", "post-op", "postoperative")
            ):
                return "procedure_for_diagnosis_intent"
            if (not self._is_explicit_hospitalization_intent(study_intent=study_intent, intent_facets=intent_facets)) and any(
                token in combined for token in ("exacerbation", "hospitalization", "hospitalisation", "rehospitalization", "rehospitalisation")
            ):
                return "narrow_hospitalization_subtype_for_plain_diagnosis"

        return None

    def _candidate_topic_signature(self, row: Dict[str, Any]) -> str:
        topic_text = self._flatten_text(row.get("primary_clinical_topic"))
        name_text = self._flatten_text(row.get("name") or row.get("phenotype_name"))
        if topic_text and name_text:
            return f"{topic_text}||{name_text}"
        if topic_text:
            return topic_text
        return name_text

    def _is_diagnosis_class_candidate(self, row: Dict[str, Any]) -> bool:
        role = self._flatten_text(row.get("phenotype_role"))
        if "diagnos" in role or role in {"condition", "case"}:
            return True
        if any(token in role for token in ("outcome", "complication", "severity", "screen", "risk_score", "visit")):
            return False
        if any(token in role for token in ("covariate", "comorbid")):
            return True
        return False

    def _allow_plain_diagnosis_fill(
        self,
        row: Dict[str, Any],
        intent_facets: Dict[str, Any],
        study_intent: str,
        current_count: int,
    ) -> bool:
        intent_role = self._flatten_text(intent_facets.get("phenotype_role"))
        if intent_role != "diagnosis":
            return True
        if self._is_explicit_hospitalization_intent(study_intent=study_intent, intent_facets=intent_facets):
            return True
        if self._is_explicit_procedure_intent(study_intent=study_intent, intent_facets=intent_facets):
            return True
        if current_count < 2:
            return True
        return self._is_diagnosis_class_candidate(row)

    def _candidate_has_defensible_topic_match(self, row: Dict[str, Any], intent_facets: Dict[str, Any], study_intent: str) -> bool:
        priority = self._candidate_metadata_priority(
            row=row,
            intent_facets=intent_facets,
            search_rank=0,
            study_intent=study_intent,
        )
        kinds = {reason.get("kind") for reason in (priority.get("reasons") or []) if isinstance(reason, dict)}
        has_primary = "topic_primary" in kinds or "dynamic_clinical_alias_match" in kinds
        has_context_only = "context_without_primary" in kinds and not has_primary
        has_mismatch_only = "topic_mismatch" in kinds and not has_primary
        return not (has_context_only or has_mismatch_only)

    def _allow_quality_threshold_fill(
        self,
        row: Dict[str, Any],
        intent_facets: Dict[str, Any],
        study_intent: str,
        current_count: int,
    ) -> bool:
        if current_count < 1:
            return True
        if self._candidate_has_defensible_topic_match(row=row, intent_facets=intent_facets, study_intent=study_intent):
            return True
        return False

    def _should_dedupe_shortlist(self, intent_facets: Dict[str, Any], study_intent: str) -> bool:
        intent_role = self._flatten_text(intent_facets.get("phenotype_role"))
        if intent_role != "diagnosis":
            return False
        return not self._is_explicit_hospitalization_intent(study_intent=study_intent, intent_facets=intent_facets)

    def _dedupe_shortlist_ids(
        self,
        shortlist_ids: List[str],
        candidate_rows_by_id: Dict[str, Dict[str, Any]],
        backfill_ids: List[str],
        target_count: int,
    ) -> tuple[List[str], Dict[str, Any]]:
        deduped: List[str] = []
        seen_ids: set[str] = set()
        seen_signatures: set[str] = set()
        duplicate_topic_ids: List[str] = []

        for phenotype_id in shortlist_ids or []:
            phenotype_id = str(phenotype_id)
            if phenotype_id in seen_ids:
                continue
            row = candidate_rows_by_id.get(phenotype_id) or {}
            signature = self._candidate_topic_signature(row)
            if signature and signature in seen_signatures:
                duplicate_topic_ids.append(phenotype_id)
                continue
            deduped.append(phenotype_id)
            seen_ids.add(phenotype_id)
            if signature:
                seen_signatures.add(signature)

        backfilled_ids: List[str] = []
        if duplicate_topic_ids and len(deduped) < target_count:
            for phenotype_id in backfill_ids:
                phenotype_id = str(phenotype_id)
                if phenotype_id in seen_ids:
                    continue
                row = candidate_rows_by_id.get(phenotype_id) or {}
                signature = self._candidate_topic_signature(row)
                if signature and signature in seen_signatures:
                    continue
                deduped.append(phenotype_id)
                seen_ids.add(phenotype_id)
                backfilled_ids.append(phenotype_id)
                if signature:
                    seen_signatures.add(signature)
                if len(deduped) >= target_count:
                    break

        diagnostics = {
            "duplicate_topic_ids": duplicate_topic_ids,
            "backfilled_ids": backfilled_ids,
            "applied": bool(duplicate_topic_ids),
        }
        return deduped, diagnostics

    def _build_shortlist_reasoning_notes(
        self,
        shortlist_rows: List[Dict[str, Any]],
        intent_facets: Dict[str, Any],
        shortlist_enforcement: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        notes: List[str] = []
        topic = self._compact_text_value(intent_facets.get("condition_or_topic"), limit=80) or "the requested clinical topic"
        role = self._flatten_text(intent_facets.get("phenotype_role")).replace("_", " ") or "phenotype"
        notes.append(f"Selected shortlisted candidates align with {topic} as a {role}-oriented study intent.")

        for row in shortlist_rows[:3]:
            if not isinstance(row, dict):
                continue
            name = row.get("name") or row.get("phenotype_name") or str(row.get("phenotype_id") or "candidate")
            candidate_role = self._flatten_text(row.get("phenotype_role")).replace("_", " ") or "phenotype"
            candidate_topic = self._compact_text_value(row.get("primary_clinical_topic"), limit=80) or name
            notes.append(f"Included {name} as a {candidate_role} candidate focused on {candidate_topic}.")

        enforcement = shortlist_enforcement or {}
        replaced_ids = [str(pid) for pid in (enforcement.get("replaced_ids") or []) if pid not in (None, "")]
        duplicate_topic_ids = [str(pid) for pid in (enforcement.get("duplicate_topic_ids") or []) if pid not in (None, "")]
        if replaced_ids:
            notes.append(
                "Shortlist replaced lower-quality candidates after rerank enforcement: "
                + ", ".join(replaced_ids[:4])
                + "."
            )
        if duplicate_topic_ids:
            notes.append(
                "Near-duplicate topical variants were removed to preserve distinct recommendation coverage: "
                + ", ".join(duplicate_topic_ids[:4])
                + "."
            )
        return notes

    def _enforce_shortlist_against_rerank(
        self,
        shortlist_ids: List[str],
        ranked_candidates: List[Dict[str, Any]],
        intent_facets: Dict[str, Any],
        study_intent: str,
        max_results: int,
        max_shortlist: int,
    ) -> tuple[List[str], Dict[str, Any]]:
        budget = self._resolve_recommendation_budget(
            max_results=max_results,
            candidate_limit=max_shortlist,
            available_candidates=len(ranked_candidates),
            ranked_count=len(ranked_candidates),
        )
        target_count = budget["shortlist_target_count"]
        strict_top_k = budget["strict_top_k"]
        strict_pool = ranked_candidates[:strict_top_k]
        strict_pool_ids = [row.get("phenotype_id") for row in strict_pool if row.get("phenotype_id")]
        strict_pool_set = set(strict_pool_ids)
        strict_pool_by_id = {
            str(row.get("phenotype_id")): row
            for row in strict_pool
            if isinstance(row, dict) and row.get("phenotype_id") not in (None, "")
        }

        blocked_candidate_reasons: Dict[str, str] = {}
        preferred_pool_ids: List[str] = []
        blocked_pool_ids: List[str] = []
        for phenotype_id in strict_pool_ids:
            row = strict_pool_by_id.get(str(phenotype_id)) or {}
            block_reason = self._shortlist_candidate_block_reason(
                row=row,
                intent_facets=intent_facets,
                study_intent=study_intent,
            )
            if block_reason:
                blocked_candidate_reasons[str(phenotype_id)] = block_reason
                blocked_pool_ids.append(str(phenotype_id))
            else:
                preferred_pool_ids.append(str(phenotype_id))

        filtered_shortlist: List[str] = []
        dropped_ids: List[str] = []
        replaced_ids: List[str] = []
        plain_diagnosis_fill_skipped_ids: List[str] = []
        quality_threshold_skipped_ids: List[str] = []
        seen: set[str] = set()
        for phenotype_id in shortlist_ids or []:
            phenotype_id = str(phenotype_id)
            if phenotype_id not in strict_pool_set:
                if phenotype_id not in (None, ""):
                    dropped_ids.append(phenotype_id)
                continue
            if phenotype_id in blocked_candidate_reasons:
                replaced_ids.append(phenotype_id)
                continue
            if phenotype_id not in seen:
                filtered_shortlist.append(phenotype_id)
                seen.add(phenotype_id)

        final_shortlist: List[str] = []
        for phenotype_id in preferred_pool_ids:
            if phenotype_id not in filtered_shortlist or phenotype_id in final_shortlist:
                continue
            row = strict_pool_by_id.get(str(phenotype_id)) or {}
            if not self._allow_plain_diagnosis_fill(
                row=row,
                intent_facets=intent_facets,
                study_intent=study_intent,
                current_count=len(final_shortlist),
            ):
                plain_diagnosis_fill_skipped_ids.append(str(phenotype_id))
                continue
            if not self._allow_quality_threshold_fill(
                row=row,
                intent_facets=intent_facets,
                study_intent=study_intent,
                current_count=len(final_shortlist),
            ):
                quality_threshold_skipped_ids.append(str(phenotype_id))
                continue
            final_shortlist.append(phenotype_id)
        for phenotype_id in preferred_pool_ids:
            if phenotype_id in final_shortlist:
                continue
            row = strict_pool_by_id.get(str(phenotype_id)) or {}
            if not self._allow_plain_diagnosis_fill(
                row=row,
                intent_facets=intent_facets,
                study_intent=study_intent,
                current_count=len(final_shortlist),
            ):
                if str(phenotype_id) not in plain_diagnosis_fill_skipped_ids:
                    plain_diagnosis_fill_skipped_ids.append(str(phenotype_id))
                continue
            if not self._allow_quality_threshold_fill(
                row=row,
                intent_facets=intent_facets,
                study_intent=study_intent,
                current_count=len(final_shortlist),
            ):
                if str(phenotype_id) not in quality_threshold_skipped_ids:
                    quality_threshold_skipped_ids.append(str(phenotype_id))
                continue
            final_shortlist.append(phenotype_id)
            if len(final_shortlist) >= target_count:
                break
        if not final_shortlist:
            final_shortlist = preferred_pool_ids[:target_count]

        dedupe_diagnostics = {
            "duplicate_topic_ids": [],
            "backfilled_ids": [],
            "applied": False,
        }
        if self._should_dedupe_shortlist(intent_facets=intent_facets, study_intent=study_intent):
            final_shortlist, dedupe_diagnostics = self._dedupe_shortlist_ids(
                shortlist_ids=final_shortlist,
                candidate_rows_by_id=strict_pool_by_id,
                backfill_ids=preferred_pool_ids,
                target_count=target_count,
            )

        diagnostics = {
            "strict_top_k": strict_top_k,
            "strict_pool_ids": strict_pool_ids,
            "planner_input_shortlist_ids": [str(pid) for pid in shortlist_ids or [] if pid not in (None, "")],
            "dropped_ids": dropped_ids,
            "replaced_ids": replaced_ids,
            "blocked_pool_ids": blocked_pool_ids,
            "blocked_candidate_reasons": blocked_candidate_reasons,
            "preferred_pool_ids": preferred_pool_ids,
            "plain_diagnosis_fill_skipped_ids": plain_diagnosis_fill_skipped_ids,
            "quality_threshold_skipped_ids": quality_threshold_skipped_ids,
            "duplicate_topic_ids": dedupe_diagnostics.get("duplicate_topic_ids") or [],
            "dedupe_backfilled_ids": dedupe_diagnostics.get("backfilled_ids") or [],
            "dedupe_applied": bool(dedupe_diagnostics.get("applied")),
            "enforced_shortlist_ids": final_shortlist,
            "enforced": final_shortlist != [str(pid) for pid in shortlist_ids or [] if pid not in (None, "")],
        }
        return final_shortlist, diagnostics

    def _candidate_metadata_priority(
        self,
        row: Dict[str, Any],
        intent_facets: Dict[str, Any],
        search_rank: int,
        study_intent: str = "",
    ) -> Dict[str, Any]:
        topic_tokens = self._topic_tokens(intent_facets.get("condition_or_topic"))
        alias_tokens_list = [
            (alias, self._topic_tokens(alias))
            for alias in (intent_facets.get("clinical_topic_aliases") or [])
            if alias not in (None, "")
        ]
        role = self._flatten_text(row.get("phenotype_role"))
        care_setting = self._flatten_text(intent_facets.get("care_setting"))
        candidate_care_setting = self._flatten_text(row.get("care_setting_scope"))
        primary_topic_tokens = self._topic_tokens(row.get("primary_clinical_topic"))
        context_tokens = self._topic_tokens(row.get("target_vs_context_conditions"))
        population_scope = self._flatten_text(row.get("population_scope"))
        population_cue = self._flatten_text(intent_facets.get("population_cue"))
        exclude_tags = self._flatten_text(row.get("exclude_from_primary_topic_match"))
        source_dataset = self._flatten_text(row.get("source_dataset"))
        signals_text = self._flatten_text(row.get("signals"))
        name_text = self._flatten_text(row.get("name") or row.get("phenotype_name"))
        short_description = self._flatten_text(row.get("short_description"))
        recommendation_summary = self._flatten_text(row.get("recommendation_summary"))
        retrieval_keywords = self._flatten_text(row.get("retrieval_keywords"))
        combined_text = " ".join(
            part for part in (name_text, short_description, recommendation_summary, signals_text, retrieval_keywords) if part
        )
        procedure_focus_text = " ".join(
            part for part in (
                name_text,
                self._flatten_text(row.get("primary_clinical_topic")),
                role,
            ) if part
        )
        reasons: List[Dict[str, Any]] = []

        score = 0.0
        explicit_procedure_intent = self._is_explicit_procedure_intent(study_intent=study_intent, intent_facets=intent_facets)

        topic_score = self._topic_overlap_score(topic_tokens, primary_topic_tokens)
        if topic_score:
            delta = topic_score * 8.0
            score += delta
            reasons.append({"kind": "topic_primary", "delta": round(delta, 4), "detail": row.get("primary_clinical_topic") or ""})
        context_score = self._topic_overlap_score(topic_tokens, context_tokens)
        if context_score:
            delta = context_score * 2.5
            score += delta
            reasons.append({"kind": "topic_context", "delta": round(delta, 4), "detail": self._compact_text_value(row.get("target_vs_context_conditions"), limit=120)})

        alias_primary_score, matched_primary_alias = self._best_alias_overlap(alias_tokens_list, primary_topic_tokens)
        if alias_primary_score > topic_score and matched_primary_alias:
            delta = alias_primary_score * 7.0
            score += delta
            reasons.append({
                "kind": "dynamic_clinical_alias_match",
                "delta": round(delta, 4),
                "detail": {"alias": matched_primary_alias, "field": "primary_clinical_topic", "topic": row.get("primary_clinical_topic") or ""},
            })
        alias_context_score, matched_context_alias = self._best_alias_overlap(alias_tokens_list, context_tokens)
        if alias_context_score > context_score and matched_context_alias:
            delta = alias_context_score * 2.0
            score += delta
            reasons.append({
                "kind": "dynamic_clinical_alias_context",
                "delta": round(delta, 4),
                "detail": {"alias": matched_context_alias, "field": "target_vs_context_conditions"},
            })

        best_topic_score = max(topic_score, alias_primary_score)
        best_context_score = max(context_score, alias_context_score)
        if topic_tokens and best_topic_score <= 0.0 and best_context_score > 0.0:
            score -= 3.0
            reasons.append({"kind": "context_without_primary", "delta": -3.0, "detail": "topic only matched context fields"})

        intent_role = self._flatten_text(intent_facets.get("phenotype_role"))
        if topic_tokens and best_topic_score <= 0.0 and best_context_score <= 0.0:
            score -= 8.0
            reasons.append({"kind": "topic_mismatch", "delta": -8.0, "detail": row.get("primary_clinical_topic") or ""})
        if intent_role == "diagnosis":
            if "diagnos" in role or role in {"condition", "case"}:
                score += 4.0
                reasons.append({"kind": "role_match", "delta": 4.0, "detail": row.get("phenotype_role") or ""})
            if any(token in role for token in ("procedure", "surgery", "repair")):
                score -= 4.5
                reasons.append({"kind": "role_penalty_procedure", "delta": -4.5, "detail": row.get("phenotype_role") or ""})
            if any(token in role for token in ("severity", "complication", "outcome", "screen", "risk_score")):
                score -= 3.0
                reasons.append({"kind": "role_penalty_non_diagnosis", "delta": -3.0, "detail": row.get("phenotype_role") or ""})
            if any(token in role for token in ("covariate", "comorbid")):
                score -= 3.5
                reasons.append({"kind": "role_penalty_covariate", "delta": -3.5, "detail": row.get("phenotype_role") or ""})
            if "visit" in role:
                score -= 2.5
                reasons.append({"kind": "role_penalty_visit", "delta": -2.5, "detail": row.get("phenotype_role") or ""})
            if (not explicit_procedure_intent) and any(token in procedure_focus_text for token in ("repair", "surgery", "surgical", "bypass", "post op", "post-op", "postoperative")):
                score -= 6.0
                reasons.append({"kind": "disease_vs_procedure_mismatch", "delta": -6.0, "detail": row.get("name") or row.get("primary_clinical_topic") or ""})
            if source_dataset == "ohdsi_phenotype_library" and any(token in procedure_focus_text for token in ("repair", "surgery", "surgical", "bypass", "post op", "post-op", "postoperative")):
                score -= 2.0
                reasons.append({"kind": "native_ohdsi_cannot_override_procedure", "delta": -2.0, "detail": row.get("source_dataset") or ""})

        if intent_role == "medication_based":
            medication_text = any(token in combined_text for token in ("medication", "drug", "med codes", "insulin", "metformin", "antidiabetic", "meglitinide", "prescription", "therapy"))
            medication_signal = "has_code_system:medication" in signals_text or medication_text
            if "medication" in role or "drug" in role:
                score += 8.0
                reasons.append({"kind": "role_match_medication", "delta": 8.0, "detail": row.get("phenotype_role") or ""})
            elif "diagnos" in role or role in {"condition", "case"}:
                score -= 6.0
                reasons.append({"kind": "role_penalty_plain_diagnosis", "delta": -6.0, "detail": row.get("phenotype_role") or ""})
            elif any(token in role for token in ("covariate", "comorbid")):
                score -= 3.5
                reasons.append({"kind": "role_penalty_covariate_for_medication", "delta": -3.5, "detail": row.get("phenotype_role") or ""})
            if medication_signal:
                score += 4.5
                reasons.append({"kind": "medication_evidence", "delta": 4.5, "detail": row.get("name") or row.get("short_description") or ""})
            else:
                score -= 4.0
                reasons.append({"kind": "missing_medication_evidence", "delta": -4.0, "detail": row.get("name") or row.get("short_description") or ""})
            if any(token in role for token in ("procedure", "screen", "severity", "outcome")):
                score -= 3.5
                reasons.append({"kind": "role_penalty_non_medication", "delta": -3.5, "detail": row.get("phenotype_role") or ""})

        if care_setting and care_setting != "any":
            if candidate_care_setting and care_setting in candidate_care_setting:
                score += 2.0
                reasons.append({"kind": "care_setting_match", "delta": 2.0, "detail": row.get("care_setting_scope") or ""})
            elif candidate_care_setting and candidate_care_setting not in {"any", "unspecified"}:
                score -= 1.5
                reasons.append({"kind": "care_setting_penalty", "delta": -1.5, "detail": row.get("care_setting_scope") or ""})

        if population_cue and population_scope:
            if "veteran" in population_cue and "veteran" in population_scope:
                score += 1.0
                reasons.append({"kind": "population_match_veteran", "delta": 1.0, "detail": row.get("population_scope") or ""})
            if "va" in population_cue and "va" in population_scope:
                score += 1.0
                reasons.append({"kind": "population_match_va", "delta": 1.0, "detail": row.get("population_scope") or ""})
        if "va" in population_cue and "va_cipher" in source_dataset:
            score += 0.75
            reasons.append({"kind": "source_match_va", "delta": 0.75, "detail": row.get("source_dataset") or ""})

        if "context" in exclude_tags:
            score -= 2.0
            reasons.append({"kind": "exclude_context", "delta": -2.0, "detail": row.get("exclude_from_primary_topic_match") or []})
        if "comorbid" in exclude_tags or "covariate" in exclude_tags:
            score -= 3.0
            reasons.append({"kind": "exclude_comorbidity", "delta": -3.0, "detail": row.get("exclude_from_primary_topic_match") or []})
        if any(token in exclude_tags for token in ("procedure", "surgery", "post-op", "postop")):
            score -= 4.0
            reasons.append({"kind": "exclude_procedure", "delta": -4.0, "detail": row.get("exclude_from_primary_topic_match") or []})
        if any(token in exclude_tags for token in ("severity", "complication", "outcome", "screen")):
            score -= 2.5
            reasons.append({"kind": "exclude_non_diagnosis", "delta": -2.5, "detail": row.get("exclude_from_primary_topic_match") or []})

        if "withdrawn" in signals_text or "[w]" in name_text:
            score -= 12.0
            reasons.append({"kind": "status_withdrawn", "delta": -12.0, "detail": row.get("signals") or row.get("name") or ""})
        if "prediction" in signals_text or "prediction" in name_text:
            score -= 4.0
            reasons.append({"kind": "status_prediction", "delta": -4.0, "detail": row.get("signals") or row.get("name") or ""})
        if "screening" in role or "screening" in name_text:
            score -= 2.5
            reasons.append({"kind": "screening_penalty", "delta": -2.5, "detail": row.get("name") or row.get("phenotype_role") or ""})

        readiness_delta = float(row.get("execution_readiness_score") or 0.0) * 0.25
        score += readiness_delta
        reasons.append({"kind": "execution_readiness", "delta": round(readiness_delta, 4), "detail": row.get("execution_readiness_score")})
        rank_delta = max(0.0, 5.0 - float(search_rank)) * 0.02
        score += rank_delta
        reasons.append({"kind": "search_rank_tiebreak", "delta": round(rank_delta, 4), "detail": search_rank})

        return {
            "metadata_score": score,
            "retrieval_score": float(row.get("score") or 0.0),
            "reasons": reasons,
        }

    def _rerank_planning_candidates(
        self,
        candidates: List[Dict[str, Any]],
        intent_facets: Dict[str, Any],
        study_intent: str = "",
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        ranked_rows: List[tuple[float, float, int, Dict[str, Any], Dict[str, Any]]] = []
        for index, row in enumerate(candidates):
            if not isinstance(row, dict):
                continue
            priority = self._candidate_metadata_priority(
                row=row,
                intent_facets=intent_facets,
                search_rank=index,
                study_intent=study_intent,
            )
            metadata_score = float(priority.get("metadata_score") or 0.0)
            retrieval_score = float(priority.get("retrieval_score") or 0.0)
            ranked_rows.append((metadata_score, retrieval_score, -index, row, priority))
        ranked_rows.sort(reverse=True)
        ranked_candidates: List[Dict[str, Any]] = []
        rerank_diagnostics: List[Dict[str, Any]] = []
        for rank_index, (metadata_score, retrieval_score, original_position, row, priority) in enumerate(ranked_rows, start=1):
            ranked_candidates.append(row)
            rerank_diagnostics.append(
                {
                    "rank": rank_index,
                    "original_rank": (-original_position) + 1,
                    "phenotype_id": row.get("phenotype_id"),
                    "name": row.get("name") or row.get("phenotype_name") or "",
                    "metadata_score": round(metadata_score, 4),
                    "retrieval_score": round(retrieval_score, 4),
                    "phenotype_role": row.get("phenotype_role") or "",
                    "primary_clinical_topic": row.get("primary_clinical_topic") or "",
                    "care_setting_scope": row.get("care_setting_scope") or "",
                    "exclude_from_primary_topic_match": row.get("exclude_from_primary_topic_match") or [],
                    "reasons": priority.get("reasons") or [],
                }
            )
        return ranked_candidates, rerank_diagnostics

    def _validate_final_recommendation_payload(
        self,
        llm_payload: Optional[Dict[str, Any]],
        catalog_rows: List[Dict[str, Any]],
    ) -> tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        diagnostics: Dict[str, Any] = {
            "rejected": False,
            "reason": None,
            "invalid_ids": [],
            "duplicate_ids": [],
            "allowed_ids": [row.get("phenotype_id") for row in catalog_rows if row.get("phenotype_id")],
        }
        if not isinstance(llm_payload, dict):
            return llm_payload, diagnostics

        raw_recs = llm_payload.get("phenotype_recommendations")
        if not isinstance(raw_recs, list):
            diagnostics["rejected"] = True
            diagnostics["reason"] = "missing_recommendations"
            return {"plan": llm_payload.get("plan"), "phenotype_recommendations": []}, diagnostics

        if not raw_recs:
            diagnostics["rejected"] = True
            diagnostics["reason"] = "empty_recommendations"
            return {"plan": llm_payload.get("plan"), "phenotype_recommendations": []}, diagnostics

        allowed_set = set(diagnostics["allowed_ids"])
        seen: set[str] = set()
        invalid_ids: List[str] = []
        duplicate_ids: List[str] = []
        valid_unique = 0

        for rec in raw_recs:
            if not isinstance(rec, dict):
                continue
            phenotype_id = rec.get("phenotype_id")
            if phenotype_id in (None, ""):
                continue
            phenotype_id = str(phenotype_id)
            if phenotype_id not in allowed_set:
                invalid_ids.append(phenotype_id)
                continue
            if phenotype_id in seen:
                duplicate_ids.append(phenotype_id)
                continue
            seen.add(phenotype_id)
            valid_unique += 1

        diagnostics["invalid_ids"] = sorted(set(invalid_ids))
        diagnostics["duplicate_ids"] = sorted(set(duplicate_ids))
        diagnostics["valid_unique_count"] = valid_unique
        if diagnostics["invalid_ids"] or diagnostics["duplicate_ids"] or valid_unique <= 0:
            diagnostics["rejected"] = True
            if diagnostics["invalid_ids"]:
                diagnostics["reason"] = "invalid_ids"
            elif diagnostics["duplicate_ids"]:
                diagnostics["reason"] = "duplicate_ids"
            else:
                diagnostics["reason"] = "no_valid_recommendations"
            return {"plan": llm_payload.get("plan"), "phenotype_recommendations": []}, diagnostics

        return llm_payload, diagnostics

    def _build_compact_final_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        compact_rows: List[Dict[str, Any]] = []
        for row in candidates or []:
            if not isinstance(row, dict):
                continue
            compact_rows.append(
                {
                    "phenotype_id": row.get("phenotype_id"),
                    "source_dataset": row.get("source_dataset"),
                    "name": row.get("name") or row.get("phenotype_name") or "",
                    "short_description": row.get("short_description") or "",
                    "primary_clinical_topic": row.get("primary_clinical_topic") or "",
                    "phenotype_role": row.get("phenotype_role") or "",
                    "care_setting_scope": row.get("care_setting_scope") or "",
                    "population_scope": row.get("population_scope") or "",
                    "recommendation_summary": row.get("recommendation_summary") or "",
                    "executable_definition_status": row.get("executable_definition_status") or "",
                    "execution_readiness_score": row.get("execution_readiness_score"),
                    "score": row.get("score"),
                }
            )
        return compact_rows

    def _default_final_recommendation_plan(self, study_intent: str) -> str:
        return "Rank phenotypes matching the study intent."

    def _default_final_recommendation_justification(self, row: Dict[str, Any]) -> str:
        phenotype_role = self._flatten_text(row.get("phenotype_role")).replace("_", " ") or "phenotype"
        name = row.get("phenotype_name") or row.get("name") or "selected phenotype"
        justification = f"Selected from the top reranked shortlisted candidates as a clinically aligned {phenotype_role} match."
        if len(justification) > 200:
            return "Selected from the top reranked shortlisted candidates as a clinically aligned match."
        return justification

    def _build_deterministic_final_payload(
        self,
        llm_payload: Optional[Dict[str, Any]],
        catalog_rows: List[Dict[str, Any]],
        max_results: int,
        study_intent: str,
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        selected_rows = [row for row in catalog_rows[: max(0, max_results)] if isinstance(row, dict)]
        selected_ids = [str(row.get("phenotype_id")) for row in selected_rows if row.get("phenotype_id") not in (None, "")]
        selected_set = set(selected_ids)
        explanation_by_id: Dict[str, Dict[str, Any]] = {}
        duplicate_ids: List[str] = []
        invalid_ids: List[str] = []

        if isinstance(llm_payload, dict):
            raw_recs = llm_payload.get("phenotype_recommendations")
            if isinstance(raw_recs, list):
                for rec in raw_recs:
                    if not isinstance(rec, dict):
                        continue
                    phenotype_id = rec.get("phenotype_id")
                    if phenotype_id in (None, ""):
                        continue
                    phenotype_id = str(phenotype_id)
                    if phenotype_id not in selected_set:
                        invalid_ids.append(phenotype_id)
                        continue
                    if phenotype_id in explanation_by_id:
                        duplicate_ids.append(phenotype_id)
                        continue
                    explanation_by_id[phenotype_id] = rec

        recommendations: List[Dict[str, Any]] = []
        matched_ids: List[str] = []
        defaulted_ids: List[str] = []
        for row in selected_rows:
            phenotype_id = str(row.get("phenotype_id") or "")
            if not phenotype_id:
                continue
            llm_rec = explanation_by_id.get(phenotype_id) or {}
            justification = llm_rec.get("justification") if isinstance(llm_rec.get("justification"), str) else ""
            confidence = llm_rec.get("confidence")
            if not justification.strip():
                justification = self._default_final_recommendation_justification(row)
                defaulted_ids.append(phenotype_id)
            else:
                matched_ids.append(phenotype_id)
            if not isinstance(confidence, (int, float)):
                confidence = None
            recommendations.append(
                {
                    "phenotype_id": phenotype_id,
                    "phenotype_name": row.get("phenotype_name") or row.get("name") or "",
                    "justification": justification[:200],
                    "confidence": float(confidence) if isinstance(confidence, (int, float)) else None,
                }
            )

        plan = ""
        if isinstance(llm_payload, dict) and isinstance(llm_payload.get("plan"), str):
            plan = llm_payload.get("plan") or ""
        if not plan.strip():
            plan = self._default_final_recommendation_plan(study_intent)

        payload = {
            "plan": plan[:300],
            "phenotype_recommendations": recommendations,
        }
        diagnostics = {
            "selected_ids": selected_ids,
            "matched_llm_ids": matched_ids,
            "defaulted_ids": defaulted_ids,
            "invalid_llm_ids": sorted(set(invalid_ids)),
            "duplicate_llm_ids": sorted(set(duplicate_ids)),
            "used_llm_justification_count": len(matched_ids),
            "used_default_justification_count": len(defaulted_ids),
        }
        return payload, diagnostics

