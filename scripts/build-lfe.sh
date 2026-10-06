#!/usr/bin/env bash
# Build the pinned local LFE toolchain and the Jiti LFE modules.
set -euo pipefail

ROOT=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
LFE_ROOT=${LFE_ROOT:-"$ROOT/_build/deps/lfe"}
LFE_VERSION=2.2.2
LFE_COMMIT=dae7489ebf9588e5f746a34cd4f8ff83d1469eef
EBIN="$ROOT/_build/ebin"
LFE_EBIN="$LFE_ROOT/ebin"
rm -f "$EBIN/.build-ok"

fail() { printf 'build-lfe: %s\n' "$*" >&2; exit 1; }
command -v erl >/dev/null 2>&1 || fail 'erl is required (activate devenv or install Erlang/OTP)'
command -v erlc >/dev/null 2>&1 || fail 'erlc is required (activate devenv or install Erlang/OTP)'
if [ ! -d "$LFE_ROOT" ]; then
  command -v git >/dev/null 2>&1 || fail 'git is required to fetch LFE'
  mkdir -p "$(dirname "$LFE_ROOT")"
  git clone --depth 1 --branch "v$LFE_VERSION" https://github.com/lfe/lfe.git "$LFE_ROOT"
fi
[ "$(git -C "$LFE_ROOT" rev-parse HEAD)" = "$LFE_COMMIT" ] || fail 'LFE checkout does not match the pinned commit'
[ -z "$(git -C "$LFE_ROOT" status --porcelain --untracked-files=no)" ] || fail 'LFE checkout has modified tracked source'
[ -x "$LFE_ROOT/bin/lfec" ] || fail "LFE compiler missing: $LFE_ROOT/bin/lfec"

actual_version=$(erl -noshell -eval \
  "{ok,[{application,lfe,Props}]}=file:consult(\"$LFE_ROOT/src/lfe.app.src\"), io:format(\"~s\", [proplists:get_value(vsn, Props)]), halt()." \
  2>/dev/null) || fail 'unable to inspect the LFE application version'
[ "$actual_version" = "$LFE_VERSION" ] || fail "expected LFE $LFE_VERSION, found $actual_version"

# LFE itself is a source dependency, not a checked-in build artifact. Make is
# incremental and is safe to run for every project build. LFE's compiler
# wrappers invoke `lfescript` through /usr/bin/env, so expose the pinned bin
# directory explicitly rather than relying on a globally installed LFE.
export PATH="$LFE_ROOT/bin:$PATH"
make -C "$LFE_ROOT" compile >/dev/null
[ -f "$LFE_EBIN/lfe.beam" ] || fail "LFE compiler did not produce $LFE_EBIN/lfe.beam"

mkdir -p "$EBIN"
sources=("$ROOT"/src/*.lfe)
[ "${#sources[@]}" -gt 0 ] || fail "no LFE sources found under $ROOT/src"

# Compile all project modules with the pinned compiler. The LFE ebin is placed
# first so macro expansion and include resolution cannot use another LFE.
export ERL_LIBS="$LFE_ROOT${ERL_LIBS:+:$ERL_LIBS}"
"$LFE_ROOT/bin/lfec" -pa "$LFE_EBIN" -o "$EBIN" "${sources[@]}"

for required in jiti_bridge jiti_kernel jiti_toolkit jiti_store jiti_operations jiti_catalogue jiti_workspace jiti_runtime jiti_processes jiti_plan; do
  [ -f "$EBIN/$required.beam" ] || fail "required kernel module missing: $EBIN/$required.beam"
done
touch "$EBIN/.build-ok"

printf 'LFE %s -> %s (%d modules)\n' "$actual_version" "$EBIN" "${#sources[@]}"
