# Your first function

Runtime: 30 seconds. Formats: landscape, portrait.

Use actual capture evidence where listed. Always display its provenance. A diagram illustrates behavior; it is not a terminal recording.

## 000–010s — No expense functions yet

Visual: No expense functions yet

On screen: Empty ledger / Empty expense catalogue / “Let me record an expense.”

Caption: Recorded kernel execution; see provenance label.

Evidence: empty_catalogue

Narration: This application starts with an empty managed ledger. Inspect its catalogue: there are no expense functions yet. Now ask for the first one.

## 010–020s — A request adds a real Lisp function

Visual: A request adds a real Lisp function

On screen: add-expense(amount, category) / Real Lisp definition / Source available in the catalogue

Caption: Recorded kernel execution; see provenance label.

Evidence: define_expense

Narration: The development tool adds add-expense. Its amount is measured in integer cents, and its second argument names the category. Inspect the definition.

## 020–030s — Use it immediately

Visual: Use it immediately

On screen: (add-expense 450 :coffee) / Coffee: $4.50 / Ask for the next capability

Caption: Recorded kernel execution; see provenance label.

Evidence: record_expense

Narration: Call it with four hundred fifty cents and coffee. The ledger changes. You have added the first reusable capability to a running application.
