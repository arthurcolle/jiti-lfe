# 0025: Fence named launches in the existing owner manager

Status: Accepted
Date: 2026-10-06

## Context

A typed job launch starts an external owned process before its receipt publishes.
Safety rejection or managed rollback can remove the receipt while leaving the
manager's admitted job. Checking managed state alone would allow duplicate retries.

## Decision

Give named local job launches an owner-manager request key and a source/timeout
hash. Repeating a key with the same hash returns the existing public handle;
different content conflicts. Apply this check atomically within the existing
manager before admission limits or process creation. Persist the accepted handle
and request hash in managed state. Reconciliation never starts replacements.

## Rationale

Only a managed receipt fence cannot cover rejected publication or rollback. A new
scheduler or job registry would duplicate the established owner. Checking within
the existing manager covers concurrent/repeated requests while retaining current
job limits, cancellation and worker cleanup. Durable snapshots cover accepted
receipts across a fresh runtime; the manager itself remains ephemeral.

## Consequences

Deduplication survives managed rollback inside the same runtime. A recorded key
cannot be reused to run against a different inherited snapshot; use a new ID for
new work. Source and timeout hashes are public receipts, not execution source.
The existing unnamed process-start API remains unchanged.

After VM loss local observations are unknown; stored terminal results remain
separate from current observation. Repeated requests with durable receipts return
those receipts and never relaunch. Unknown handles cannot cancel a replacement.
Launch/cancellation remain outside managed rollback. A crash or publication failure
before durable recording still has an uncertain external-effect boundary; manager
deduplication is not a durable exactly-once guarantee. Inspect evidence and never
blindly replay that request. No automatic job admission or recovery scheduling is
introduced.

Implementation: [owner manager](../../src/jiti_processes.lfe),
[typed job operations](../../src/jiti_toolkit.lfe),
[bounded frontend waits](../../scripts/lfe_toolkit.py).
Verification: [deduplication, rejected publication, rollback, cancellation and
fresh-VM scenarios](../../tests/lfe_toolkit.py).
Related: [owned process leases](0021-lfe-owned-process-leases.md),
[managed snapshots](0016-lfe-managed-snapshots.md),
[typed toolkit](0024-typed-managed-toolkit.md).
