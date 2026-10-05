#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
mode=${1:-test}
default_timeout=180
shift || true
if [[ "$mode" == live ]]; then
  default_timeout=600
  # Underclass development profile; user-supplied environment always wins.
  if [[ -f "$HOME/.codex/config.toml" ]]; then
    export OPENAI_MODEL="${OPENAI_MODEL:-$(python3 -c 'import tomllib,pathlib; print(tomllib.loads((pathlib.Path.home()/".codex/config.toml").read_text()).get("model", ""))')}"
    export OPENAI_BASE_URL="${OPENAI_BASE_URL:-$(python3 -c 'import tomllib,pathlib; c=tomllib.loads((pathlib.Path.home()/".codex/config.toml").read_text()); print(c.get("model_providers",{}).get(c.get("model_provider"),{}).get("base_url","https://api.openai.com/v1"))')}"
    if [[ -z "${OPENAI_API_KEY:-}" && -z "${OPENAI_API_KEY_FILE:-}" && -f "$HOME/.codex/underclass-overalls.key" ]]; then
      export OPENAI_API_KEY_FILE="$HOME/.codex/underclass-overalls.key"
    fi
  fi
  if [[ -z "${OPENAI_MODEL:-}" || ( -z "${OPENAI_API_KEY:-}" && -z "${OPENAI_API_KEY_FILE:-}" ) ]]; then
    echo 'Configure OPENAI_MODEL plus OPENAI_API_KEY or OPENAI_API_KEY_FILE; optionally OPENAI_BASE_URL.' >&2
    exit 2
  fi
fi
exec timeout "${TEST_TIMEOUT:-$default_timeout}" sbcl --noinform --script scripts/test.lisp "$mode" "$@"
