# Typed LFE toolkit verification

Review date: 2026-10-06. This records execution evidence for the added toolkit,
not evidence of population improvement or a complete farm behavioral loop.

The chat catalogue now contains 55 native LFE tools plus 9 conversation-context
tools. This change adds 31 native tools. The actual BEAM scenarios in
[`tests/lfe_toolkit.py`](../../tests/lfe_toolkit.py) invoke every addition and check
managed state, function results, job ownership, atomic failure and fresh-VM recovery.
The full `make test` includes these scenarios, the prior kernel/planning/farm
scenarios and the frontend context/display contracts. ADR validation passes with
25 records. The original `devenv shell test` and `devenv shell test-live` commands
were attempted and cannot run because `devenv` is not installed on this machine;
these SBCL gates remain unverified.

## Bounded real model workflow

[`tests/lfe_toolkit_live.py`](../../tests/lfe_toolkit_live.py) uses real Responses
requests, capped at 24 requests and 22 model tool calls, with at most one owned
job for this workflow. The owner supplies the exact function body, test cases,
state key, job expression and note contents. Separate harness inspections check
actual state, parsed source equality and job receipts; model prose is not evidence.

The second fresh run, `.jiti/toolkit-live-20261006-2/report.json`, passed using
`gpt-6.1-sol`. It made 11 Responses requests and 10 tool calls:

`tools_list → function_define → function_test → function_call → state_put →
state_get → job_start → job_wait → note_put → note_get`.

Both invoice cases returned their expected totals (100 and 0), the actual call
returned 100, and the stored binary-key value read back as 100. Exactly one named
job was admitted and settled with public result `#(ok 100)`. The exact requested
function was checked by comparing parsed forms rather than printed notation.
The note and state persisted at revision 5. Fresh-VM recovery retained the job's
recorded success while current observation was unknown, and the runtime owned
zero replacement jobs. The smoke establishes use/recovery of ten additions;
offline actual-runtime scenarios cover all 31.

The first run, `.jiti/toolkit-live-20261006-1/report.json`, also completed the model's
ten operations but its harness failed before recovery because it expected `#B(...)`
in normalized function source. The pinned LFE pretty printer uses equivalent
`#"..."` notation. The harness was corrected to compare parsed forms, and the
second run used a fresh store. The first failure report is preserved.

Model usage receipts are retained in the local reports. They are token usage,
not confirmed monetary charges; monetary charges are unknown. Test reports and
stores are ignored local evidence, not checked-in credentials or production data.

## Boundaries tested

Stale increments cannot apply twice; compare/set mismatch makes no revision.
Patches failing after an earlier write restore the whole candidate. Previews and
test mutations leave committed code/data unchanged. Unknown atom reads leave the
warmed VM atom count unchanged. Function source pagination preserves complete
normalized forms. Identifiable callers are retained during forgetting.

Named launches deduplicate in the owner manager even after safety rejection or
managed rollback. Different content conflicts. Accepted receipts prevent replay
after VM loss; unknown handles cannot stop replacement work and unknown observation
does not erase a recorded terminal result. This does not establish durable
exactly-once unmanaged effects before receipt publication.

Discovery and dispatch respect advertised tools. Workspace tests reject traversal,
absolute and hidden paths, reconstruct UTF-8 split across read chunks, and continue
after capped matches. Notes and workspace text remain data rather than authority.
The [contract review](../lfe-toolkit-contract.md) lists bounds, adversarial cases and
compatibility. [ADR 0024](../adr/0024-typed-managed-toolkit.md) records the adapter
decision; [ADR 0025](../adr/0025-named-job-admission-fencing.md) records owner fencing.
