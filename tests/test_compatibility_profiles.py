from __future__ import annotations

import hashlib
import re
from datetime import date
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
PROFILES_PATH = ROOT / "docs" / "COMPATIBILITY_PROFILES.yaml"
SHA256 = re.compile(r"^[0-9a-f]{64}$")
GIT_SHA = re.compile(r"^[0-9a-f]{40}$")
ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _profiles() -> dict[str, dict]:
    payload = yaml.safe_load(PROFILES_PATH.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    return payload["profiles"]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_compatibility_profiles_use_immutable_identifiers() -> None:
    for name, profile in _profiles().items():
        assert "latest" not in name.lower()
        assert profile["kind"] in {"source_baseline", "deployment_artifact"}
        assert GIT_SHA.fullmatch(profile["study_agent"]["commit"])
        assert SHA256.fullmatch(profile["python"]["uv_lock_sha256"])
        if profile["kind"] == "deployment_artifact":
            assert ISO_DATE.fullmatch(profile["released_on"])
            assert ISO_DATE.fullmatch(profile["supported_until"])
            assert date.fromisoformat(profile["supported_until"]) >= date.fromisoformat(
                profile["released_on"]
            )
            artifact = profile["deployment_artifact"]
            assert SHA256.fullmatch(artifact["runtime_zip_sha256"])
            assert SHA256.fullmatch(artifact["runtime_manifest_sha256"])
        else:
            assert profile["released_on"] is None
            assert profile["supported_until"] is None
            assert profile["deployment_artifact"] is None

        r_profile = profile["r"]
        if r_profile["required"]:
            assert SHA256.fullmatch(r_profile["renv_lock_sha256"])
            for package in r_profile["companion_packages"].values():
                assert GIT_SHA.fullmatch(package["commit"])
        else:
            assert set(r_profile) == {"required"}


def test_current_profiles_match_repository_lockfiles() -> None:
    profiles = _profiles()
    current_profiles = [profile for profile in profiles.values() if profile.get("current")]
    assert current_profiles

    uv_lock_sha = _sha256(ROOT / "uv.lock")
    assert all(profile["python"]["uv_lock_sha256"] == uv_lock_sha for profile in current_profiles)

    full_r_profiles = [profile for profile in current_profiles if profile["r"]["required"]]
    assert len(full_r_profiles) == 1
    assert full_r_profiles[0]["r"]["renv_lock_sha256"] == _sha256(ROOT / "renv.lock")
