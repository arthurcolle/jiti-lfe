# Jiti farm verification — October 6, 2026

## Actual source review

Jiti read DSCO plan/execution and agents.erl supervision sources through native
workspace tools, saved `portfolio-review` at revision 3, then read the retained
video design and current Persistent Episodes/Living Swarm documents. It saved
`video-farm-review` and seven documented planning/process wrappers at revision 5.
The exported [reviews](../evidence/lfe-workspace-and-video-review.json) and
[helpers](../../examples/planning.lfe) preserve those actual model-produced artifacts.
The earlier portfolio review's implementation-status describes its review-time
state; the planner/process implementations and gates now exist separately.

The exact video is `Gw_hnD7m00M`. The design is
[Agent Farm: the population is the product](../../../agent-farm/docs/VIDEO_GROUNDED_FARM_DESIGN.md).
The cached captions, normalized transcript and creator notes match the manifest's
SHA-256 digests. This run reread that design; it does not claim a fresh visual review.

## Bounded live comparison

Seven actual supervised farm_actor identities used temporary independent
`gpt-6.1-sol` Responses cognition. Six variants had different immutable tool grants;
one descendant inherited an observed parent's policy and evidence. The child tool
boundary admits contract inspection, actual-runtime probes and baseline trace
retrieval. It denies arbitrary source, shell, grant changes and verifier changes.
Models proposed grouping, priority and concurrency width, within a sealed schema.
No named agent-role hierarchy was prescribed.

| Actor | Dataset | Granted tools | Proposed grouping | Verified jobs | Elapsed ms |
|---|---|---|---|---:|---:|
| variant-1 | common | none | flat | 18 | 738.491 |
| variant-2 | common | contract | flat | 18 | 743.54 |
| variant-3 | common | probe | flat | 18 | 727.621 |
| variant-4 | common | contract, probe | components | 18 | 760.884 |
| variant-5 | common | trace | flat | 18 | 733.041 |
| variant-6 | common | contract, probe, trace | flat | 18 | 745.429 |
| descendant-1 | fresh | probe | flat | 18 | 815.828 |
| variant-3 parent comparison | fresh | probe | flat | 18 | 803.195 |

All variants chose critical-path priority and width 2. Five chose a flat graph;
one chose connected-component groups. The six variants independently passed
108 jobs on identical held-out cases. The serial baseline passed 18 jobs in
1389.299 ms. Each task has independently checked arithmetic,
actual delay/worker execution, exact-once launch and verified precedence.
Timing includes local orchestration and is not general model throughput.

`variant-3` received one extra descendant decision and three fresh trials
because all its outputs passed and its observed common-case time was least.
This is a small comparison subject to noise. Parent and child chose the same
policy. On the identical fresh set, parent elapsed was
803.195 ms and child was 815.828 ms.
The descendant passed but did not improve. No runtime default was promoted.
The no-tool variant also chose the prevailing policy, so this does not establish
that additional tools improve decisions. It is not trained MuZero, emergent
negotiation, general team learning, reproduction economics or paid work.

## Failure retained and explicit continuation

The first live pass stopped on a receipt serializer that lacked floating-point
support. Two proposals were retained; four prior proposals were not durably
captured and remain unknown. Baseline final outputs were independently recovered
from their actual managed plan; its public timing/chronology remain unknown.
The serializer was fixed and per-decision reservation/proposal journals added.
Explicit continuation reused the two retained proposals and obtained new decisions
for missing proposals. Failed/missing prior receipts were not counted as successes.
The first pass ceiling was 24 Responses requests; continuation ceiling was 20
(the conservative combined declaration is 48). Retained successful decisions
account for 18 requests;
physical usage of lost first-pass decisions is unknown. Token usage is retained
where received. Billing uses the configured Responses lane; monetary charges are
unknown. No provider default, subscription lane or routing policy was switched.

## Actual recovery

After completion, the experiment node was stopped and relaunched from its actor
records. All seven identities and immutable grants recovered. Old generation
handles observed `stale`; old-generation stop was denied. Explicit adoption
observed the newer generation. All seven actors were idle with empty messages;
no cognition or jobs replayed. Runtime receipt:
`../.jiti/rollouts/20261006-empirical/runtime-recovery.json`.
The experiment completed at population revision 27; recovery
and explicit adoption subsequently published newer revisions.

## Artifacts and operation

- [Live comparison and lineage](../../.jiti/rollouts/20261006-empirical/index.html).
- [Full retained report](../../.jiti/rollouts/20261006-empirical/report.json).
- [VM recovery proof](../../.jiti/rollouts/20261006-empirical/runtime-recovery.json).
- [Standalone actor startup](../../../agents.erl/docs/PERSISTENT_JITI_ACTORS.md).
- [Bounded runner](../../scripts/farm_rollouts.py).

The existing Farm keeps its native SQLite/controller ownership. Jiti's adapter
is opt-in and owns standalone experiment identities. Remote identities persist;
local asynchronous jobs are session-owned. Operator LFE is cooperative and is
not a hostile-code sandbox. External effects are outside managed rollback.
The machine has no `devenv`, SBCL or Nix executable, so original SBCL `devenv`
gates could not run. LFE tests and actual Responses calls are separate evidence.

Verification commands: `make test` in Jiti;
`python3 scripts/test_persistent_agents.py` in agents.erl. The focused suite proves
actual crashes, full local/remote recovery, dependency/ancestor gates, independent
checks, tool denial, held-out jobs, permissions, corruption and CLI inspection.
ADRs 0019–0022 record these decisions and evidence boundaries.

## Durable Jiti observations and handoff

Jiti read this receipt through its terminal and saved `farm-rollout-observations`,
`implementation-checkpoint` and `farm-observations/0` at revision 6. The original
reviews remain historical. A fresh LFE VM reopened that image and recovered the
accessor. Its exported [observations](../evidence/lfe-farm-observations.json) and
[accessor](../../examples/farm-observations.lfe) retain the measured regression and
missing-receipt uncertainty. The terminal writer was released for normal user chat.

Final gates: `make test` passed all four LFE suites and 22 ADR validations;
`python3 scripts/test_persistent_agents.py` passed. Original SBCL gates remain
unavailable for the missing-toolchain reason above.
