import json
from typing import Any, Dict
from unittest.mock import MagicMock

import pytest

from study_agent_acp.server import SERVICES


pytestmark = pytest.mark.acp


def test_service_registry_includes_new_flow() -> None:
    endpoints = {entry["name"]: entry["endpoint"] for entry in SERVICES}
    assert endpoints.get("cohort_methods_specifications_recommendation") == "/flows/cohort_methods_specifications_recommendation"
