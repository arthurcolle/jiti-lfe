# Jiti-LFE

**Build and use a persistent Lisp application through normal chat.**

This fork runs LFE on Erlang/OTP by default. Chat can define and test functions,
manage data, run owned background jobs, build dependency plans, and inspect a
saved project workspace. Accepted code, data, notes, project pins and source
baselines recover from the same store after restarting.

The inherited [SBCL backend](docs/sbcl.md) remains available with `--legacy`.
Its live restart semantics differ from LFE's whole-action retry.

## Start chatting

Requires Erlang/OTP 27+, Python 3, Git, Make and Bash. Verified with OTP 29.
The build fetches and verifies pinned LFE 2.2.2, then compiles the native modules.

```sh
git clone https://github.com/arthurcolle/jiti-lfe.git
cd jiti-lfe
make build
export OPENAI_MODEL='your-model-id'
export OPENAI_API_KEY_FILE='/absolute/path/to/api-key'
make chat
```

`OPENAI_API_KEY` also works. `OPENAI_BASE_URL` can select a Responses-compatible
service; explicit settings take precedence over discovered local configuration.
`--model NAME` overrides model selection. Keep credentials outside this repo.

Chat exposes **69 native tools and 9 conversation-context tools**. Tools produce
actual runtime observations; a model's completion statement is not acceptance.
Use `/help` for terminal commands and `/tool-limit N` for the per-turn call limit.

`make chat` installs the optional terminal editor into `.jiti/ui-venv`: formatted
Markdown/code, multiline input, Tab command completion, Ctrl+R history and a live
session bar. Tools stay quiet; `/activity` and `/details N` open their receipts.
Use `/view verbose` for more output and `/model NAME` to change subsequent requests.
`--plain` and `--json` keep the dependency-free automation interface.

## Dynamic execution

Build new capabilities in the live image: overloaded functions, multimethods,
partial application, composition, map and fold, including dynamic Erlang calls
such as `(map-call (tuple 'remote 'erlang 'abs) '(-3 4 -5))`.
Stored named pipelines resolve
the current implementation on every call, including after repair or restart.

```lisp
(defun double (x) (* x 2))
(defun plus (a b) (+ a b))
(method-put 'transform '(number) 'double)
(state-put 'pipeline
  (compose (list (tuple 'dispatch 'transform) (partial 'plus '(10)))))
(map-call (state-get 'pipeline) '(2 3 4)) ; (14 16 18)
```

Tuple tags and JSON map type tags support domain-specific dispatch. Overlapping
signatures must have a unique most specific match. Try the
[polymorphic pricing example](examples/dynamic-dispatch.lfe); temporary lambdas
can execute too, while durable state stores named descriptors.

Manual LFE needs no model credentials:

```sh
make repl
python3 scripts/repl.py --eval '(+ 2 3)' --json
```

The second command returns `5`. `--lfe` remains a compatible explicit selector.
The default store is `.jiti/default`; `--store PATH` selects another. Rebuild after
editing native `.lfe` files; the frontend rejects stale or incomplete builds.

## Examples built for this fork

These are runnable LFE programs with fixed acceptance checks, not sample
conversations claiming a model did the work. Run them without credentials:

```sh
make examples
```

The runner creates temporary stores, executes the programs, checks recovery in
fresh processes and removes its temporary data. See the
[example guide](examples/README.md) to load them into your own persistent store.

| Example | What it does | Checked result |
|---|---|---|
| [Invoice audit](examples/invoice-audit.lfe) | Validate line items, count each valid ID once and report rejected rows. | 32,400 cents; three accepted lines, one duplicate and one invalid line. |
| [Release gate](examples/release-gate.lfe) | Launch two independent checks, inspect their receipts, then verify them before admitting the dependent release task. | Three verified tasks; fixture p95 is 100 ms; restart launches no replacement jobs. |
| [Reservation repair](examples/reservation-repair.lfe) | Diagnose missing pricing after a provisional stock edit, repair and retry the whole action, then preview another reservation. | Stock goes from 20 to 16 once; price is 6,000 cents; preview changes are discarded. |
| [Dynamic dispatch](examples/dynamic-dispatch.lfe) | Price heterogeneous inputs through multimethods, compose a fee, and fold the result. | 925 cents; stored descriptors follow live function replacement. |

For chat, give it a concrete contract:

