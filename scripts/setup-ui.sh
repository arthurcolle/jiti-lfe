#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if command -v uv >/dev/null 2>&1; then
  test -x .jiti/ui-venv/bin/python || uv venv .jiti/ui-venv
  uv pip install --python .jiti/ui-venv/bin/python -r requirements-ui.txt
else
  test -x .jiti/ui-venv/bin/python || python3 -m venv .jiti/ui-venv
  .jiti/ui-venv/bin/python -m pip install -r requirements-ui.txt
fi
