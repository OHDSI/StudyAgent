"""Run a non-PHI live LLM smoke test for the computable phenotype prompt contract."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

from study_agent_acp.agent import StudyAgent
from study_agent_acp.llm_client import build_lint_prompt
from study_agent_core.config import apply_config, load_config, load_secret_environment
from study_agent_mcp.tools.phenotype_make_computable import _load_bundle


def _configure(config_path: str, profile: str | None) -> None:
    path = Path(config_path).resolve()
    for name, value in load_secret_environment(cwd=path.parent).items():
        os.environ.setdefault(name, value)
    config = load_config(path, profile=profile, cwd=path.parent, required=True)
    assert config is not None
    apply_config(config)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--profile", default=None)
    args = parser.parse_args()
    _configure(args.config, args.profile)

    bundle = _load_bundle()
    prompt = build_lint_prompt(
        bundle["overview"],
        bundle["spec"],
        bundle["output_schema"],
        "phenotype_make_computable",
        {
            "narrative_statement": (
                "Earliest event of advanced liver disease. "
                "Persons exit at end of observation period."
            ),
            "scope": {
                "index_event": "Advanced liver disease",
                "criterion_domains": {"Advanced liver disease": "Condition"},
                "entry_limit": "First",
                "prior_observation": 0,
                "index_day_boundary": "included",
                "windows": "none",
                "exit_strategy": "observation",
            },
            "concept_candidates": [
                {
                    "conceptId": 4064161,
                    "conceptName": "Cirrhosis of liver",
                    "domainId": "Condition",
                    "standardConcept": "S",
                }
            ],
        },
        max_kb=20,
    )
    result = StudyAgent()._call_llm(
        prompt,
        required_keys=[
            "status",
            "scope_check",
            "concept_sets",
            "cohort_plan",
            "assumptions",
            "warnings",
        ],
    )
    payload = result.parsed_content if isinstance(result.parsed_content, dict) else {}
    print(
        {
            "status": result.status,
            "schema_valid": result.schema_valid,
            "parse_stage": result.parse_stage,
            "missing_keys": result.missing_keys,
            "proposal_status": payload.get("status"),
            "error": result.error,
        }
    )
    return 0 if result.status == "ok" and result.schema_valid else 1


if __name__ == "__main__":
    raise SystemExit(main())
