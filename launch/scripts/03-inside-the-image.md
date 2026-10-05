# Inside the running Lisp image

Runtime: 240 seconds. Formats: landscape.

Use actual capture evidence where listed. Always display its provenance. A diagram illustrates behavior; it is not a terminal recording.

## 000–020s — A controller outside, a worker inside

Visual: A controller outside, a worker inside

On screen: External controller / Registered action protocol / Owning SBCL worker / Managed application world

Caption: Explanatory diagram

Narration: Jiti is a cooperative live image repair kernel for SBCL. An external controller proposes actions. One owning worker evaluates application forms and retains live restarts when a condition pauses an attempt. This separation lets the controller inspect and repair a call without moving its restart to another thread.

## 020–040s — The world adapter defines what is managed

Visual: The world adapter defines what is managed

On screen: Evaluation + observation / Checkpoint + restore / Function catalogue / Durable export + import

Caption: Explanatory diagram

Narration: An application supplies a world adapter: an evaluation package, observations, checkpoints, restoration, and a catalogue. Durable export and import make managed state recoverable. The reference adapter covers readable table values and supported named function definitions. An application with other resources needs corresponding adapter coverage.

## 040–060s — A small foundation, then incremental definitions

Visual: A small foundation, then incremental definitions

On screen: Empty catalogue / add-expense → total-expenses / spending-by-category → budget-report / Source remains inspectable

Caption: Recorded kernel execution; see provenance label.

Evidence: empty_catalogue, budget_report

Narration: The expense example starts with an empty ledger and executable caller checks. It has no expense functions. Development adds add-expense, total-expenses, spending-by-category, and budget-report in stages. The source is inspectable, and each accepted definition becomes available to later calls.

## 060–080s — Goals and safety answer different questions

Visual: Goals and safety answer different questions

On screen: Goal: does the report work? / Safety: is the ledger valid? / False goal → may keep safe progress / Failed safety check → restore

Caption: Recorded kernel execution; see provenance label.

Evidence: caller_checks, safety_rejection

Narration: A goal asks whether we have reached the desired behavior. A safety invariant asks whether an intermediate state is acceptable. A false goal can coexist with an accepted development step. A false or signaled invariant rejects the attempt and restores its managed checkpoint. The caller owns both contracts.

## 080–100s — One provisional checkpoint covers the attempt

Visual: One provisional checkpoint covers the attempt

On screen: Checkpoint / Evaluate → pause → repair / Check accepted result / Commit or restore

Caption: Explanatory diagram

Narration: The worker checkpoints managed state before reading, compiling, and evaluating a form. Repairs performed while that attempt is paused share its provisional checkpoint. If repair evaluation fails, the entire attempt is aborted. This makes code changes and data changes participate in the same managed rollback boundary.

## 100–120s — Operations, revisions, and generations differ

Visual: Operations, revisions, and generations differ

On screen: Operation: one attempt / Revision: accepted managed state / Generation: coordination guard / Pure result ≠ new revision

Caption: Explanatory diagram

Narration: Each attempt has an operation identity for diagnostics. A revision identifies accepted managed code or data. Pure calls and final-state no-ops do not create revisions. Observation generations coordinate worker actions and reject stale commands. These identifiers serve different purposes, even when one interaction displays all three.

## 120–140s — Preview restores managed code and data

Visual: Preview restores managed code and data

On screen: Preview an added expense / Observe temporary result / Restore managed state / External effects need separate handling

Caption: Recorded kernel execution; see provenance label.

Evidence: preview_restore

Narration: Preview evaluates an operation and returns bounded printable results, then restores the checkpoint. Its restoration also covers repairs made during a pause. Ordinary execution can retain safe changes instead. Preview only covers managed effects; an adapter cannot retract an email or network request simply by restoring its ledger.

## 140–160s — Rollback publishes a new point in history

Visual: Rollback publishes a new point in history

On screen: Accepted revision A / Accepted revision B / Rollback creates revision C / C restores A; history remains

Caption: Recorded kernel execution; see provenance label.

Evidence: rollback_history

Narration: After a change is accepted, rollback can restore an older managed revision. It publishes a new revision rather than erasing the intervening history. This is different from preview, which does not retain the temporary change. Rollback restores application code and data, not a historical call stack.

## 160–180s — A condition exposes live restart choices

Visual: A condition exposes live restart choices

On screen: Unsupported :transport category / Live restart choices / Original marker: v1-active-frame / Report entry count: 1

Caption: Recorded kernel execution; see provenance label.

Evidence: paused_call

Narration: Here a report encounters a category its label helper cannot handle. The worker pauses inside the active call and exposes restart choices. The operation identity remains the same. Its local marker and entry counter give us concrete evidence about which frame continues when we repair and resume.

## 180–200s — Resume the original frame after repairing a helper

Visual: Resume the original frame after repairing a helper

On screen: Repair helper and report definition / Resume → v1-active-frame, count 1 / Next call → v2-new-frame, count 2

Caption: Recorded kernel execution; see provenance label.

Evidence: repair_resume, subsequent_call

Narration: We replace the category helper and also define a new report body. Resuming through the live restart completes the existing invocation with its original frame marker. A subsequent report call enters the new body and increments the counter again. Global dispatch can see new helpers; existing frames retain their bodies.

## 200–220s — Durable recovery starts a fresh process

Visual: Durable recovery starts a fresh process

On screen: Immutable accepted artifacts / New SBCL process / Import definitions + ledger / No replay of old operations

Caption: Recorded kernel execution; see provenance label.

Evidence: fresh_recovery

Narration: Persistence records immutable world artifacts and a current revision pointer. Recovery imports the accepted revision into a fresh process. It does not replay old actions or recreate suspended stacks. Unfinished operations become interrupted diagnostics. The recovered expense functions still read the recovered ledger and produce the same totals.

## 220–240s — An inspectable experiment in live development

Visual: An inspectable experiment in live development

On screen: Cooperative SBCL application / Complete adapter coverage matters / Inspect code, operations, and checks / Try the reproducible demo

Caption: Explanatory diagram

Narration: The kernel relies on cooperative application code and accurate world adapters. Arbitrary hostile Lisp and unmanaged resources are beyond its guarantees. What the demo makes concrete is incremental development with caller-owned checks, accepted history, and a live repair path. Run it, inspect its evidence, and adapt the world to your application.
