# Grow an app by talking to it

Runtime: 90 seconds. Formats: landscape.

Use actual capture evidence where listed. Always display its provenance. A diagram illustrates behavior; it is not a terminal recording.

## 000–010s — Start with an empty application catalogue

Visual: Start with an empty application catalogue

On screen: A running Lisp kernel / An empty managed ledger / No expense functions

Caption: The runtime and caller checks already exist.

Evidence: empty_catalogue

Narration: This is Jiti: a running Lisp application you can grow through conversation. Our expense ledger begins empty. There are no expense functions yet.

## 010–022s — Teach it to record an expense

Visual: Teach it to record an expense

On screen: “Let me record an expense.” / (add-expense 450 :coffee) / Amounts use integer cents

Caption: Recorded kernel execution; see provenance label.

Evidence: define_expense, record_expense

Narration: Ask it to record expenses. The controller adds a real Lisp function. Call it with four hundred fifty cents and the coffee category. The ledger now contains that entry.

## 022–035s — Add the next useful capability

Visual: Add the next useful capability

On screen: Coffee $4.50 / Groceries $32.00 · Transport $18.00 / Total $54.50

Caption: Recorded kernel execution; see provenance label.

Evidence: spending_total

Narration: Next, ask for total spending. Add groceries and transport, then call the new function. Four fifty, thirty-two dollars, and eighteen dollars become fifty-four dollars and fifty cents.

## 035–047s — Reuse what the application has learned

Visual: Reuse what the application has learned

On screen: Category totals / Budget $60.00 / Spent $54.50 · Remaining $5.50

Caption: Recorded kernel execution; see provenance label.

Evidence: category_totals, budget_report

Narration: Ask for spending by category, then a budget report. That report calls the functions already in the image. With a sixty dollar budget, five dollars and fifty cents remain.

## 047–062s — Try a change, then undo an accepted change

Visual: Try a change, then undo an accepted change

On screen: Preview → inspect → restore / Accept → publish revision / Rollback → new revision

Caption: Recorded kernel execution; see provenance label.

Evidence: preview_restore, rollback_history

Narration: Preview an extra expense and inspect its result. The managed ledger is restored afterward. Accept a change instead, and it becomes a revision. Rollback restores earlier code and data while preserving history.

## 062–077s — Repair a call while it is paused

Visual: Repair a call while it is paused

On screen: Same operation / Original frame resumes / Next call uses new definition

Caption: Recorded kernel execution; see provenance label.

Evidence: paused_call, repair_resume, subsequent_call

Narration: A report pauses on an unsupported category. Repair its helper and resume through the live restart. The original call keeps its existing frame. A later invocation uses the new report definition.

## 077–090s — Reopen it. Keep the application you built.

Visual: Reopen it. Keep the application you built.

On screen: Accepted code + managed data recover / Active stacks stay in the live process / Run Jiti · inspect the source

Caption: Recorded kernel execution; see provenance label.

Evidence: fresh_recovery

Narration: Restart the process. Accepted functions and ledger data recover together. Jiti combines conversation with Lisp development, live repair, and managed history. Inspect the source, run the demo, and build the next capability.
