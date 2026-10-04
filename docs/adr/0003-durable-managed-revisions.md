# 0003: Durable managed revisions

Status: Accepted
Date: 2026-10-04

## Context

Accepted development must survive process restarts without pretending arbitrary effects or live stacks can be serialized.

## Decision

Export managed code and data to immutable revisions and atomically publish a flushed CURRENT pointer. Fresh-process recovery loads CURRENT and never automatically replays unfinished forms.

## Rationale

A write-ahead action log cannot make arbitrary Lisp effects transactional. Whole-image cores introduce resource and quiescence requirements. Managed export/import keeps persistence explicit and domain-owned.

## Consequences

The current pointer is authoritative; manifest events provide accepted history. An append-only diagnostic journal retains attempted actions and conditions. A torn final journal record is ignored and archived during recovery; it cannot override CURRENT or corrupt subsequent diagnostic records. Errors after publication begins are uncertain and fault the session. Runtime compatibility and world coverage are part of the contract.

Implementation: [src/store.lisp](../../src/store.lisp). Verification: [kernel suite](../../tests/suite.lisp).
