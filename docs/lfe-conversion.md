# LFE backend

LFE is the default backend in this fork: `make repl` starts manual evaluation and
`make chat` starts normal chat. `--lfe` remains compatible; `--legacy` explicitly
selects the inherited [SBCL backend](sbcl.md). The stores and repair models remain
separate. See [ADR 0027](adr/0027-lfe-fork-default.md), the original isolated
evaluation decision [0015](adr/0015-experimental-lfe-evaluation.md), and
[managed persistence](adr/0016-lfe-managed-snapshots.md).

## Build and run

Install Erlang/OTP 27 or later, Git, Make, Bash and Python 3. The implementation
was verified on OTP 29 with LFE 2.2.2. The build fetches LFE tag `v2.2.2` if absent
and checks commit `dae7489ebf9588e5f746a34cd4f8ff83d1469eef`. Neither the dependency
checkout nor generated BEAM files belong in Git.

```sh
make
make test
make repl
```

In the LFE terminal:

```lisp
(+ 2 3)
(defun twice (x) (* x 2))
(state-put 'x (twice 7))
(twice (state-get 'x))
```

The values are `5`, `twice`, `14`, and `28`. Reopening the same store recovers the
definition and `x`. Pure expressions and identical final definitions/data do not
create revisions. Ordinary named functions support recursion, pattern clauses,
and lexical function arguments. Use `(forget 'twice 1)` to remove a definition.
Persisted definitions are interpreted LFE forms, not hot-loaded BEAM modules.

```sh
python3 scripts/repl.py --lfe --store /tmp/jiti-lfe-demo --eval '(+ 2 3)' --json
devenv shell -- lfe-repl
devenv shell test-lfe
```

`--eval` exits successfully only for an `ok` result. `--plain` supports pipes;
`--json` emits JSON lines. Source may contain multiple top-level forms. Multiline
terminal input is collected until balanced, then parsed by the actual LFE reader.
Rebuild after editing `.lfe` files; the frontend rejects stale/incomplete builds.

## Inspect the application

Routine commands show their result and revision. They no longer dump all managed
state. Start with `/status` for capability counts and any pending repair, then use
the appropriate inspection:

```text
/state                    List ordinary keys with short value previews
/state diagnosis          Read one atom-keyed value
/state last-invoice binary Read a binary-keyed value
/functions                Discover managed functions
/describe invoice-total 1 Inspect a function's source and callers
/plans                    List saved plans; /plan ID shows dependencies and checks
/jobs                     List job receipts; /job ID shows recorded/current status
/notes                    List saved notes; /note ID reads one
/help                     Quick command guide; /help all lists advanced controls
/exit                     Close; /quit and /q also work
```

`/state-list OFFSET`, `/functions OFFSET`, `/plans OFFSET`, `/jobs OFFSET`, and
`/notes OFFSET` continue paginated inspection. Tuple-keyed internal records belong
to the plans/jobs/notes interfaces, not ordinary state lookup. Inspections do not
create revisions or resume work. `/details` shows the last received raw bridge
receipt without issuing a new operation; `--json` keeps raw JSON output.

Returned values use a native bounded LFE pretty view. A printable integer list
may appear in string notation; its stored type is unchanged. Display shortening
and native depth/size bounds are explicit. Inspect a specific field when necessary.
An `ok` receipt says the operation ran; a returned `blocked` diagnosis still needs
resolution. Goal outcomes are shown for evaluated actions with goal predicates,
and remain separate from safety checks.

Chat receives operation receipts and targeted observations rather than a repeated
whole-state dump. Successful tools show one activity line and chat explains their
outcomes; errors and pending repairs show their details immediately. Chat
automatically compacts at its configured threshold; `/context`
shows the budget, `/compact` compacts now, and `/recall QUERY` searches archived
excerpts. Compaction is local and lossy. `/clear` clears conversation context while
preserving the application and pending repair. See [ADR 0029](adr/0029-targeted-cli-observations.md).

## Native chat planning

```sh
python3 scripts/repl.py --lfe --mode chat
```

Describe the work normally. For example: “Create a plan with two independent
data checks and a final task that depends on both. Run the checks, inspect their
actual results, and verify the acceptance contract before running the final task.”

Chat now receives nine native planning tools:

