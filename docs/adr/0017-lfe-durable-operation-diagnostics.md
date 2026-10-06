# 0017: Durable LFE operation diagnostics independent of accepted state

Status: Accepted
Date: 2026-10-06

## Context

The LFE controller recovered accepted code/data but lost all evidence of failed,
previewed, or interrupted actions when its VM exited. A repair token alone cannot
identify an attempt across a fresh process, and a failure while reporting a
published revision can leave its outcome uncertain.

## Decision

Give each ordinary evaluation or rollback a durable operation identity before
evaluation. Store one versioned JSON diagnostic record per operation, updating it
through synced temporary files and atomic rename. Repairs, retries and abortion
update the original operation. Store the publishing operation ID in each new
accepted snapshot so recovery can reconcile publication independently of a
missing final diagnostic update. Never recover execution from diagnostics.

## Rationale

Replaying a write-ahead action log could repeat unmanaged Erlang effects.
An append-only diagnostic journal would require framing, torn-tail recovery and
compaction. Atomic individual records reuse the existing publication approach
and avoid appending into incomplete records. This costs filesystem entries and
does not retain an immutable history of every repair step; the final record is
an operation summary, not a full execution trace.

## Consequences

CURRENT and its accepted ancestry remain authoritative. Recovery marks unfinished
operations interrupted unless their identity appears in accepted ancestry, in
which case it records committed publication. Recovered goal results are unknown;
publication alone does not prove the caller's goal. Unfinished operations are
never retried, and live repair tokens are never restored. Graceful quit/EOF abort
a pending attempt. Stale/blocked requests and inspection create no operations.

Diagnostics contain source hashes/lengths, action names, timestamps, statuses,
steps and revision references. They exclude raw source, state, values, conditions
and credentials. Files use mode 0600 in a 0700 directory. The controller retains
100 recent operations and displays 25; older files remain on disk. Corrupt
published records prevent opening the store; incomplete temporary files are ignored.
An operation-write failure closes the controller because the outcome may be
uncertain. Parent-directory sync and power-loss durability remain unverified, as
in [0016](0016-lfe-managed-snapshots.md). The launcher must own the writer lock.

Implementation: [operations](../../src/jiti_operations.lfe),
[controller](../../src/jiti_bridge.lfe), [terminal](../../scripts/lfe_repl.py).
Verification: [actual VM and publication fault scenarios](../../tests/lfe_diagnostics.py).
Related: [SBCL durable revisions](0003-durable-managed-revisions.md),
[LFE snapshot persistence](0016-lfe-managed-snapshots.md).
