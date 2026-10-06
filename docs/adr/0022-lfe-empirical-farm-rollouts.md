# 0022: Allocate experimental descendant trials from independently checked rollouts

Status: Accepted
Date: 2026-10-06

## Context

The retained Agent Farms video design calls for variation, measured acceptance,
resource allocation and independently measured descendants. The user asked for
different tool sets and empirical decomposition rather than invented hierarchies.

## Decision

Run explicit bounded experiments over a sealed scheduling-policy schema. Give six
independent model decisions different immutable subsets of contract inspection,
bounded real-runtime probes and trace retrieval. Execute accepted proposals through
the actual LFE planner on a common held-out task set. Grant one extra descendant
trial based on accepted output and observed execution time; compare parent and
child on fresh common tasks. Retain failures, ties, tool calls, usage and lineage.

## Rationale

Preset agent roles would encode the desired result. Unrestricted model-written code
could alter the test boundary. A small declarative policy separates proposals from
the verifier and makes the first full loop inspectable. The minimum useful tool set
is an experimental question: zero tools is a valid comparison.

## Consequences

Only grouping, priority and width vary. Two model decisions can run concurrently;
each receives at most four Responses requests, six tool calls and two probes.
Task source, expected results, held-out inputs, grants and budgets stay outside
child control. Small arithmetic/delay jobs establish scheduling execution, not
general learning, team benefit, trained MuZero dynamics, negotiation or paid work.
Timing includes orchestration and noise. No winner becomes an operational default.
The observed descendant can fail or regress. A partial experiment requires explicit
continuation; missing receipts remain unknown and cannot count as successful work.
Model billing uses the configured Responses lane; monetary charges are unknown.

Implementation: [bounded runner and dispatcher](../../scripts/farm_rollouts.py).
Verification: [real rollouts and dispatch denial](../../tests/lfe_farm_rollouts.py),
[live evidence](../lfe-farm-verification-2026-10-06.md).
Reference: [retained video design](../../../agent-farm/docs/VIDEO_GROUNDED_FARM_DESIGN.md).
Related: [owned actors](0021-lfe-owned-process-leases.md),
[plan admission](0020-lfe-plan-admission-and-verification.md).
