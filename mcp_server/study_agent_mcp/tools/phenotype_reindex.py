from __future__ import annotations

import os
import subprocess
import sys
from typing import Any, Dict, Optional

from ._common import with_meta


def register(mcp: object) -> None:
    @mcp.tool(name="phenotype_reindex")
    def phenotype_reindex_tool(
        metadata_csv: str,
        output_dir: str,
        definitions_dir: Optional[str] = None,
        build_dense: bool = True,
        require_dense: bool = False,
        batch_size: int = 64,
    ) -> Dict[str, Any]:
        if os.getenv("PHENOTYPE_REINDEX_ALLOW", "0") != "1":
            payload = {"error": "phenotype_reindex is disabled. Set PHENOTYPE_REINDEX_ALLOW=1 to enable."}
            return with_meta(payload, "phenotype_reindex")

        script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "scripts", "build_phenotype_index.py")
        )
        cmd = [
            sys.executable,
            script_path,
            "--metadata-csv",
            metadata_csv,
            "--output-dir",
            output_dir,
            "--batch-size",
            str(batch_size),
        ]
        if definitions_dir:
            cmd.extend(["--definitions-dir", definitions_dir])
        if build_dense:
            cmd.append("--build-dense")
        if require_dense:
            cmd.append("--require-dense")

        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        payload = {
            "status": "ok" if result.returncode == 0 else "error",
            "returncode": result.returncode,
            "stdout": result.stdout[-4000:],
            "stderr": result.stderr[-4000:],
        }
        return with_meta(payload, "phenotype_reindex")

    return None