| Tool | Behavior |
| --- | --- |
| `plan_list` | Discover saved plans, 50 per page. |
| `plan_create` | Build up to 32 task/group nodes atomically, including forward references. |
| `plan_add`, `plan_depend` | Extend unstarted plans using the current version. |
| `plan_launch` | Explicitly start one admitted task through the owned job manager. |
| `plan_reconcile` | Observe existing jobs and publish their outcomes. |
| `plan_wait` | Wait up to 30 seconds for existing jobs and reconcile receipts. |
| `plan_verify` | Apply the stored read-only acceptance check. |
| `plan_control` | Block/unblock admission or cancel owned work. |

Each task supplies its acceptance check, optional LFE job source and deadline.
Checks are not inferred from a successful exit or a model's completion statement.
Caller-supplied checks remain the acceptance contract. A check supplied by an
agent needs independent review before it can establish owner/customer usefulness.
Jobs inherit a snapshot; job-local state writes do not publish owner state.
Lifecycle changes require the returned `plan_version`; stale edits are rejected.
After start, topology freezes. A failed kernel edit may pause the managed action;
abort it before attempting a new edit. Launch/cancellation have external effects
that managed rollback cannot undo. Recovery observes saved state and never
automatically launches replacement jobs.

Wait through `plan_wait`, which runs outside the short evaluation deadline and
does not issue extra model requests. A timed-out wait reports jobs still running
without pausing a kernel action. Waiting neither launches nor verifies work.

`/plans [OFFSET]` and `/plan ID` expose the same discovery and inspection in the
terminal. Inspection includes public job IDs, timestamps and result receipts.
The default model output budget is 8192 tokens per request; use
`--max-output-tokens 16384` for larger generated definitions (maximum 32768).
The existing `/tool-limit N` control independently changes the per-turn call limit.

Offline verification is included in `make test`. An explicit credentialed smoke
runs two actual concurrent jobs, verifies their fixed checks, executes a dependent
join, and checks fresh-process recovery without replay:

```sh
python3 tests/lfe_native_plans_live.py --output .jiti/native-plans-live-NEW
```

The smoke has at most 18 model tool calls and 20 Responses requests. Use a fresh
output directory; a previous workflow is never resumed automatically. Monetary
charges remain unknown. [ADR 0023](adr/0023-native-lfe-planning-tools.md) records
the adapter decision; [live verification](verification/lfe-native-plans-verification-2026-10-06.md)
retains the observed workflow, initial failures and recovery evidence.

## Expanded native toolkit

Normal chat now includes 69 native LFE tools, plus 9 conversation-context tools.
The [project workspace](workspace.md) adds 14 tools for saved project selection,
pins, code maps, source evidence, digest baselines and observed changes.
The 31 additions below use the same evaluator, snapshot store and owned process
manager. Their advertised names have an `lfe_` prefix; ordinary prompts need no
special syntax.

| Family | Added tools |
| --- | --- |
| State | `state_list`, `state_get`, `state_put`, `state_delete`, `state_increment`, `state_compare_set`, `state_append`, `state_merge`, `state_patch` |
| Functions | `function_search`, `function_source`, `function_define`, `function_call`, `function_test`, `function_forget` |
| Checks | `expression_check` |
| Jobs | `job_start`, `job_list`, `job_status`, `job_reconcile`, `job_wait`, `job_cancel` |
| Working notes | `note_put`, `note_get`, `note_list`, `note_search`, `note_delete` |
| Discovery | `tools_list`, `tools_describe` |
| Workspace | `workspace_find`, `workspace_search` |

Examples of normal chat:

> Define invoice-total for rows with qty and price fields. Test an empty invoice
> and a three-row invoice, then save the verified total in managed state.

> Find the LFE toolkit source, inspect its tools, and save a short note about the
> relevant limits so we can retrieve it after reopening.

> Run this long calculation as a named background job, wait for its actual result,
> and show its recorded receipt. If we restart, inspect it before doing more work.

Data fields accept serialized JSON: strings become UTF-8 binaries, arrays become
lists and object keys are binaries. A call's `args_json` is a literal JSON array.
State operations explicitly distinguish atom and binary keys. Unknown reads do
not create atoms. Structured responses appear under `data`, with bounded values,
explicit presence and pagination. Function source pages recover the complete
normalized form rather than silently stopping at the old 4096-character display.

Managed mutations require the actual `expected_revision`; old retries are rejected.
`preview=true` discards managed edits. Atomic patches discard all edits if any
step or owner safety check fails. Previews and tests cannot undo external I/O.
Function tests and predicate checks restore provisional code/data and report
mutating or false checks as failed observations. Their expected values still need
independent acceptance criteria for claims about correctness or usefulness.

