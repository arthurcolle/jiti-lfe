# 0010: Development and execution share one transaction engine

Status: Accepted
Date: 2026-10-05

## Context

A user incrementally adds functionality through chat, then wants to call or compose those building blocks without defining another function. Application functions can also mutate managed state or signal resumable conditions.

## Decision

Expose development and execution as distinct intentions over one worker-owned evaluator. Compose using ordinary Lisp expressions. Ordinary execution retains safe managed changes; explicit preview serializes results and restores the entire operation checkpoint. Repairs and restart actions inherit the active operation's transaction and preview policy. Discover application functionality through an adapter-owned catalogue.

## Rationale

A separate pipeline language duplicates Lisp composition and restricts its expressiveness. A separate execution worker loses live dynamic extent. Pure-only execution excludes stateful applications; implicit preview would discard normal application updates. Explicit preview supports experimentation without changing ordinary execution semantics.

## Consequences

Tool names and REPL commands distinguish adding functionality, executing existing functionality, and previewing managed effects. Bare Lisp forms execute normally, including supported definitions. Model instructions favor reuse and save a named composition only on request. Intent is not a hostile-code isolation boundary. Returned values are bounded printable copies, not live handles. Preview cannot reverse unmanaged external effects. The reference adapter covers readable table data, direct named DEFUNs, and literal local FMAKUNBOUND edits (see [0012](0012-managed-function-removal.md)); richer adapters own richer state, catalogues, persistence, and rollback coverage. No application functionality is hardcoded into the kernel.

Related: [worker ownership](0001-worker-owned-live-repair.md), [attempt rollback](0002-managed-attempt-rollback.md), [tool control](0006-interactive-tool-control.md), [change-sensitive revisions](0009-change-sensitive-revisions.md).

Implementation: [worker](../../src/kernel.lisp), [tools](../../src/tools.lisp), [REPL](../../src/cli.lisp). Verification: [composition suite](../../tests/composition-suite.lisp), [CLI scenarios](../../tests/cli_scenarios.py).
