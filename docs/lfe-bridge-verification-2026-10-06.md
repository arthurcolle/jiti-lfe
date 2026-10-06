# LFE conversion and local agents.erl bridge verification

Date: 2026-10-06
Repositories: `/Users/arthurcolle/Dsco/jiti` and
`/Users/arthurcolle/Dsco/agents.erl`.

## Implemented conversion checkpoint

- Source-free durable operation summaries, stable attempt identities through
  repair/retry/abort, and reconciliation against accepted snapshot ancestry.
- Managed function catalogue metadata, documentation, normalized source,
  name/arity inspection, advisory callers and bounded pagination.
- Terminal commands and native LFE Responses tools for these inspections.
- ADRs 0017 and 0018, with the persistence consequences in 0016 updated.

`make test` passed on OTP 29 and pinned LFE 2.2.2:

```text
LFE scenarios and 180 generated state-machine actions passed
LFE catalogue, durable operations, real crash/publication faults, bounds, and CLI passed
18 ADRs: identities, evidence links, and supersession valid
```

The diagnostics scenarios exercise actual VM death during evaluation, a final
diagnostic publication fault after CURRENT advances, old snapshots without
catalogue metadata, Unicode truncation, and recovery beyond the 100-record
inspection window. `git diff --check` also passed for tracked changes.

`devenv shell test` and `devenv shell test-live` could not run: `devenv` is absent.
SBCL was also absent during this work. Those legacy gates are not claimed as
passed. This remains an experimental LFE backend, not a completed SBCL port.

## Live terminal bridge

No local BEAM VM or epmd listener was present when inspected. A minimal local
target was started from the existing agents.erl build: registry, model selection
service, dynamic agent supervisor, and one idle `agent_instance`. It did not start
the web application or its fleet. The agents.erl source tree remained clean.

Target identity:

```text
node: agents_jiti@127.0.0.1
agent ID: jiti-bridge-agent
name: Jiti bridge target
type: ai
model: gpt-5.6-sol
autonomous_mode: false
metrics: total_requests=0, successful_requests=0, failed_requests=0, total_tokens=0
```

The model field above is decoded from the actual RPC response. The chat model's
prose incorrectly called it gpt-5.4-sol; the remote state is authoritative.

In a real PTY running `scripts/repl.py --lfe --mode chat`, Jiti was asked to
connect using native LFE tools, verify the registry and agent state, save only
the endpoint and agent ID, and define `agents-status/0`. Successful tool results
showed connection and remote state. The definition and managed endpoint were
saved at revision 2 of `.jiti/agents-bridge`; the exact normalized definition was
exported to [examples/agents-bridge.lfe](../examples/agents-bridge.lfe).

After gracefully closing the first terminal, a fresh VM recovered that store:

```text
lfe> (erlang:node)
value: nonode@nohost
lfe> (agents-status)
value: remote agent state with the identity and zero-request metrics above
lfe> (erlang:node)
value: jiti_lfe_10933@127.0.0.1
lfe> (erlang:nodes)
value: (agents_jiti@127.0.0.1)
```

`epmd -names` listed both nodes. `lsof` showed the target listening on
`127.0.0.1:52888`, Jiti listening on `127.0.0.1:53924`, and an established
distribution connection between the two VMs. These PIDs, node names and ports
are run observations, not stable configuration. Both processes remained running
at this checkpoint.

## Boundaries

The target stayed idle: no remote inference or autonomy was enabled. Existing
Erlang cookie handling was automatic; credentials were never read or displayed
by the model. Distribution was bound to loopback. RPC and networking are external
effects outside managed rollback. This proves status lookup and reconnection,
not remote task execution, replication or distributed transactions.

Desktop control of Kitty and Terminal was rejected by app permissions. The
verified terminal interactions used tool-managed PTYs.
