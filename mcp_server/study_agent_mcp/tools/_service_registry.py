from __future__ import annotations

import functools
import os
from typing import Any, Iterable

import yaml


@functools.lru_cache(maxsize=1)
def load_service_registry() -> dict[str, Any]:
    registry_path = os.getenv("STUDY_AGENT_SERVICE_REGISTRY", "docs/SERVICE_REGISTRY.yaml")
    with open(registry_path, "r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data if isinstance(data, dict) else {}


def get_service_definition(service_name: str) -> dict[str, Any]:
    data = load_service_registry()
    services = data.get("services") or {}
    if not isinstance(services, dict):
        return {}
    service = services.get(service_name) or {}
    return service if isinstance(service, dict) else {}


def get_service_validation(service_name: str) -> dict[str, Any]:
    service = get_service_definition(service_name)
    validation = service.get("validation") or {}
    return validation if isinstance(validation, dict) else {}


def get_controlled_identifier_keys(service_name: str, fallback: Iterable[str]) -> frozenset[str]:
    try:
        validation = get_service_validation(service_name)
    except Exception:
        return frozenset(str(key).strip().lower() for key in fallback if str(key).strip())

    keys = validation.get("controlled_identifier_keys") or []
    if not isinstance(keys, list):
        return frozenset(str(key).strip().lower() for key in fallback if str(key).strip())

    configured = {
        str(key).strip().lower()
        for key in keys
        if str(key).strip()
    }
    if configured:
        return frozenset(configured)
    return frozenset(str(key).strip().lower() for key in fallback if str(key).strip())
