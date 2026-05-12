#!/usr/bin/env python3
from __future__ import annotations

import json
import sys

from study_agent_acp.agent import StudyAgent
import study_agent_acp.agent as agent_module


class StubMCPClient:
    def __init__(self) -> None:
        self.calls = []

    def list_tools(self):
        return []

    def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        if name == "case_causal_review_sanitize_row":
            case_row = arguments.get("case_row", {})
            candidate_items = list(case_row.get("candidate_items") or [])
            context_items = list(case_row.get("context_items") or [])
            return {
                "sanitized_row": {
                    "case_id": case_row.get("case_id") or "",
                    "case_summary": case_row.get("case_summary") or "",
                    "index_event": case_row.get("index_event") or {},
                    "candidate_items": candidate_items,
                    "candidate_items_by_domain": {"drug_exposures": candidate_items},
                    "context_items": context_items,
                    "context_items_by_domain": {"labs": context_items} if context_items else {},
                    "case_metadata": case_row.get("case_metadata") or {},
                    "annotations": case_row.get("annotations") or {},
                    "tool_hints": case_row.get("tool_hints") or {},
                },
                "diagnostics": {"sanitization_status": "ok"},
            }
        if name == "case_causal_review_prompt_bundle":
            return {
                "overview": "overview",
                "spec": "spec",
                "output_schema": {"type": "object"},
                "system_prompt": "system",
            }
        if name == "get_case_review_drug_signal_details":
            return {
                "status": "ok",
                "source_record_id": arguments.get("source_record_id"),
                "adverse_event_concept_id": arguments.get("adverse_event_concept_id"),
                "has_disproportional_signal": True,
            }
        if name == "get_case_review_report_literature_stub":
            return {
                "status": "ok",
                "case_id": arguments.get("case_id"),
                "literature_reference_present": True,
            }
        if name == "case_causal_review_build_prompt":
            return {
                "prompt": "main",
                "prompt_payload": {
                    "task": "case_causal_review",
                    "adverse_event_name": arguments.get("adverse_event_name"),
                    "source_type": arguments.get("source_type"),
                    "allowed_domains": arguments.get("allowed_domains") or [],
                    "enrichment": arguments.get("enrichment") or {},
                },
            }
        if name == "case_causal_review_parse_response":
            return {
                "candidates_by_domain": {
                    "drug_exposures": [
                        {
                            "domain": "drug_exposures",
                            "label": "Warfarin",
                            "source_record_id": "drug-1",
                            "why_it_may_contribute": "Bleeding risk",
                            "confidence": "high",
                            "rank": 1,
                            "candidate_role": "primary_suspect",
                            "evidence_basis": "Signal annotation and clinical plausibility",
                        }
                    ]
                },
                "narrative": "Warfarin is a plausible contributor.",
                "mode": "case_causal_review",
                "diagnostics": {"parse_mode": "dict"},
            }
        raise ValueError(f"unexpected tool: {name}")


def _fake_llm(prompt, required_keys=None):
    return {
        "candidates_by_domain": {
            "drug_exposures": [
                {
                    "domain": "drug_exposures",
                    "label": "Warfarin",
                    "source_record_id": "drug-1",
                    "why_it_may_contribute": "Bleeding risk",
                    "confidence": "high",
                    "rank": 1,
                }
            ]
        },
        "narrative": "Warfarin is a plausible contributor.",
        "mode": "case_causal_review",
        "diagnostics": {},
    }


def main() -> int:
    original_call_llm = agent_module.call_llm
    agent_module.call_llm = _fake_llm
    try:
        client = StubMCPClient()
        agent = StudyAgent(mcp_client=client)
        result = agent.run_case_causal_review_flow(
            adverse_event_name="GI bleed",
            case_row={
                "case_id": "case-1",
                "case_summary": "GI bleed after anticoagulation.",
                "index_event": {
                    "domain": "index_event",
                    "label": "GI bleed",
                    "source_record_id": "reaction-1",
                    "annotations": {"adverse_event_concept_id": 321, "adverse_event_meddra_id": "789"},
                },
                "candidate_items": [
                    {
                        "domain": "drug_exposures",
                        "label": "Warfarin",
                        "source_record_id": "drug-1",
                        "subrole": "primary_suspect",
                        "annotations": {"ingredient_concept_id": 123, "ingred_rxcui": "456"},
                    }
                ],
                "context_items": [
                    {
                        "domain": "labs",
                        "label": "INR 4.2",
                        "source_record_id": "lab-1",
                        "subrole": "proximate_marker",
                        "annotations": {},
                    }
                ],
                "case_metadata": {
                    "literature_reference_present": True,
                    "lookup_key": {"primaryid": None, "isr": "6526923"},
                },
                "annotations": {"concept_set_available_domains": ["drug_exposures"]},
                "tool_hints": {
                    "available_expansions": [
                        "get_case_review_drug_signal_details",
                        "get_case_review_report_literature_stub",
                    ],
                    "prefetch_expansions": [
                        "get_case_review_drug_signal_details",
                        "get_case_review_report_literature_stub",
                    ],
                },
            },
            source_type="signal_validation",
            allowed_domains=["drug_exposures"],
        )
    finally:
        agent_module.call_llm = original_call_llm

    assert result["status"] == "ok"
    assert result["flow_name"] == "case_causal_review"
    assert result["mode"] == "case_causal_review"
    assert result["candidates_by_domain"]["drug_exposures"][0]["label"] == "Warfarin"
    assert result["diagnostics"]["optional_enrichment"]["called"] == [
        "get_case_review_drug_signal_details",
        "get_case_review_report_literature_stub",
    ]
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
