# 0002: Managed attempt rollback

Status: Accepted
Date: 2026-10-04

## Context

A repair can change functions and data while the original failed computation still holds references into the world.

## Decision

Place the outer evaluation and its provisional repairs in one caller-owned checkpoint. Unwind the outer attempt before restoring; a failed repair aborts the whole attempt.

## Rationale

Per-repair rollback through rebinding roots could leave live frames referencing mutated objects. Keeping repairs independently committed would conflict with parent rollback. Grouping them defines one coherent acceptance boundary.

## Consequences

The caller must cover every allowed mutation. The reference adapter supports one readable data table and direct named DEFUNs, not arbitrary classes, methods, files, or external effects. Restore failures fault the session.

Implementation: [src/reference-world.lisp](../../src/reference-world.lisp). Verification: [kernel suite](../../tests/suite.lisp).
