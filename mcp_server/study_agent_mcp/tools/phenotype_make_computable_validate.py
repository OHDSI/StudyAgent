from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from threading import Lock
from typing import Any, Dict

from study_agent_core.config import ConfigError, load_config

from ._common import with_meta
from .phenotype_make_computable_emit import ENTRY_POINT

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FORBIDDEN_IDENTIFIERS = ("assign", "assigninnamespace", "attach", "connection", "download", "download.file", "dyn.load", "eval", "file", "get", "getnamespace", "library.dynam", "load", "loadnamespace", "parse", "pipe", "readlines", "readrds", "readurl", "save", "serialize", "setwd", "shell", "socket", "source", "system", "system2", "unlink", "url", "write", "writelines")
_FORBIDDEN_NAMESPACE_PREFIXES = ("base::", "utils::", "methods::", "parallel::", "tools::", "httr::", "curl::")
# Capr/Circe validation shells out to R and writes temporary compilation artifacts.
# One lane per MCP process avoids resource contention under threaded transports.
_R_VALIDATION_LOCK = Lock()


def _configured_mcp_r_value(name: str) -> str | None:
    """Read an MCP R runtime value from validated config for direct tool use."""
    try:
        config = load_config()
    except ConfigError:
        return None
    if config is None:
        return None
    value = getattr(config.mcp.r, name)
    return str(value).strip() if value is not None else None


def _r_library_path() -> str | None:
    """Resolve the R library from environment, config, then local renv."""
    configured = os.getenv("R_LIBS_USER", "").strip()
    if configured:
        return configured
    configured = _configured_mcp_r_value("library")
    if configured:
        return configured
    library_root = _REPO_ROOT / "renv" / "library"
    candidates = sorted(
        path for path in library_root.glob("*/*/*") if path.is_dir()
    )
    return str(candidates[0]) if candidates else None


def _r_script_path() -> str:
    """Resolve Rscript from environment, then validated MCP config."""
    configured = os.getenv("R_SCRIPT", "").strip()
    if configured:
        return configured
    return _configured_mcp_r_value("rscript") or "Rscript"


def _unsafe_r_constructs(capr_code: str) -> list[str]:
    import re
    normalized = capr_code.lower().replace("`", "")
    normalized = re.sub(r'(["\'])(?:\\.|(?!\1).)*\1', '""', normalized, flags=re.DOTALL)
    normalized = re.sub(r"(?m)#.*$", "", normalized)
    hits = [name for name in _FORBIDDEN_IDENTIFIERS if re.search(rf"(?<![a-z0-9_.]){re.escape(name)}(?![a-z0-9_.])", normalized)]
    hits.extend(prefix for prefix in _FORBIDDEN_NAMESPACE_PREFIXES if prefix in normalized)
    return sorted(set(hits))



def _read_r_environment(path: Path) -> Dict[str, Any]:
    """Read runtime provenance emitted by the same R process that validated Capr."""
    result: Dict[str, Any] = {"validation_packages": {}, "loaded_namespaces": {}}
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) < 2:
            continue
        if fields[0] in {"r_version", "platform"}:
            result[fields[0]] = fields[1]
        elif len(fields) == 3 and fields[0] == "validation_package":
            result["validation_packages"][fields[1]] = fields[2]
        elif len(fields) == 3 and fields[0] == "loaded_namespace":
            result["loaded_namespaces"][fields[1]] = fields[2]
    if not result.get("r_version") or not result.get("platform"):
        raise ValueError("r_environment_metadata_incomplete")
    return result


def validate_capr_source(capr_code: str, timeout_seconds: int = 60) -> Dict[str, Any]:
    """Validate pure function-form Capr source and compile its Circe JSON."""
    if not capr_code.strip():
        return {"status": "failed", "messages": ["empty_capr_code"]}
    hits = _unsafe_r_constructs(capr_code)
    if hits:
        return {"status": "failed", "messages": [f"forbidden_r_constructs:{','.join(hits)}"]}
    r_library = _r_library_path()
    if not r_library:
        return {"status": "failed", "messages": ["r_library_not_found"]}
    with _R_VALIDATION_LOCK:
        return _validate_capr_source_serialized(capr_code, timeout_seconds, r_library)


def _validate_capr_source_serialized(capr_code: str, timeout_seconds: int, r_library: str) -> Dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="study-agent-capr-") as directory:
        root = Path(directory)
        script, output, environment_output = root / "phenotype_definition.R", root / "cohort.json", root / "r_environment.tsv"
        script.write_text(capr_code, encoding="utf-8")
        runner = (
            "args<-commandArgs(TRUE); e<-new.env(parent=baseenv()); sys.source(args[1],envir=e); "
            f"if(!exists('{ENTRY_POINT}',envir=e,inherits=FALSE)) stop('capr_entry_point_missing'); "
            f"d<-e[['{ENTRY_POINT}']](); if(!methods::is(d,'Cohort')) stop('capr_entry_point_did_not_return_cohort'); "
            "Capr::writeCohort(d,args[2]); if(!file.exists(args[2])) stop('cohort_json_not_written'); "
            "j<-paste(readLines(args[2],warn=FALSE),collapse='\\n'); e2<-CirceR::cohortExpressionFromJson(j); "
            "s<-CirceR::buildCohortQuery(e2,CirceR::createGenerateOptions(generateStats=FALSE)); if(!is.character(s)||!nchar(s)) stop('circe_sql_empty'); "
            "pv<-function(p) if(requireNamespace(p,quietly=TRUE)) as.character(utils::packageVersion(p)) else 'not_installed'; direct<-c('Capr','CirceR','SqlRender'); loaded<-sort(loadedNamespaces()); lines<-c(paste('r_version',R.version.string,sep='\t'),paste('platform',R.version$platform,sep='\t'),vapply(direct,function(p) paste('validation_package',p,pv(p),sep='\t'),''),vapply(loaded,function(p) paste('loaded_namespace',p,pv(p),sep='\t'),'')); writeLines(lines,args[3])"
        )
        env = {"PATH": os.environ.get("PATH", ""), "R_PROFILE_USER": "/dev/null", "R_ENVIRON_USER": "/dev/null", "R_LIBS_USER": r_library}
        try:
            result = subprocess.run([_r_script_path(), "--vanilla", "-e", runner, str(script), str(output), str(environment_output)], cwd=root, env=env, text=True, capture_output=True, timeout=max(1, min(timeout_seconds, 120)), check=False)
        except subprocess.TimeoutExpired:
            return {"status": "failed", "messages": ["r_validation_timeout"]}
        if result.returncode:
            return {"status": "failed", "messages": ["r_validation_failed"], "stderr": result.stderr[-4000:]}
        circe = json.loads(output.read_text(encoding="utf-8"))
        if not isinstance(circe.get("PrimaryCriteria"), dict) or not isinstance(circe.get("ConceptSets"), list):
            return {"status": "failed", "messages": ["circe_required_fields_missing"]}
        try:
            r_environment = _read_r_environment(environment_output)
        except (OSError, ValueError) as exc:
            r_environment = {"status": "unavailable", "error": str(exc)}
        return {"status": "passed", "messages": [], "circe_json": circe, "r_environment": r_environment}


def register(mcp: object) -> None:
    @mcp.tool(name="phenotype_make_computable_validate")
    def phenotype_make_computable_validate_tool(capr_code: str, timeout_seconds: int = 60) -> Dict[str, Any]:
        return with_meta(validate_capr_source(capr_code, timeout_seconds), "phenotype_make_computable_validate")
