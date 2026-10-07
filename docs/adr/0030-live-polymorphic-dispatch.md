# 0030: Resolve durable polymorphic calls against the live managed image

Status: Accepted
Date: 2026-10-06

## Context

Fixed name/arity calls cannot select implementations from heterogeneous values or
persist a composed capability that follows later repairs.

## Decision

Keep multimethod registries and named partial/composition descriptors in managed
state. Resolve implementations against the current provisional definitions at
invocation. Explicit remote descriptors invoke existing Erlang module functions;
they expose the same cooperative execution boundary as ordinary remote LFE calls.
Select the unique most specific matching argument signature; reject
incomparable matches. Temporary closures can execute but cannot become durable data.

## Rationale

Capturing function objects would retain obsolete code and prevent recovery. First
match registration order would hide ambiguous overloads. A specificity partial
order makes overlapping multi-argument signatures explicit without a ranking score.

## Consequences

Method edits obey safety, preview, publication and rollback. Replacing a managed
function changes subsequent calls through stored descriptors. Missing or ambiguous
implementations pause an action; repair retries the whole action. External effects
remain outside managed rollback. Registries do not grant execution permissions.
Managed definitions can shadow convenience names; explicit `jiti_dispatch` calls
remain available without taking over an existing application's function names.

Implementation: [dispatch](../../src/jiti_dispatch.lfe), [environment](../../src/jiti_kernel.lfe).
Verification: [native scenarios](../../tests/lfe_dispatch.py).
Related: [snapshots](0016-lfe-managed-snapshots.md), [goals and safety](0004-goals-and-safety.md).
