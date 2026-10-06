# 0016: Separate managed snapshot storage for LFE

Status: Accepted
Date: 2026-10-05

## Context

The experimental LFE backend needs fresh-process recovery of accepted immutable
data and interpreted definitions. The SBCL store format and live stack are not
interchangeable with BEAM terms.

## Decision

Use a separate local LFE store containing immutable, versioned, checksummed BEAM
term snapshots and a synced temporary CURRENT file published through rename.
The Python launcher holds an OS advisory writer lock throughout VM ownership.
Recovery loads only CURRENT; failed or unfinished actions are never replayed.

## Rationale

Reusing the SBCL format would misrepresent runtime compatibility and requires a
real migration adapter. Replaying an action log could repeat unmanaged effects.
Managed snapshots keep the recovery boundary explicit, as in
[0003](0003-durable-managed-revisions.md), without changing the SBCL decision.

## Consequences

Only changes to final managed data or definitions create revisions. Rollback
publishes earlier accepted content with new ancestry; it does not decrement the
revision counter. Unpublished orphan files are skipped and excluded from history.
Store errors close the controller because publication may have an uncertain
outcome. Fresh-process recovery requires the same OTP major release.

The store is trusted owner-controlled local input. The envelope uses safe term
decoding and a checksum; the payload recreates user atoms and is not an untrusted
data format. Snapshots reject runtime handles in managed data. Files are created
with permissions 0600. The supported Python entry point enforces one writer;
direct bridge callers must provide equivalent locking. CURRENT and snapshot files
are synced, but parent-directory syncing and power-loss durability have not been
established. [0017](0017-lfe-durable-operation-diagnostics.md) adds separate durable
operation diagnostics without replay. This experiment has no schema migration,
replication, consensus or legacy-store import. Optional catalogue metadata and
publishing-operation identities preserve readability of older LFE snapshots.

Implementation: [store](../../src/jiti_store.lfe),
[writer lock](../../scripts/lfe_repl.py), [controller](../../src/jiti_bridge.lfe).
Verification: [fresh VM, rollback, orphan, corruption and writer tests](../../tests/lfe_scenarios.py).
Related: [experimental evaluator](0015-experimental-lfe-evaluation.md),
[change-sensitive revisions](0009-change-sensitive-revisions.md),
[history-preserving rollback](0007-history-preserving-rollback.md).
