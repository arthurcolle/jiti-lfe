# 0021: Own asynchronous jobs and fence durable remote actor incarnations

Status: Accepted
Date: 2026-10-06

## Context

Persisting a PID would confuse durable logical identity with a live incarnation.
Registry membership alone does not establish supervisory ownership. Restarting
Jiti must not silently replay uncertain external work.

## Decision

Use a session OTP supervisor to own bounded asynchronous LFE jobs. Persist public
receipts rather than PIDs. For standalone Jiti actors, use an opt-in agents.erl
service that saves lifecycle intent and increments durable incarnation generations.
Require matching owner namespace and generation for stop; adoption is explicit.
The established Farm retains its native SQLite owner and controllers unchanged.

## Rationale

Bare spawned processes can outlive a failed manager. Persisted handles without
generation fencing can stop a replacement incarnation. Moving existing Farm state
into another registry would create competing owners. The small standalone adapter
lets Jiti exercise actual OTP identities while preserving that boundary.

## Consequences

Local jobs die with their owner and become unknown after VM loss; they are not
replayed. Remote actor identity and immutable experimental tool grants recover,
while no cognition, inbox or submitted jobs are replayed. Stopped intent remains
stopped. Checksums detect record corruption, not privileged rewriting; power-loss
directory durability is not proven. Owner IDs are namespaces, not cryptographic
authentication: the Erlang cookie trusts the local operator's nodes. The typed
experiment dispatcher enforces grants; arbitrary operator LFE remains cooperative.

Implementation: [runtime](../../src/jiti_runtime.lfe),
[process manager](../../src/jiti_processes.lfe),
[durable service](../../../agents.erl/apps/agents/src/persistent_agent_service.erl),
[minimal supervisor](../../../agents.erl/apps/agents/src/persistent_agents_sup.erl).
Verification: [real local/distributed recovery](../../tests/lfe_planning.py),
[actor crashes, grants and full VM recovery](../../../agents.erl/scripts/test_persistent_agents.py).
Related: [plan admission](0020-lfe-plan-admission-and-verification.md).
