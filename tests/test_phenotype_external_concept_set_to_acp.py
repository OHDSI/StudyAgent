import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT_PATH = Path("scripts/phenotype_external_concept_set_to_acp.py")
SPEC = importlib.util.spec_from_file_location("phenotype_external_concept_set_to_acp", SCRIPT_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_atlas_export_normalizes_policy_items(tmp_path):
    source = tmp_path / "warfarin.json"
    source.write_text(json.dumps({
        "name": "Warfarin",
        "expression": {"items": [
            {"concept": {"CONCEPT_ID": 1310149, "DOMAIN_ID": "Drug"}, "includeDescendants": True, "includeMapped": False, "isExcluded": False},
            {"concept": {"CONCEPT_ID": 40228152, "DOMAIN_ID": "Drug"}, "includeDescendants": False, "includeMapped": True, "isExcluded": True},
        ]},
    }), encoding="utf-8")

    result = MODULE.parse_atlas_json(source)
    bare_expression = tmp_path / "bare-expression.json"
    bare_expression.write_text(json.dumps({"items": json.loads(source.read_text(encoding="utf-8"))["expression"]["items"]}), encoding="utf-8")
    assert MODULE.parse_atlas_json(bare_expression, name="Warfarin") == result

    assert result == {
        "source": "atlas_json",
        "concept_sets": [{
            "name": "Warfarin",
            "domain": "Drug",
            "items": [
                {"concept_id": 1310149, "domain": "Drug", "include_descendants": True, "include_mapped": False, "is_excluded": False},
                {"concept_id": 40228152, "domain": "Drug", "include_descendants": False, "include_mapped": True, "is_excluded": True},
            ],
        }],
    }


def test_pasted_ids_require_set_name_and_domain_and_dedupe():
    result = MODULE.parse_concept_ids(["1, 2", "2,3"], "Warfarin", "Drug")
    assert result["concept_sets"] == [{"name": "Warfarin", "domain": "Drug", "concept_ids": [1, 2, 3]}]
    with pytest.raises(ValueError, match="concept_set_name_and_domain_required"):
        MODULE.parse_concept_ids(["1"], "", "Drug")