Named jobs deduplicate identical ID/source/timeout requests within the owner
manager, including after managed rollback or safety rejection. Accepted handles
also persist in snapshots. A different request with the same ID conflicts; use a
new ID for new work, including work against a changed inherited snapshot.
`job_wait` waits at most 30 seconds outside evaluation, then reconciles once.
After VM loss, current observations are unknown while recorded terminal results
remain available. Inspection and reconciliation never replay jobs. Unknown handles
cannot cancel a replacement. A crash before durable recording remains an uncertain
external-effect boundary: inspect, never blindly retry.

Notes record their input revision, text and tags in managed state. They are
working data and must contain no credentials. Tool discovery exposes only tools
advertised to that chat and cannot enable additional capabilities. Workspace
finding/search uses existing read-only restrictions and reports bounds, truncation
and offset accuracy; no shell or workspace writer is added.

`make test` includes [all 31-tool BEAM scenarios](../tests/lfe_toolkit.py).
To explicitly run the bounded live smoke with configured credentials:

```sh
python3 tests/lfe_toolkit_live.py --output .jiti/toolkit-live-NEW
```

The live runner caps 24 Responses requests and 22 model tool calls, validates the
actual code, cases, result and single job, then reopens the store and checks that
no jobs were replayed. Use a fresh output directory. See the
[contract review](lfe-toolkit-contract.md), [typed-tool ADR](adr/0024-typed-managed-toolkit.md)
and [named-job ADR](adr/0025-named-job-admission-fencing.md).
The [verification receipt](verification/lfe-toolkit-verification-2026-10-06.md) records the
observed model workflow, retained initial harness failure and recovery checks.

## Managed evaluation and explicit repair

The controller owns accepted code/data. A monitored process evaluates each action
against a provisional snapshot under `--timeout-ms` (default 1000). A failure
discards that evaluator's provisional mutations and retains the original source,
base snapshot and a repair token. There is no suspended stack.

```text
lfe> (future 4)
paused ... token=...
lfe> /repair (defun future (x) (+ x 1))
lfe> /retry
ok ... value: 5
```

Repairs stay provisional until retry succeeds. Retry runs the entire failed
action again. `/abort` and failed repairs discard the provisional attempt.
Repair/retry/abort accept an explicit token; stale tokens are rejected. New
ordinary actions and rollback are rejected while a repair is pending.
`/preview SOURCE` returns a value and discards successful managed mutations,
including repaired preview attempts.

Caller-owned checks are selected at startup, not generated by the chat model:

```sh
python3 scripts/repl.py --lfe \
  --safety "(orelse (=:= (state-get 'x) 'undefined) (>= (state-get 'x) 0))" \
  --goal "(=:= (state-get 'x) 7)"
```

Checks must return the atom `true` and leave managed state/code unchanged.
Signalled/failed safety checks reject candidates. Unmet or signalled goals allow
safe intermediate progress and report `goal: false`; absent goals never imply
completion. Both options can be repeated. The deadline also bounds checks.

## Recovery

The default store is `.jiti/default`. The launcher holds an OS writer lock, and
snapshot files are created with mode 0600. `/history` follows accepted ancestry.
`/rollback N` restores earlier accepted code/data by publishing another revision.
Recovery reads CURRENT and never replays unfinished actions. Corrupt snapshots
and incompatible OTP major releases prevent opening the store. Unpublished orphan files cannot
be selected as rollback targets.

The format is trusted local BEAM-term data with a version/checksum envelope.
It is separate from `.image-agent` SBCL stores; there is no import/migration.
File sync and atomic CURRENT rename are implemented; parent-directory syncing
and power-loss durability are not established. Direct bridge callers must provide
writer locking equivalent to the supported Python entry point.

## Operation diagnostics and function inspection

`/operations` shows 25 of the 100 most recent operation summaries. Each attempt
gets an identity before evaluation; repair, retry and abort retain that identity.
JSON records under the store's `operations/` directory contain hashes and lengths
of source, action names, timestamps, statuses and revision references. They omit
raw source, state, values and conditions. Older records remain on disk.

Recovery marks unfinished attempts interrupted and never replays them. If an
operation published an accepted revision before its final diagnostic update,
accepted ancestry reconciles that publication as committed. The recovered goal
result remains unknown. Live repair tokens are not recovered. Graceful quit/EOF
aborts a pending attempt; a corrupt published diagnostic fails opening the store.
These records are summaries, not an immutable trace of every repair step.

