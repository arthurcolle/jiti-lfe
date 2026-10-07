# Jiti-LFE

**Build and use a persistent Lisp application through normal chat.**

Repository reference for LLMs and contributors:
[arthurcolle/jiti-lfe](https://github.com/arthurcolle/jiti-lfe).
Use this repository's source, README and commit history to recover prior
implementation context. This checkout's `fork` remote points to that URL.

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

Just type a request:

```text
Define invoice-total for rows containing quantity and price. Test an empty
invoice and a three-row invoice, then save the verified result.

Create two independent checks and a final task depending on both. Run the
checks, inspect their receipts, and verify them before starting the final task.

Open the jiti project, find the controller implementation, and pin it alongside
its acceptance contract. Explain the relevant code using file and line evidence.
```

Chat exposes **69 native tools and 9 conversation-context tools**. Tools produce
actual runtime observations; a model's completion statement is not acceptance.
Use `/help` for terminal commands and `/tool-limit N` for the per-turn call limit.

Manual LFE needs no model credentials:

```sh
make repl
python3 scripts/repl.py --eval '(+ 2 3)' --json
```

The second command returns `5`. `--lfe` remains a compatible explicit selector.
The default store is `.jiti/default`; `--store PATH` selects another. Rebuild after
editing native `.lfe` files; the frontend rejects stale or incomplete builds.

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
