#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export FLASK_ENV=production
export ACP_PORT=${ACP_PORT:-7777}
python3 -m pip install --quiet flask requests
python3 acp/server.py