`/functions [OFFSET]` lists 50 name/arity entries per page, including bounded
arguments and documentation. `/describe NAME ARITY` displays normalized LFE
source and identifiable callers. Inspection uses provisional definitions during
repair and accepted definitions otherwise. Metadata follows managed preview,
abort, forget and rollback. Old snapshots without metadata reconstruct source
from their function bodies. Caller information is advisory: computed, remote and
higher-order calls may be absent. Native chat tools expose the same inspections.

## Local agents.erl bridge

The [bridge example](../examples/agents-bridge.lfe) was developed through the
actual chat terminal and saved at revision 2 of `.jiti/agents-bridge`. It connects
to `agents_jiti@127.0.0.1` and looks up `jiti-bridge-agent` through the remote
registry. `(agents-status)` returns selected agent state through two RPCs with
5-second deadlines. A fresh VM starts a unique local longname before connecting.
Managed state holds the remote node and agent ID; it never holds a PID.

The target must be running and use the same existing Erlang cookie. Start the
terminal with distribution bound to loopback:

```sh
ERL_EPMD_ADDRESS=127.0.0.1 \
ERL_FLAGS='-kernel inet_dist_use_interface {127,0,0,1}' \
python3 scripts/repl.py --lfe --store .jiti/agents-bridge --timeout-ms 12000
```

Only one terminal may own that store at a time. The saved function reconnects
after reopening; connections themselves are not persisted. It reads state and
does not enable autonomy or send chat tasks. Distribution and remote effects
remain outside managed rollback. This is a local status bridge, not a distributed
transaction or a full agents.erl application launch. See the
[live verification receipt](verification/lfe-bridge-verification-2026-10-06.md).

## Current boundaries

This is not a full port of the SBCL application. SBCL still provides live restart
dynamic extent, its world-adapter interface, autonomous evolution, context
compaction, terminal UI, experiments and launch
capture. The LFE experiment now has a session supervisor, explicit asynchronous
jobs, durable plan graphs and fenced remote actors. It has no replication or consensus.

Managed rollback covers immutable data placed through `state-put`/`state-delete`
and named definitions. PIDs, refs, ports and functions cannot be stored as managed
data. Files, messages, ETS, spawned processes and arbitrary Erlang effects remain
outside the checkpoint. Ordinary evaluator terminal output is discarded to keep
the JSON bridge intact. Process isolation and deadlines are not a security sandbox.

The existing optional `/mode chat` frontend uses native LFE tools through a
Responses endpoint. Actual LFE provider/tool use has been verified in the bridge
and farm experiments; the offline suite does not establish SBCL chat parity.
Credentials are removed from the evaluator environment;
never place secrets in source or managed data. Model credentials are unnecessary
for LFE evaluation and the offline tests; the explicit live smoke uses configured credentials.

## Verification and original conversion audit

`make test` exercises actual BEAM processes: arithmetic, function composition and
recursion, fresh-process recovery, preview discard, repair/abort, stale tokens,
safety/goal separation, timeout recovery, rollback ancestry, writer exclusion,
orphan handling, corruption rejection and piped multiline input. Three fixed
seeds generate 180 state-machine actions checked against an independent reference
model. Property failures are minimized and saved under `.image-agent/lfe-failures`.

The diagnostics suite additionally kills real BEAM processes during evaluation,
forces a final diagnostic rename failure after CURRENT publication, checks
reconciliation in a fresh process, and exercises catalogue metadata, callers,
pagination, permissions, record bounds, native tool dispatch and terminal commands.

The planning and farm suites verify real concurrent workers, ancestor/dependency
cycles, version fences, independent checks, manager failures, full local/remote VM
recovery, immutable tool grants and denied child-tool dispatch. Use `/plan ID` for
structured inspection. [Planning helpers](../examples/planning.lfe) were developed
by Jiti after it read the DSCO source and retained video design.

See [the live farm receipt](verification/lfe-farm-verification-2026-10-06.md) for the six tool
variants, fresh descendant comparison and seven-actor restart proof. The explicit
runner is `scripts/farm_rollouts.py`; it never schedules itself after recovery.

```sh
python3 tests/lfe_scenarios.py --replay .image-agent/lfe-failures/424242.json
make test-kernel     # devenv shell test: original SBCL kernel
python3 scripts/check-adrs.py
```

The original local conversion had no Makefile. Its `evaluate` function accepted
every nonempty string, never invoked the LFE evaluator and returned an empty
value. The bridge incremented counters without saving definitions or data; its
store module was unused. Arithmetic and invalid text both returned success, and
fresh processes always reopened at revision zero. Those behaviors were reproduced
before implementing this backend. The current tests distinguish these behaviors
from real evaluation and managed persistence.
