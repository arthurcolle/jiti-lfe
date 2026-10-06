# 0019: Provide bounded workspace evidence to LFE chat

Status: Accepted
Date: 2026-10-06

## Context

Jiti was asked to study the adjacent DSCO repositories. Generic evaluation printed
deeply truncated directory/source values, so the model could not reliably inspect
the actual contracts or retained video design.

## Decision

Expose typed listing and source-reading tools under the literal DSCO workspace.
Return paginated structured results with explicit byte offsets and encoding.
Reject absolute paths, hidden components, traversal, symlinks and non-source types.

## Rationale

Prompt-only summaries cannot establish current implementation. Generic file I/O
in evaluated source is difficult to bound or inspect. Small typed readers make
evidence readable without adding shell execution to the inspection interface.

## Consequences

Pages contain at most 80 names or 12,000 source bytes. Paths are installation
specific. Encoding fallback is explicit. This convenience API is not a hostile
code sandbox or a race-free filesystem authority boundary: the cooperative
operator evaluator still has ordinary Erlang file/process capabilities.

Implementation: [workspace reader](../../src/jiti_workspace.lfe),
[controller and tools](../../scripts/lfe_repl.py).
Evidence: [actual Jiti reviews](../lfe-workspace-and-video-review.json).
Related: [LFE evaluation](0015-experimental-lfe-evaluation.md).