```text
Build an invoice audit using JSON-compatible rows with id, qty and unit_cents.
Require positive integer quantities and nonnegative integer prices. Count each
valid ID once. Use the five rows in examples/invoice-audit.lfe as fixtures:
32,400 cents, three accepted lines, duplicate A-101 and invalid A-103. Test an
empty invoice and a fractional price too. Save the report and show the receipts.
```

```text
Create a release plan with independent receipt-schema and p95 checks, followed
by a release decision that depends on both. Use examples/release-gate.lfe's
fixed fixtures and acceptance checks. Launch both checks before waiting. Show
that successful execution alone does not admit the release task; verify the
checks, then run the dependent task. This should produce a local decision only.
```

```text
Use examples/reservation-repair.lfe to define an inventory reservation with
20 units. Try reserving four while pricing is missing. Inspect the failure,
define pricing at 1,500 cents per unit, and retry the failed action. Verify
stock is 16 and the price is 6,000 cents. Preview two more units and show that
the accepted stock and price stay unchanged.
```

The invoice and duration records are synthetic fixtures. The release example
produces a local decision; it does not deploy software. Its p95 is a calculation
over supplied data, not a runtime performance measurement.

## A project workspace that survives restart

The selected project, pins and digest baselines are managed state. Source is read
fresh, with hashes, line numbers and explicit coverage limits.

```text
/workspace open jiti jiti
/workspace tree src
/workspace pin src/jiti_kernel.lfe "Kernel implementation"
/workspace pin docs/lfe-conversion.md "Behavior contract"
/workspace symbols jiti
/workspace snapshot before
/workspace context kernel
/workspace diff before
```

Project roots are relative to the native inspection root, currently
`/Users/arthurcolle/Dsco` for this installation. The example's second `jiti` names
that directory. This root is independent of the managed store and is currently
installation-specific. Hidden paths, symlinks and unsupported file types are
excluded. Workspace tools inspect source and save metadata; they do not edit or
execute project files. See the [workspace guide](docs/workspace.md) for all 14
project tools, limits and the difference between a digest baseline and a backup.

`/functions`, `/describe NAME ARITY`, `/plans`, `/plan ID`, `/operations` and
`/history` inspect the actual application, jobs, diagnostics and revisions.

## Managed evaluation and repair

A controller owns accepted code and data. Each action evaluates provisionally in
a bounded monitored process. Safety checks can reject an attempt; unmet goal
predicates allow safe intermediate progress. Managed mutations use revision
fences and can be previewed. Rollback publishes an earlier managed state as a new
revision, preserving history.

LFE errors unwind evaluation. Repair edits remain provisional until retry of the
whole failed action succeeds; abort discards the attempt. LFE does not preserve an
active SBCL restart stack. External I/O and arbitrary Erlang effects are outside
managed rollback. Recorded job results and current process observations are
separate; recovery never automatically replays work.

## Verify and develop

```sh
make test
python3 scripts/check-adrs.py
```

Offline checks exercise real BEAM processes, typed contracts, recovery, planning,
workspace limits and generated state-machine traces. With configured credentials,
the bounded project-workspace smoke can run explicitly:

```sh
python3 tests/lfe_workspace_live.py --output .jiti/workspace-live-NEW
```

It caps 30 model requests and 28 tool calls, admits no background workers, and
checks observed source changes plus recovery. Use a fresh output directory.
[Verification reports](docs/verification/README.md) distinguish offline results,
real model runs and known limits. Small farm trials remain experimental evidence;
this is not a demonstrated self-improving population.

Read the [backend guide](docs/lfe-conversion.md), [workspace guide](docs/workspace.md),
[planning experiments](docs/goap.md), [development workflow](docs/development.md)
and [architectural decisions](docs/adr/). Generated stores, worker transcripts,
crash dumps and build outputs stay local. Retained reports and compact evidence
have their own folders under `docs/`.

## Origin

Jiti-LFE builds on [Geoffrey Huntley's original Jiti](https://github.com/ghuntley/jiti).
LLMs and contributors can consult that repository's source, README and commit
history for the original SBCL kernel and design context. This fork's examples
above exercise its LFE runtime and whole-action repair semantics.

This fork is [arthurcolle/jiti-lfe](https://github.com/arthurcolle/jiti-lfe).
The `origin` remote points to `ghuntley/jiti`; `fork` points to `arthurcolle/jiti-lfe`.
