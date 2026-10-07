#!/usr/bin/env bash
# Exercise the shipped LFE examples with the actual CLI, then reopen each store.
set -euo pipefail
JITI_EXAMPLE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$JITI_EXAMPLE_ROOT"
JITI_EXAMPLE_TMP="$(mktemp -d "${TMPDIR:-/tmp}/jiti-examples.XXXXXX")"
trap 'rm -rf "$JITI_EXAMPLE_TMP"' EXIT
JITI_EXAMPLE_PYTHON="${JITI_EXAMPLE_PYTHON:-python3}"

run_action() {
  local example_id="$1" example_source="$2"
  if ! "$JITI_EXAMPLE_PYTHON" scripts/repl.py --store "$JITI_EXAMPLE_TMP/$example_id" \
      --timeout-ms 5000 --eval "$example_source" --json > "$JITI_EXAMPLE_TMP/last.jsonl"; then
    cat "$JITI_EXAMPLE_TMP/last.jsonl"
    return 1
  fi
}

run_action invoice "$(cat examples/invoice-audit.lfe)"
run_action invoice "(case (andalso (=:= (map-get (state-get 'invoice-report) #B(\"total_cents\")) 32400) (=:= (invoice-audit ()) (map #B(\"accepted_lines\") 0 #B(\"total_cents\") 0 #B(\"duplicates\") () #B(\"invalid\") ()))) ('true 'recovered) (_ (error 'invoice_recovery_failed)))"
printf '%s\n' 'PASS invoice audit: 32400 cents, 3 accepted lines, 1 duplicate, 1 invalid; recovered.'

run_action release "$(cat examples/release-gate.lfe)"
run_action release "(case (andalso (=:= (state-get 'release-report) (map 'decision 'ready 'fixture_p95_ms 100 'verified_tasks 3)) (lists:all (lambda (node) (=:= (map-get node 'status) 'done)) (maps:values (map-get (jiti_plan:inspect #B(\"release\")) 'nodes))) (=:= (jiti_processes:all) ())) ('true 'recovered_without_replay) (_ (error 'release_recovery_failed)))"
printf '%s\n' 'PASS release gate: 3 verified tasks, fixture p95 100 ms; dependent admission and no-replay recovery.'

run_action reservation "$(cat examples/reservation-repair.lfe)"
"$JITI_EXAMPLE_PYTHON" scripts/repl.py --store "$JITI_EXAMPLE_TMP/reservation" --plain --json \
    > "$JITI_EXAMPLE_TMP/repair.jsonl" <<'LFE'
(reserve-items 4)
/status
/repair (defun reservation-price (quantity) (* quantity 1500))
/retry
/preview (reserve-items 2)
/status
/quit
LFE
run_action reservation "(case (andalso (=:= (state-get 'stock) 16) (=:= (state-get 'reservation-cents) 6000) (=:= (reservation-price 2) 3000)) ('true 'recovered) (_ (error 'reservation_recovery_failed)))"
printf '%s\n' 'PASS reservation repair: failed attempt discarded, retry reserves once, preview discarded; recovered.'

run_action dispatch "$(cat examples/dynamic-dispatch.lfe)"
run_action dispatch "(case (=:= (invoke (state-get 'pricing-pipeline) '(3)) 325) ('true 'recovered) (_ (error 'dispatch_recovery_failed)))"
printf '%s\n' 'PASS dynamic dispatch: heterogeneous pricing, composition and fold total 925 cents; recovered.'
