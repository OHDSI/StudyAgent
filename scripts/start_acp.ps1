# NOTE: Run the script that adds Use-AirgapPythonEnv to the powershell environment:
#  D:\conda_envs\airgap-python.ps1

#requires -version 5.1
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# cd "$(dirname "$0")/.."
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Resolve-Path (Join-Path $ScriptDir "..")
Set-Location $RepoRoot

# export FLASK_ENV=production
$env:FLASK_ENV = "production"

# export ACP_PORT=${ACP_PORT:-7777}
if ([string]::IsNullOrWhiteSpace($env:ACP_PORT)) {$env:ACP_PORT = "7777"}

#python3 acp/server.py
# (assumes pything is available on PATH as a side-effect of Use-AirgapPythonEnv (see note above)
# Note change to a path above scripts\ was above
python .\acp\server.py
