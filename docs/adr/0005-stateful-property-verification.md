# 0005: Stateful property verification

Status: Accepted
Date: 2026-10-04

## Context

Most kernel failures involve sequences of suspension, mutation, rollback, and recovery rather than isolated forms.

## Decision

Use check-it generation and shrinking with FiveAM suites, comparing generated histories against an independent model of data and function behavior.

## Rationale

Example tests cover specific Lisp semantics but do not explore many action combinations. Unrestricted random Lisp mostly yields invalid or uncontrolled programs; bounded commands produce useful model-based histories.

## Consequences

Record seeds and minimized traces for replay. Use process-kill publication tests and injected storage failures. Passing generated cases is evidence, not proof or a power-loss simulation.

Implementation: [tests/suite.lisp](../../tests/suite.lisp). Verification: [kernel suite](../../tests/suite.lisp).
