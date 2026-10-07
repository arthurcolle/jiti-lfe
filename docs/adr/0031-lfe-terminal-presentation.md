# 0031: An optional scrolling terminal editor for LFE

Status: Accepted
Date: 2026-10-06

## Context

The LFE frontend needs readable chat and whole-message editing while preserving
raw receipts and the existing bridge protocol.

## Decision

Use prompt-toolkit and Rich only in interactive terminals. Keep input history and
a bounded receipt browser in memory. A repo-local optional environment supplies
presentation dependencies; batch, JSON and legacy dispatch remain independent.

## Rationale

The established terminal libraries provide multiline editing and Markdown without
coupling the evaluator to a full-screen application. Memory-only history avoids
silently writing model prompts to disk. Plain clients need no UI dependencies.

## Consequences

Quiet tools retain their complete receipts for local inspection. Terminal editing
does not issue bridge calls; spinners do not retry requests. Chat context still
ends with its frontend session. Source completeness is advisory; LFE remains the
reader and evaluator. Small terminals reflow content; glyphs depend on the font.

Implementation: [presentation](../../scripts/lfe_terminal.py), [launcher](../../scripts/repl.py).
Verification: [receipt fidelity](../../tests/lfe_display_test.py), real PTY execution.
Related: [structured terminal](0011-structured-terminal-frontend.md), [targeted observations](0029-targeted-cli-observations.md).
