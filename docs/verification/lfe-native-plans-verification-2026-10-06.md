# Native LFE chat planning verification — October 6, 2026

## Implemented capabilities

The ordinary `--lfe --mode chat` interface now exposes nine native plan tools:
listing, atomic construction, incremental additions, dependencies, explicit
launch, reconciliation, bounded waiting, verification, and admission/cancellation
controls. They adapt existing managed planner operations rather than owning a
second scheduler. Construction supports forward references and supplies inspected
versions and public receipts after successful changes. `/plans` discovers durable
plans after reopening. Model output defaults to 8192 tokens per request and is
configurable up to 32768 with `--max-output-tokens`.

Implementation: [adapters](../../scripts/lfe_plan_tools.py),
[chat interface](../../scripts/lfe_repl.py),
[structured controller inspection](../../src/jiti_bridge.lfe).
[ADR 0023](../adr/0023-native-lfe-planning-tools.md) records the decision; prior
ownership, verification and rollback decisions remain in force.

## Actual model workflows

Both fresh runs used `gpt-6.1-sol`, with at most 18 model tool calls and 20 Responses
requests each. The fixed owner contract specified the exact sources, checks,
dependencies and result values. Two independent workers computed a fixture
subtotal of 100 and a negative-record count of 2. Only after both checks passed
could a dependent join execute and return `#(validated 100 2)`.

| Run | Model requests | Model tool calls | Actual worker overlap | Paused evaluations |
| --- | ---: | ---: | ---: | ---: |
| Initial adapter smoke | 18 | 17 | 22,999 ms | 2 |
| Final smoke with bounded wait | 11 | 10 | 21,963 ms | 0 |

In the initial smoke, chat attempted two wait-only owner evaluations that exceeded
the evaluation deadline; both were explicitly aborted. It completed the workflow.
That observation motivated `plan_wait`, which waits outside the evaluator while
explicitly reconciling existing jobs. It neither launches nor verifies work.

The final smoke used `plan_wait` twice, verified all three exact checks, and
independently confirmed that the supplied sources/checks were preserved and exactly
three local jobs existed. Fresh-process recovery retained all three done nodes and
started no replacement jobs. Both runs ended at plan version 14 and revision 10.
These are two execution smokes, not a statistically controlled performance study or
evidence that the full Agent Farm population feedback loop exists. Token usage is
retained in the reports; monetary charges are unknown.

Retained reports:
[initial run](../../.jiti/native-plans-live-20261006-1/report.json),
[final run](../../.jiti/native-plans-live-20261006-2/report.json).
Explicit runner: [live smoke](../../tests/lfe_native_plans_live.py).

## Offline and required checks

`make test` passed the actual BEAM scenarios, 180 generated state-machine actions,
catalogue/diagnostic tests, native plan tests, six call-limit regressions,
local/distributed ownership and recovery tests, farm rollouts and ADR validation.
The native-tool suite checks atomic construction failure, escaped identifiers,
stale versions, ancestor gates, real jobs, premature/false/mutating verification,
topology freeze, cancellation, wait deadlines, pagination and recovery.

The call-limit regression had retained an expectation of 12 despite the existing
CLI default of 0; that expectation was corrected without changing the default.
The distributed suite initially could not start its loopback Erlang node inside
the sandbox; the complete suite passed with loopback access.

`python3 scripts/check-adrs.py` passed all 23 records. `git diff --check` passed.
The required `devenv shell test` and `devenv shell test-live` commands were attempted
but could not run because `devenv` is not installed. The LFE tests and real Responses
smokes above are separate verification; the original SBCL gates remain unrun.
