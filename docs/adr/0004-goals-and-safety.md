# 0004: Separate goals from safety

Status: Accepted
Date: 2026-10-04

## Context

Incremental development needs accepted intermediate revisions even when the application does not yet satisfy its task.

## Decision

Use goals for completion and invariants for candidate safety. Only evaluate acceptance at safe points. Property checks retain this classification and return counterexamples as feedback.

## Rationale

Treating every failed application test as a safety violation would prevent useful intermediate edits. Conversely, goal failures cannot justify publishing an unsafe candidate.

## Consequences

All goals must pass for success. Failed or signaled safety checks reject a candidate; signaled goals never imply completion. A nonempty goal contract is required for autonomous completion; interactive development may omit goals.

Implementation: [src/properties.lisp](../../src/properties.lisp). Verification: [kernel suite](../../tests/suite.lisp).
