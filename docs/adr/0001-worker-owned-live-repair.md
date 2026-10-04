# 0001: Worker-owned live repair

Status: Accepted
Date: 2026-10-04

## Context

A controller must return a condition to its caller while its Common Lisp restarts remain active.

## Decision

Use one persistent SBCL worker per world. Controllers send evaluate, resume, and abort actions; the worker retains the suspended dynamic stack.

## Rationale

A synchronous callback could preserve restarts with less machinery, but would not provide the selected external step API. A mailbox gives external stepping without claiming process isolation.

## Consequences

Restart IDs refer to live objects only within one pause. Repairs execute in the same worker; existing frames retain their old bodies. Cached function objects and inline sites may retain old behavior. Threads do not isolate hangs or crashes.

Implementation: [src/kernel.lisp](../../src/kernel.lisp). Verification: [kernel suite](../../tests/suite.lisp).
