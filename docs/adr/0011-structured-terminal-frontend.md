# 0011: A structured terminal frontend over the Lisp REPL

Status: Accepted
Date: 2026-10-05

## Context

The interactive session needs editable multiline input, persistent input history, Unicode presentation, and readable results while preserving the worker's live restart stack. The plain line interface remains useful for pipes and automation.

## Decision

Use a Python prompt-toolkit and Rich frontend for terminal editing and presentation, connected to the existing Lisp REPL by structured NDJSON events. Lisp retains command dispatch, form reading, and worker ownership. Completeness probes use the actual Lisp reader with reader evaluation disabled and never execute an action. Store whole submitted inputs privately per workspace; retain conversation context only in memory. Keep the plain interface for noninteractive streams and explicit selection.

## Rationale

A second parser in Python would disagree with Lisp reader syntax. Putting terminal editing into the worker would couple presentation to suspended evaluation. The frontend reuses established editing and rendering libraries while a small bridge keeps kernel semantics in Lisp. A scrolling interface preserves terminal scrollback without introducing a full-screen application. This adds a subprocess protocol and Python dependencies, which require lifecycle and real-terminal verification.

## Consequences

Multiline editing and history recall operate on whole submissions. Enter waits for completeness classification before consuming subsequent input. Displayed application values are literal and control characters are escaped; assistant responses may use Markdown. Terminal input history contains prompts and commands and is stored with permissions 0600. EOF restores provisional changes through existing session shutdown; clearing a draft does not abort a paused call. Glyph rendering depends on terminal and font support. These choices do not isolate hostile Lisp or persist call stacks.

Related: [interactive control](0006-interactive-tool-control.md), [development and execution](0010-development-and-execution.md).

Implementation: [frontend](../../scripts/terminal_ui.py), [bridge](../../src/terminal.lisp), [REPL](../../src/cli.lisp), [launcher](../../scripts/repl.py). Verification: [real terminal scenarios and history properties](../../tests/terminal_scenarios.py).
