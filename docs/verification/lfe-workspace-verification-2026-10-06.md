# LFE project workspace verification — 2026-10-06

The implemented workspace adds fourteen project tools to the 55 existing native
tools, alongside nine conversation-context tools. It stores selection, pins and
digest baselines in managed state and reads source through the native boundary.
The fork now defaults its launcher to LFE; explicit `--lfe` remains compatible
and SBCL is selected with `--legacy`.

## Observed offline behavior

[Actual BEAM scenarios](../../tests/lfe_workspace.py) exercise all fourteen tools:
project lifecycle, previews and stale revisions; source/path restrictions; actual
hashes and line evidence; native lexical code maps; scan/file/byte limits;
changed/added/removed files; immutable roots and baselines; changed pins; project
switching; rollback and fresh-VM recovery. Terminal workspace commands also run
without an HTTP request. Files containing an import-time exception are inspected
without execution.

[Launcher checks](../../tests/lfe_launcher.py) execute actual default and explicit
LFE evaluation and use dispatch probes for legacy argument forwarding and
conflicting selectors. These probes do not establish SBCL runtime correctness.
The complete `make test` result and unavailable development-environment gates are
recorded in the final validation below.

## Bounded real chat

The [live runner](../../tests/lfe_workspace_live.py) passed using `gpt-6-sol`, with
16 Responses requests and 14 tool calls against ceilings of 30 requests and 28 tool calls. No
background workers were admitted. The
[retained summary](../evidence/lfe-project-workspace-smoke-2026-10-06.json)
contains actual counts, tool names, source hashes and resulting comparisons.
Full native-run receipts are `.jiti/workspace-live-20261006-native-1/report.json`.
The earlier frontend prototype also passed a 16-request smoke; its local receipt
remains `.jiti/workspace-live-20261006-1/report.json`. That prototype was replaced
by native LFE operations before publication, per the user's request.

The model opened an actual fixture project, inspected its tree, symbols, search
hits and source lines, pinned implementation and contract, and saved a baseline.
The owner-side harness then changed `Engine.run(x)` from `x * 2` to `x * 3` and
added a file. A second normal chat turn observed the changed implementation,
unchanged `x * 2` contract, changed pin and added file. Independent checks of the
files and hashes agreed. A fresh VM recovered project selection, both pins and
the baseline; no jobs were replayed. Read-only tools never modified the sources.
The fixture was removed after the run; the managed store and receipts remain.

## Limits

This small source-inspection experiment establishes execution and recovery.
It does not establish autonomous repository repair, atomic filesystem snapshots,
complete semantic indexing, sandboxing or sustained farm improvement. Monetary
charges are unknown. The DSCO inspection root remains installation-specific.

## Final validation

`make test` passed after the native port: real BEAM scenarios, 180 generated
state-machine actions, catalogue/diagnostics and publication faults, native plans,
all 31 toolkit scenarios, all 14 workspace tools, actual launcher checks, display
and context suites, distributed actor recovery/fencing, farm rollouts and 28 ADRs.
All local Markdown link targets exist and `git diff --check` passed.

The first sandboxed full run reached distributed planning but failed because
Erlang's loopback listener was denied with `register/listen error: eperm`.
Rerunning with the local listener allowed passed, including a final full run after
the port. `devenv shell test` and `devenv shell test-live` were both attempted and
are unavailable (`command not found: devenv`); the SBCL gates remain unverified.
Native development briefly exposed an invalid regex capture option and corrected
it to the Erlang tuple form; the final source navigation checks and live smoke
passed. No property failure occurred; no minimized failure trace was needed.

Related: [workspace guide](../workspace.md), [contract review](../workspace-contract.md),
[ADR 0026](../adr/0026-managed-project-workspace.md),
[ADR 0027](../adr/0027-lfe-fork-default.md),
[native workspace ADR](../adr/0028-native-lfe-workspace.md).
