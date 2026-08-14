#!/usr/bin/env python3
"""Backward-compatible wrapper for the installed phenotype-index builder."""

from study_agent_mcp.phenotype_index_builder import main


if __name__ == "__main__":
    raise SystemExit(main())
