# 0026: Managed project bindings with fresh source evidence

Status: Superseded
Date: 2026-10-06
Superseded by: [0028: Native LFE workspace operations](0028-native-lfe-workspace.md)

## Context

DSCO-relative source readers can inspect a file but do not preserve a project's
selection or its important source/contract references. Conversation summaries
alone cannot establish whether source still matches a prior observation.

## Decision

Store project bindings, pinned references and bounded digest manifests as managed
state. Obtain fresh source evidence through the existing native read-only boundary;
compute code maps and digest comparisons in the frontend without executing files.
Include only bounded project metadata automatically in model context, with source
excerpts explicitly fetched as evidence. Preserve coverage and unknown outcomes.

## Rationale

Conversation-only selection disappears on restart and mixes remembered content
with current evidence. A separate project database would create another rollback
and recovery authority. Existing managed snapshots already own durable state and
revision fencing. A full repository index or source-copy store would add cache
invalidation and storage machinery beyond this bounded inspection use case.

## Consequences

Metadata preview, rollback and recovery follow the existing kernel. File edits
remain external and are never restored by these tools. Hash baselines are not
atomic filesystem snapshots or backups. Scans exclude dependencies/generated
content and expose coverage limits; partial comparisons cannot assert an unchanged
project. Code maps outside Python AST declarations are lexical. Selected roots
remain beneath the existing installation-specific DSCO root, with no added grants.

The initial Python adapter was removed by the successor. Current implementation:
[native observations](../../src/jiti_workspace_project.lfe),
[managed records](../../src/jiti_workspace_state.lfe),
[native reader](../../src/jiti_workspace.lfe), [chat](../../scripts/lfe_repl.py).
Verification: [offline](../../tests/lfe_workspace.py),
[bounded live runner](../../tests/lfe_workspace_live.py),
[report](../verification/lfe-workspace-verification-2026-10-06.md).
Related: [source boundary](0019-lfe-bounded-workspace-inspection.md),
[typed tools](0024-typed-managed-toolkit.md), [guide](../workspace.md).
