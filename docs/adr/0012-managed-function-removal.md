# 0012: Function removal is a managed code edit

Status: Accepted
Date: 2026-10-05

## Context

Users can add and redefine accepted application functions through chat, but the reference adapter previously treated an unbound accepted function as an unrecorded mutation. Removal must cover the binding, source catalogue, checkpoints, and durable recovery together.

## Decision

Treat direct literal local FMAKUNBOUND forms, optionally grouped with other edits in PROGN, as managed development changes. Retain callers unless the user requests related edits. Use the existing worker transaction, safety checks, change detection, and surviving-definition export. An optional caller-owned pre-evaluation validation hook lets adapters reject edits outside their coverage before execution; the reference adapter uses it to restrict supported removal syntax and targets.

## Rationale

Reusing Lisp forms avoids another deletion command or worker action. Recording the final declared edit for each function supports atomic deletion and caller repairs without reading an intermediate function binding after evaluation has finished. Automatic cascade removal can destroy desired functionality, and a static dependency graph cannot exhaustively capture computed Lisp calls. Caller-owned safety checks provide the acceptance contract; source inspection supplies advisory information.

## Consequences

Accepted removal creates a revision; repeated removal of an absent local function is a no-op. Preview, aborted attempts, and rejected safety checks restore bindings and metadata. Recovery loads surviving definitions; rollback can restore removed functions without changing the artifact format. Callers may later signal UNDEFINED-FUNCTION and enter the existing repair workflow. Active frames and cached function objects retain their bodies. The reference adapter rejects indirect FMAKUNBOUND references conservatively; arbitrary computed effects remain outside cooperative syntax protection. Custom adapters own validation and rollback coverage, including initialization outside worker execution.

Related: [attempt rollback](0002-managed-attempt-rollback.md), [change-sensitive revisions](0009-change-sensitive-revisions.md), [development and execution](0010-development-and-execution.md).

Implementation: [reference adapter](../../src/reference-world.lisp), [worker](../../src/kernel.lisp), [model instructions](../../src/chat.lisp). Verification: [removal scenarios, generated histories, and live deletion](../../tests/composition-suite.lisp).
