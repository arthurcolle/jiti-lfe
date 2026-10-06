# 0020: Separate plan containment, dependency admission and verification

Status: Accepted
Date: 2026-10-06

## Context

DSCO's plan/step/atom sources distinguish containment from execution precedence.
Jiti needed durable task decomposition and explicit management of multiple jobs.
The user rejected preset agent-role hierarchies and required empirical proposals.

## Decision

Store caller-created task/group containment and dependencies in managed snapshots.
Compute the complete ready frontier from task dependencies and ancestor gates.
Validate their combined wait graph; freeze topology once execution or verification
starts. Fence launch and verification with the current plan version. Require a
successful runtime observation and a separate read-only stored check to finish jobs.

## Rationale

A parent/child tree alone does not describe precedence. A FIFO queue loses ancestor
admission and task relationships. Model-authored success prose cannot establish
completion. A generic representation permits empirically chosen groupings without
making scout/planner/executor roles an architectural requirement.

## Consequences

Plans admit at most 128 nodes and depth 32. Ready ties use priority then binary ID.
Checks return quoted atom true and cannot mutate managed state. No automatic
dispatch occurs. Remote liveness is not proof of substantive agent work; its check
must test the required result. External effects remain outside managed rollback,
and plan publication is not a distributed transaction. Group completion aggregates
children, with an optional extra check. Topology edits require a new plan after start.

Implementation: [planner](../../src/jiti_plan.lfe),
[structured inspection](../../src/jiti_bridge.lfe),
[Jiti-developed helpers](../../examples/planning.lfe).
Verification: [planning and runtime scenarios](../../tests/lfe_planning.py),
[empirical executions](../../tests/lfe_farm_rollouts.py).
Related: [snapshots](0016-lfe-managed-snapshots.md),
[owned processes](0021-lfe-owned-process-leases.md).
