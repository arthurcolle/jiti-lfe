# 0023: Expose declarative planning through native chat tools

Status: Accepted
Date: 2026-10-06

## Context

LFE chat could inspect a plan, but construction and lifecycle actions required
generated source. Harder live use exposed unnecessary inspection, malformed input,
and repeated source generation around capabilities the kernel already implements.

## Decision

Expose typed declarative plan construction, edits, launch, reconciliation,
verification and admission controls. Translate actions into existing managed
planner operations; do not create another plan owner or evaluator. Check expected
versions before mutation and again inside the managed operation. Supply structured
inspection after successful changes and read-only paginated plan discovery.
Wait for existing jobs with bounded frontend polling of explicit reconciliation,
rather than sleeping inside a deadline-bound managed evaluation.

## Rationale

Leaving all planning to generic source tools increases syntax and version mistakes
and hides job relationships in printed terms. A separate Python scheduler would
duplicate admission, ownership and recovery rules. Thin adapters reuse those rules
while making whole-plan construction one atomic managed action. Numeric UTF-8
binary literals keep user IDs and source text from interpolating into generated forms.
The first live workflow's wait-only evaluations timed out; a dedicated wait tool
keeps that delay outside the evaluator without introducing automatic scheduling.

## Consequences

One construction call admits at most 32 nodes and 64,000 combined source/check
bytes; incremental additions remain subject to the kernel's 128-node limit.
Forward references are supported by installing containment before precedence.
Tasks require a stored check, but presence alone does not establish the check's
independence or usefulness. Verification uses that check and rejects mutations.
Topology freezes after start. Failed kernel edits retain the existing explicit
pause/abort protocol. External launches and cancellation remain outside managed
rollback; recovery does not dispatch work. Remote reconciliation remains explicit
adoption under the existing owner/generation rules. Generic operator source remains
cooperative rather than sandboxed. Model output is caller-configurable, defaulting
to 8192 tokens per request; this does not grant additional execution authority.

Implementation: [typed adapters](../../scripts/lfe_plan_tools.py),
[chat schemas and controls](../../scripts/lfe_repl.py),
[structured inspections](../../src/jiti_bridge.lfe).
Verification: [actual native-tool scenarios](../../tests/lfe_native_plans.py),
[explicit bounded live workflow](../../tests/lfe_native_plans_live.py),
[retained live verification](../verification/lfe-native-plans-verification-2026-10-06.md).
Related: [plan admission](0020-lfe-plan-admission-and-verification.md),
[owned processes](0021-lfe-owned-process-leases.md),
[managed snapshots](0016-lfe-managed-snapshots.md).
