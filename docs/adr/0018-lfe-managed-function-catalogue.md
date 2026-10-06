# 0018: Persist LFE function catalogue metadata with managed definitions

Status: Accepted
Date: 2026-10-06

## Context

The LFE backend persisted interpreted function bodies but discarded their
documentation and original definition structure. Displaying the raw definition
map could not explain overloaded names, arguments, or callers to a user or model.

## Decision

Retain normalized, readable LFE definition source and documentation in the same
managed snapshot as each name/arity function body. Inspect a deterministic
catalogue in pages of 50 entries and describe individual names by explicit arity.
Descriptions include advisory callers detected in interpreted bodies.

## Rationale

Reconstructing source solely from expanded lambda bodies loses documentation and
the submitted defun structure. A separate metadata store could diverge during
repair, preview or rollback. Metadata in the managed snapshot follows the same
acceptance boundary as code, without requiring compiled-module upgrade semantics.
Keeping name and arity distinct follows Erlang function identity.

## Consequences

Metadata-only changes create revisions; whitespace-normalized identical
definitions remain no-ops. Failed evaluation and preview discard catalogue
changes. Pending repairs expose their provisional catalogue; abort discards it.
Forget and rollback cover metadata as well as the interpreted body. Existing
snapshots without catalogue metadata remain readable, using reconstructed
define-function source until their definitions are replaced.

Inspection never evaluates user functions or interns a supplied name. Summaries
bound documentation and arguments to 512 characters; descriptions bound source
to 4096 with explicit truncation flags. Caller detection ignores quoted data but
cannot find all computed, higher-order or remote calls. Removing a function does
not remove or repair its callers automatically. Source formatting and comments
are not preserved byte-for-byte.

Implementation: [catalogue](../../src/jiti_catalogue.lfe),
[evaluator](../../src/jiti_kernel.lfe), [controller](../../src/jiti_bridge.lfe),
[terminal and native tools](../../scripts/lfe_repl.py).
Verification: [catalogue, recovery and CLI scenarios](../../tests/lfe_diagnostics.py).
Related: [LFE evaluation](0015-experimental-lfe-evaluation.md),
[snapshots](0016-lfe-managed-snapshots.md),
[function removal](0012-managed-function-removal.md).
