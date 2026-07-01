#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys

from study_agent_mcp.tools import keeper_concept_sets


class DummyMCP:
    def __init__(self) -> None:
        self.tools = {}

    def tool(self, name: str):
        def decorator(fn):
            self.tools[name] = fn
            return fn

        return decorator


def _registered_tools():
    mcp = DummyMCP()
    keeper_concept_sets.register(mcp)
    return mcp.tools


def _parse_csv_env(name: str, default: str) -> list[str]:
    raw = (os.getenv(name, default) or "").strip()
    return [item.strip() for item in raw.split(",") if item.strip()]


def main() -> int:
    bulk_url = (os.getenv("PHOEBE_BULK_URL", "") or "").strip()
    if not bulk_url:
        raise SystemExit("PHOEBE_BULK_URL must be set for the real Hecate bulk-endpoint smoke test.")

    os.environ["PHOEBE_PROVIDER"] = "hecate_api"
    concept_ids = [int(value) for value in _parse_csv_env("HECATE_SMOKE_CONCEPT_IDS", "4247297,4116092,133419,133713,133714,134294,139750,139757,140048,141232,434590,438983,440050,442143,444462,979932,1567502,1567503,1567505,1567506,1567507,1567508,1595515,1595516,4080901,4089870,4089871,4092364,4095591,4110725,4110726,4110727,4112760,4115298,4116198,4155297,4198437,4244049,4244050,4244051,4244166,4244167,4244168,4244169,4244170,4244488,4244489,4245465,4245466,4245467,4245918,4245919,4246470,4246471,4246472,4246473,4246474,4246790,4246791,4246792,4247221,4247222,4247224,4247225,4247226,4247713,4247714,4247715,4300096,4309088,4309539,4310839,4313171,4313205,35206200,35206201,35206202,35206203,35617772,36712733,37111319,37208039,37397353,40320205,40320210,40390683,40390685,40390688,40390701,40390732,40486090,40488963,40488990,40488993,42535535,42709764,42709765,44794562,44799801,44820607,44822880,44824026,44825201,44828735,44828736,44830977,44834486,44836834,45537805,45542596,45542597,45542598,45542599,45547489,45547490,45547491,45547567,45557052,45561797,45561799,45571501,45585992,45585993,45590890,45605270,45605271,45617577")]
    relationship_ids = _parse_csv_env("HECATE_SMOKE_RELATIONSHIP_IDS", "Ontology-parent")
    min_count = int(os.getenv("HECATE_SMOKE_EXPECT_MIN_COUNT", "1"))

    tools = _registered_tools()
    print(f"Running real Hecate PHOEBE bulk smoke test against: {bulk_url}")
    result = tools["phoebe_related_concepts"](
        concept_ids=concept_ids,
        relationship_ids=relationship_ids,
    )

    assert result["provider"] == "hecate_api"
    assert result["url"]
    assert result["count"] >= min_count
    assert result["count"] == len(result["concepts"])
    assert all("conceptId" in item for item in result["concepts"])
    assert all("sourceConceptId" in item for item in result["concepts"])

    payload = {
        "provider": result["provider"],
        "url": result["url"],
        "requested_concept_ids": concept_ids,
        "requested_relationship_ids": relationship_ids,
        "count": result["count"],
        "sample": result["concepts"][: min(5, len(result["concepts"]))],
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
