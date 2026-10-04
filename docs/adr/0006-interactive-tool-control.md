# 0006: Interactive tool control

Status: Accepted
Date: 2026-10-04

## Context

Users need to converse with OpenAI about a loaded program over multiple requests, including while a failed call retains live restarts. The single-proposal adapter does not expose native Responses tools or an interactive terminal.

## Decision

Keep one worker-owned interactive session across terminal prompts. Register typed tools with local argument validation and expose them through native Responses function calls. Execute completed calls serially, retain matching call outputs and reasoning items, and bound each chat turn independently from the worker action budget.

## Rationale

A plain Lisp REPL gives the controller direct evaluator access but does not provide the model a discoverable interface or preserve managed acceptance automatically. A new worker per prompt loses suspended restarts. The registry reuses the existing worker boundary and makes tool descriptions and execution agree without changing the deterministic proposer contract.

## Consequences

Interactive sessions report goal checks without terminating when goals pass. Chat is the default input mode, with explicit Lisp mode and commands. Context resets occur only after matching tool results; current world/revision state supplies fresh context. Conversation text is in memory, while accepted world state remains durable. Complete Responses are required before execution; transport failure never executes partial calls. A process lock permits only one CLI for a workspace. This remains a cooperative Lisp environment, not hostile-code isolation.

Related: [worker ownership](0001-worker-owned-live-repair.md), [goal contracts](0004-goals-and-safety.md).

Implementation: [tools](../../src/tools.lisp), [chat controller](../../src/chat.lisp), [terminal](../../src/cli.lisp). Verification: [CLI suite](../../tests/cli-suite.lisp), [process scenarios](../../tests/cli_scenarios.py).
