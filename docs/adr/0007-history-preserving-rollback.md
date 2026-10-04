# 0007: History-preserving rollback

Status: Accepted
Date: 2026-10-04

## Context

A user can request restoration of a previous accepted program state. Observation generations change at communication boundaries and cannot identify durable code/data versions.

## Decision

Identify accepted revisions by immutable IDs and monotonically numbered publication history. Worker-executed rollback imports a selected accepted revision, checks current safety invariants, and publishes a new revision whose parent is the former current revision and whose rollback source identifies the restored state. Retain every accepted revision.

## Rationale

Moving CURRENT backwards would erase the intervening ancestry from normal history and reuse numbering after further edits. Replaying actions could reproduce external effects and cannot restore arbitrary continuations. Publishing restored managed state preserves a linear audit trail and reuses the existing atomic publication protocol.

## Consequences

Rollback first unwinds a paused attempt and restores its provisional checkpoint before importing historical state. Restart IDs and observation generations become stale. Import or safety failures restore the current checkpoint; uncertain publication faults the session. Legacy manifests obtain numbers from their parent chain without rewriting accepted artifacts. The model's rollback tool is described as acting only on explicit user requests and asking about ambiguous targets; this instruction is a cooperative model policy, not a separate natural-language authorization classifier. Revision listing excludes abandoned publication artifacts.

Related: [durable revisions](0003-durable-managed-revisions.md), [managed rollback](0002-managed-attempt-rollback.md), [interactive tools](0006-interactive-tool-control.md).

Implementation: [store](../../src/store.lisp), [worker](../../src/kernel.lisp). Verification: [rollback properties and failures](../../tests/cli-suite.lisp).
