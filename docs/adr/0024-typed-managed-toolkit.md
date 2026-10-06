# 0024: Use typed operations within the existing managed evaluator

Status: Accepted
Date: 2026-10-06

## Context

Normal LFE chat required generated source for routine state edits, function calls,
notes and job inspection. Planning already has typed adapters, but generic source
does not expose literal data types, atomic patches or separate test observations.

## Decision

Add a bounded typed toolkit whose mutations run inside the same provisional LFE
worker and publish through existing safety checks, snapshots and diagnostics.
Require the current revision for managed mutations and offer explicit previews.
Decode data from JSON rather than evaluating data fields as source. Keep read-only
inspection separate and return typed results under a nested `data` field; core
revision, goal and pause tokens remain controller-owned. A typed rejection restores
the provisional candidate and records a rejected operation without a new pause.

## Rationale

More source-generation examples would leave everyday operations vulnerable to
quoting and stale-write mistakes. Implementing state/code storage in Python would
introduce a second owner and bypass rollback. Typed entry points preserve the
existing evaluator and make literal arguments, revisions and observations explicit.
Function bodies remain explicitly cooperative executable LFE, not a sandbox.

## Consequences

The toolkit adds 31 tools for managed state, functions, owned jobs, durable notes,
effective tool discovery and bounded workspace searches. Values have 32 KiB,
16-level and 1024-node JSON bounds; requests have a 128 KiB adapter bound. JSON
strings become binaries, arrays become lists and object keys remain binaries.
Unknown atom/function reads do not intern names. Explicit definitions/atom puts
may intern symbols, as existing cooperative source can. Internal records use
separate tuple keys rather than appearing as ordinary state entries.

Tests and predicate checks restore the candidate between observations and reject
managed mutations as evidence. They do not undo external I/O, substitute for owner
safety checks or independently validate model-authored expected values. Previews
discard managed code/data only. Caller detection remains advisory for computed
calls. Tool discovery and dispatch are restricted to advertised tools. Workspace
search inherits existing read-only paths, file types and symlink restrictions.
Notes are durable owner-controlled data with revision provenance, not authority.

Implementation: [typed schemas/adapters](../../scripts/lfe_toolkit.py),
[native operations](../../src/jiti_toolkit.lfe),
[worker entry points](../../src/jiti_kernel.lfe),
[controller receipts](../../src/jiti_bridge.lfe).
Verification: [actual BEAM scenarios](../../tests/lfe_toolkit.py),
[bounded live smoke](../../tests/lfe_toolkit_live.py),
[contract review](../lfe-toolkit-contract.md).
Related: [managed snapshots](0016-lfe-managed-snapshots.md),
[function catalogue](0018-lfe-managed-function-catalogue.md),
[workspace inspection](0019-lfe-bounded-workspace-inspection.md),
[native planning](0023-native-lfe-planning-tools.md),
[named admission fencing](0025-named-job-admission-fencing.md).
