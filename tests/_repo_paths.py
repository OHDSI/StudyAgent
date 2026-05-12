from __future__ import annotations

import os
from pathlib import Path


def repo_root() -> Path:
    env_root = os.environ.get("STUDY_AGENT_REPO_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def repo_path(*parts: str) -> Path:
    return repo_root().joinpath(*parts)
