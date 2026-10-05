# 0009: Change-sensitive application revisions

Status: Accepted
Date: 2026-10-05

## Context

Calling existing functionality should return a result without manufacturing another application version. Accepted executions may also change application data and need durable recovery.

## Decision

Separate attempted operations from immutable application revisions. Compare deterministic caller-owned managed-state projections before and after a transaction; publish only when accepted managed code or data changes. Record attempts and outcomes in the diagnostic journal. Initial publication and explicit rollback still create revisions.

## Rationale

Publishing every evaluation makes history reflect interaction frequency rather than application changes. Restricting execution to pure functions excludes normal application behavior. Comparing snapshots is unsuitable because checkpoints contain live function objects. A readable managed-state projection makes change detection domain-owned while reusing durable export/import.

## Consequences

World adapters supply managed-state and catalogue callbacks. Comparison uses EQUALP over the character codes of a deterministic readable representation, preserving string case and numeric representation that EQUALP on raw values would erase. Projections must be acyclic readable trees and cover the adapter's managed resources. Operations are diagnostic and are never automatically replayed. No-op development and pure execution preserve CURRENT. A final-state no-op can have transient effects recorded in its operation. Existing immutable publication and uncertain-publication behavior remain in force.

Related: [durability](0003-durable-managed-revisions.md), [rollback](0007-history-preserving-rollback.md).

Implementation: [worker](../../src/kernel.lisp), [store](../../src/store.lisp). Verification: [composition transactions](../../tests/composition-suite.lisp).
