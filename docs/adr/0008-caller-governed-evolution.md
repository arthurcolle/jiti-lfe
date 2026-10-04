# 0008: Caller-governed autonomous evolution

Status: Accepted
Date: 2026-10-04

## Context

A live evolution experiment needs the Lisp process to generate prompts and refine a running program without letting model completion claims or model-created tests define success.

## Decision

Drive the existing interactive tool controller with a bounded Lisp loop that generates prompts from a caller-owned goal and observed check failures. Require executable caller goals to pass at an idle boundary. Keep the evolving function absent initially, and prove the learned implementation survives fresh-process recovery and history-preserving rollback.

## Rationale

A fixed sequence of terminal prompts would demonstrate API interaction but leave correction to the operator. Trusting model-written tests would allow the acceptance contract to drift. The outer loop reuses worker ownership, one-form evaluation, managed revisions, and native tool calls while reserving acceptance and budgets for the caller.

## Consequences

The Unicode experiment supplies fixed examples and seeded generated inputs, not an implementation. It checks original grapheme order, input immutability, fresh results, length, and code-point contents. Generated boundaries depend on the pinned SBCL Unicode implementation; fixed expectations are independent. Failed candidates produce bounded, minimized replay artifacts with source and environment evidence. Each model turn is bounded, the worker action budget remains independent, and an external watchdog bounds the experiment process. Caller experiment symbols are package-protected. This demonstrates managed program evolution; active continuations and unmanaged resources retain the existing limitations.

Related: [goals and safety](0004-goals-and-safety.md), [interactive tools](0006-interactive-tool-control.md), [history-preserving rollback](0007-history-preserving-rollback.md).

Implementation: [evolution driver](../../src/experiments.lisp), [watchdog launcher](../../scripts/experiment.py). Verification: [experiment tests](../../tests/experiment-suite.lisp).
