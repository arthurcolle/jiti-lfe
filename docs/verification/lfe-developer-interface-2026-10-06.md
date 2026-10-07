# LFE developer interface verification, 2026-10-06

The developer interface now defaults to concise results and targeted inspection.
Chat prints successful tool activity separately from its explanation, and projects
tool receipts without the repeated whole-state dump. Raw bridge fields remain
available through `/details` and `--json`. Decision: [ADR 0029](../adr/0029-targeted-cli-observations.md).

## Offline and runtime evidence

- `make test` passed: real LFE scenarios and 180 generated state-machine actions,
  catalogue/operation crash diagnostics, native plans, all 31 added toolkit tools,
  all 14 project workspace tools, launcher routing, runnable examples, tool limits,
  display workflows, context compaction, hierarchical planning and empirical farm
  scenarios. The working tree also contains concurrent dispatch/UI/example work;
  this report does not attribute those changes to the interface patch.
- `tests/lfe_display_test.py` passed 15 tests. Real BEAM workflows cover targeted
  inspection without revision changes, `/exit`, fresh-process recovery, actual
  launcher pause/repair/retry, receipt fidelity, escaped terminal controls, raw JSON,
  local `/details`, and bounded native views of printable and nonprintable binaries.
  An improper-list return remains printable without breaking a successful action.
- 100 real read-only status tool exchanges against a state containing a 100,000
  character list retained all receipts and kept serialized chat context below
  100 KiB. Provider replies in this test are deterministic offline fixtures.
- `python3 scripts/check-adrs.py` passed for 31 ADRs in the final working tree;
  `git diff --check` passed.

## Live chat evidence

Two bounded real Responses runs used disposable stores containing the supplied
diagnosis shape: `x` expected/observed false, `y` expected true with unknown status,
and unresolved `y`. Each run made two provider requests and one native `state_get`
call, with a ceiling of six requests and four calls. Independent bridge inspection
confirmed the revision stayed at 1. Model receipts omitted whole state.

The final run used 8,521 serialized context bytes. Terminal output showed one
`state_get | ok | rev 1` activity line, followed by an explanation that the diagnosis
was blocked, `x` was satisfied, and `y` needed an observed value. It also identified
the practical limit: the stored diagnosis did not define what `y` represents or how
to check it. No model response was treated as evidence that `y` had been resolved.

## Integrated dynamic execution and terminal editor

The final `make test` passed with native multimethod/closure/remote-call scenarios,
hot replacement, ambiguity rejection, preview, rollback and fresh-process recovery.
ADRs 0030 and 0031 record dynamic execution and optional terminal presentation.
Real PTY input checked multiline submission, mode switching, the model/status bar,
Markdown code, quiet activity and local receipt browsing. Rich rendering also
preserved complete receipts and kept failed checks visible.

Two additional live turns pinned `gpt-6-sol`, each with a four-tool ceiling, made
four provider requests and two executed tools total. The first replaced pricing
and invoked Erlang `abs` through a saved composed pipeline. Its Unicode pretty
view exposed the numeric-list presentation problem. After adding the native typed
JSON view, the second displayed `[625,275,325]`; reopening independently recovered
that result at revision 2. These receipts establish execution, not billing or
population improvement. Native desktop inspection was unavailable because its
automation pipe failed; terminal rendering was verified through the actual PTY.

## Limits

`devenv shell test` and `devenv shell test-live` were attempted but could not run:
`devenv` is not installed/on PATH. No SBCL gate is claimed. Live chat was checked
through the actual LFE frontend and local configured provider instead.

Pretty views and archive excerpts remain bounded; compaction is lossy and can
refuse an oversized current prompt. Removing duplicate state does not establish a
provider's maximum context window. Targeted reads preserve native atom/binary key
types; internal tuple keys use their own interfaces. LFE repair continues to retry
the whole action after repair, with managed rollback, rather than preserve an
unwound call stack.
