# 0015: Isolated experimental LFE evaluation

Status: Accepted
Date: 2026-10-05

## Context

An unfinished local conversion selected LFE by default while its kernel merely
recorded source strings. LFE evaluates Erlang semantics; an exception unwinds
the computation and cannot preserve the live SBCL restart objects required by
[0001](0001-worker-owned-live-repair.md).

## Decision

Expose LFE as an explicitly selected experimental backend (`--lfe`, `make repl`)
with a controller-owned snapshot and a bounded monitored evaluator per action.
Retain the SBCL backend and its existing worker/restart contract as the default.
LFE repair retains an explicit failed action and provisional snapshot; retry
evaluates the whole action anew. It never claims continuation of an active stack.

## Rationale

A mechanical translation would silently change the meaning of live repair.
Deleting the LFE experiment would lose useful evaluation and process-isolation
work. An explicit backend makes its different semantics reviewable without
superseding the accepted SBCL decision. Interpreted named functions support
composition and recursive calls without introducing compiled-module upgrade
semantics.

## Consequences

The controller alone publishes managed state and code. Failed evaluation
discards provisional effects; repairs remain provisional until retry succeeds.
Abort and failed repairs discard the entire provisional attempt. Tokens reject
stale repair/retry/abort requests. Preview discards successful managed changes.
Caller-supplied safety expressions reject candidates; unmet goals permit safe
intermediate progress, following [0004](0004-goals-and-safety.md).

Snapshots cover managed immutable data and top-level named definitions only.
External I/O, spawned processes, ETS and arbitrary Erlang effects are unmanaged.
The evaluator deadline bounds cooperative evaluation; it is not a security
sandbox or OTP supervision application. Application adapters, live restarts,
autonomous evolution and legacy CLI parity remain specific to SBCL. LFE chat
transport exists but real-provider parity has not been established here.

Implementation: [kernel](../../src/jiti_kernel.lfe),
[controller](../../src/jiti_bridge.lfe), [launcher](../../scripts/repl.py).
Verification: [BEAM scenarios and generated traces](../../tests/lfe_scenarios.py).
Related: [LFE persistence](0016-lfe-managed-snapshots.md).
