from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict

from ._common import with_meta

_R_LIBS = "/ai-agent/HadesProject/OHDSI-Study-Agent/renv/library/linux-ubuntu-noble/R-4.5/x86_64-pc-linux-gnu"
_FORBIDDEN_IDENTIFIERS = (
    "assign", "assigninnamespace", "attach", "connection", "download", "download.file",
    "dyn.load", "eval", "file", "get", "getnamespace", "library.dynam", "load",
    "loadnamespace", "parse", "pipe", "readlines", "readrds", "readurl", "save",
    "serialize", "setwd", "shell", "socket", "source", "system", "system2", "unlink",
    "url", "write", "writelines",
)
_FORBIDDEN_NAMESPACE_PREFIXES = ("base::", "utils::", "methods::", "parallel::", "tools::", "httr::", "curl::")


def _unsafe_r_constructs(capr_code: str) -> list[str]:
    """Reject source capable of process, filesystem, network, or reflective execution."""
    import re

    normalized = capr_code.lower().replace("`", "")
    normalized = re.sub(r'(["\'])(?:\\.|(?!\1).)*\1', '""', normalized, flags=re.DOTALL)
    normalized = re.sub(r"(?m)#.*$", "", normalized)
    hits = [name for name in _FORBIDDEN_IDENTIFIERS if re.search(rf"(?<![a-z0-9_.]){re.escape(name)}(?![a-z0-9_.])", normalized)]
    hits.extend(prefix for prefix in _FORBIDDEN_NAMESPACE_PREFIXES if prefix in normalized)
    return sorted(set(hits))


def validate_capr_source(capr_code: str, timeout_seconds: int = 60) -> Dict[str, Any]:
    """Execute deterministic Capr source and require CirceR SQL compilation."""
    if not capr_code.strip():
        return {"status": "failed", "messages": ["empty_capr_code"]}
    hits = _unsafe_r_constructs(capr_code)
    if hits:
        return {"status": "failed", "messages": [f"forbidden_r_constructs:{','.join(hits)}"]}
    with tempfile.TemporaryDirectory(prefix="study-agent-capr-") as directory:
        root = Path(directory)
        script = root / "cohort.R"
        output = root / "cohort.json"
        script.write_text(capr_code, encoding="utf-8")
        runner = (
            "args<-commandArgs(TRUE); suppressPackageStartupMessages(library(Capr)); "
            "source(args[1], local=new.env(parent=globalenv())); "
            "if(!file.exists(args[2])) stop('cohort_json_not_written'); "
            "j<-paste(readLines(args[2],warn=FALSE),collapse='\\n'); "
            "e<-CirceR::cohortExpressionFromJson(j); "
            "s<-CirceR::buildCohortQuery(e,CirceR::createGenerateOptions(generateStats=FALSE)); "
            "if(!is.character(s)||!nchar(s)) stop('circe_sql_empty')"
        )
        env = {"PATH": os.environ.get("PATH", ""), "R_PROFILE_USER": "/dev/null", "R_ENVIRON_USER": "/dev/null", "R_LIBS_USER": _R_LIBS}
        try:
            result = subprocess.run(["Rscript", "--vanilla", "-e", runner, str(script), str(output)], cwd=root, env=env, text=True, capture_output=True, timeout=max(1, min(timeout_seconds, 120)), check=False)
        except subprocess.TimeoutExpired:
            return {"status": "failed", "messages": ["r_validation_timeout"]}
        if result.returncode:
            return {"status": "failed", "messages": ["r_validation_failed"], "stderr": result.stderr[-4000:]}
        circe = json.loads(output.read_text(encoding="utf-8"))
        if not isinstance(circe.get("PrimaryCriteria"), dict) or not isinstance(circe.get("ConceptSets"), list):
            return {"status": "failed", "messages": ["circe_required_fields_missing"]}
        return {"status": "passed", "messages": [], "circe_json": circe}


def register(mcp: object) -> None:
    @mcp.tool(name="phenotype_make_computable_validate")
    def phenotype_make_computable_validate_tool(capr_code: str, timeout_seconds: int = 60) -> Dict[str, Any]:
        return with_meta(validate_capr_source(capr_code, timeout_seconds), "phenotype_make_computable_validate")
