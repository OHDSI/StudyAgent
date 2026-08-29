"""Optional compatibility diagnostics for externally owned R client packages."""

from __future__ import annotations

import os
import subprocess
from threading import Lock
from typing import Any, Dict

from ._common import with_meta
from .phenotype_make_computable_validate import _r_library_path, _r_script_path

_R_CLIENT_LOCK = Lock()
_REQUIRED_PACKAGES = {
    "slashOhdsiAcpClient": {
        "minimum_version": "0.1.0",
        "functions": {
            "acp_connect": ("url",),
            "acp_check_health": ("client",),
            "acp_check_compatibility": ("client",),
        },
    },
    "slashOhdsiStrategusAssistant": {
        "minimum_version": "0.1.0",
        "functions": {
            "checkStrategusRuntime": ("strict",),
            "runStrategusIncidenceShell": ("outputDir", "acpUrl", "checkRuntime"),
            "runStrategusCohortMethodsShell": ("outputDir", "acpUrl", "checkRuntime"),
        },
    },
}


def _parse_rows(stdout: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "r_environment": {},
        "packages": {},
        "public_contract": {},
        "strategus_runtime": {"dependencies": {}},
    }
    for line in stdout.splitlines():
        fields = line.split("|")
        if len(fields) < 3:
            continue
        kind, name, *values = fields
        if kind == "environment":
            result["r_environment"][name] = values[0]
        elif kind == "package":
            installed, minimum, compatible = values
            result["packages"][name] = {
                "installed_version": installed or None,
                "minimum_version": minimum,
                "compatible": compatible == "true",
            }
        elif kind == "function":
            exported, required, actual, compatible = values
            result["public_contract"][name] = {
                "exported": exported == "true",
                "required_formals": required.split(",") if required else [],
                "actual_formals": actual.split(",") if actual else [],
                "compatible": compatible == "true",
            }
        elif kind == "strategus":
            result["strategus_runtime"][name] = values[0]
        elif kind == "strategus_dependency":
            expected, installed, matches = values
            result["strategus_runtime"]["dependencies"][name] = {
                "expected": expected,
                "installed": installed or None,
                "matches": matches == "true",
            }
    return result


def check_r_client_compatibility(timeout_seconds: int = 30) -> Dict[str, Any]:
    """Check installed public contracts in the R library used by ACP/MCP validation."""
    r_library = _r_library_path()
    if not r_library:
        return {"status": "unavailable", "messages": ["r_library_not_found"]}
    package_contract = ";".join(
        f"{package}|{spec['minimum_version']}|"
        + "~".join(
            f"{function}:{','.join(formals)}"
            for function, formals in spec["functions"].items()
        )
        for package, spec in _REQUIRED_PACKAGES.items()
    )
    runner = r'''args <- commandArgs(TRUE)
contract <- strsplit(args[[1]], ";", fixed = TRUE)[[1]]
emit <- function(...) cat(paste(..., sep = "|", collapse = "|"), "\n", sep = "")
for (entry in contract) {
  parts <- strsplit(entry, "|", fixed = TRUE)[[1]]
  package <- parts[[1]]; minimum <- parts[[2]]; functions <- strsplit(parts[[3]], "~", fixed = TRUE)[[1]]
  installed <- if (requireNamespace(package, quietly = TRUE)) as.character(utils::packageVersion(package)) else ""
  compatible <- nzchar(installed) && utils::compareVersion(installed, minimum) >= 0
  emit("package", package, installed, minimum, tolower(as.character(compatible)))
  exports <- if (nzchar(installed)) getNamespaceExports(package) else character()
  for (function_spec in functions) {
    pair <- strsplit(function_spec, ":", fixed = TRUE)[[1]]
    function_name <- pair[[1]]; required <- if (length(pair) > 1) strsplit(pair[[2]], ",", fixed = TRUE)[[1]] else character()
    exported <- function_name %in% exports
    actual <- if (exported) names(formals(getExportedValue(package, function_name))) else character()
    function_compatible <- exported && all(required %in% actual)
    emit("function", paste(package, function_name, sep = "::"), tolower(as.character(exported)), paste(required, collapse = ","), paste(actual, collapse = ","), tolower(as.character(function_compatible)))
  }
}
emit("environment", "r_version", R.version.string)
emit("environment", "platform", R.version$platform)
runtime <- tryCatch(slashOhdsiStrategusAssistant::checkStrategusRuntime(strict = FALSE), error = function(error) error)
if (inherits(runtime, "error")) {
  emit("strategus", "status", "failed")
  emit("strategus", "error", conditionMessage(runtime))
} else {
  emit("strategus", "status", "passed")
  emit("strategus", "profile", runtime$profile %||% "")
  emit("strategus", "r_version_matches", tolower(as.character(isTRUE(runtime$r_version_matches))))
  for (dependency in runtime$packages) emit("strategus_dependency", dependency$package, dependency$expected, dependency$installed %||% "", tolower(as.character(isTRUE(dependency$matches))))
}'''
    # `%||%` is local to this self-contained script and avoids loading either package.
    runner = "`%||%` <- function(x, y) if (is.null(x)) y else x\n" + runner
    env = {
        "PATH": os.environ.get("PATH", ""),
        "R_PROFILE_USER": "/dev/null",
        "R_ENVIRON_USER": "/dev/null",
        "R_LIBS_USER": r_library,
    }
    with _R_CLIENT_LOCK:
        try:
            process = subprocess.run(
                [_r_script_path(), "--vanilla", "-e", runner, package_contract],
                env=env,
                text=True,
                capture_output=True,
                timeout=max(1, min(timeout_seconds, 120)),
                check=False,
            )
        except subprocess.TimeoutExpired:
            return {"status": "unavailable", "messages": ["r_client_compatibility_timeout"]}
    if process.returncode:
        return {
            "status": "unavailable",
            "messages": ["r_client_compatibility_failed"],
            "stderr": process.stderr[-4000:],
        }
    result = _parse_rows(process.stdout)
    result["r_library"] = r_library
    package_ok = all(item["compatible"] for item in result["packages"].values())
    contract_ok = all(item["compatible"] for item in result["public_contract"].values())
    strategus_ok = result["strategus_runtime"].get("status") == "passed" and result["strategus_runtime"].get("r_version_matches") == "true" and all(
        item["matches"] for item in result["strategus_runtime"]["dependencies"].values()
    )
    result["status"] = "passed" if package_ok and contract_ok and strategus_ok else "failed"
    result["messages"] = [] if result["status"] == "passed" else ["r_client_compatibility_contract_not_met"]
    return result


def register(mcp: object) -> None:
    @mcp.tool(name="r_client_compatibility")
    def r_client_compatibility_tool(timeout_seconds: int = 30) -> Dict[str, Any]:
        return with_meta(check_r_client_compatibility(timeout_seconds), "r_client_compatibility")
