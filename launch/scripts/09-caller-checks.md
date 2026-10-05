# Who decides whether it works?

Runtime: 45 seconds. Formats: landscape, portrait.

Use actual capture evidence where listed. Always display its provenance. A diagram illustrates behavior; it is not a terminal recording.

## 000–015s — The caller defines success

Visual: The caller defines success

On screen: Known data → $54.50 spent / Budget $60.00 → $5.50 remains / Caller-owned acceptance contract

Caption: Recorded kernel execution; see provenance label.

Evidence: caller_checks

Narration: The caller supplies executable goals. For this ledger, the known expenses must total fifty-four dollars and fifty cents, and the sixty dollar report must leave five dollars and fifty cents. Model-written tests cannot replace that contract.

## 015–030s — Safety checks protect intermediate state

Visual: Safety checks protect intermediate state

On screen: Validate ledger entries / Reject invalid managed state / Restore the attempt checkpoint

Caption: Recorded kernel execution; see provenance label.

Evidence: safety_rejection

Narration: Safety invariants answer another question: is the managed ledger still valid? A bad amount or malformed entry must fail the caller check. When safety fails, the attempt is rejected and managed changes are restored.

## 030–045s — Safe progress can precede a finished feature

Visual: Safe progress can precede a finished feature

On screen: Goal false + safety passes / Useful intermediate revision / Goal passes → requested behavior

Caption: Recorded kernel execution; see provenance label.

Evidence: define_expense

Narration: A missing report can leave the goal false while a useful new helper is accepted. That allows incremental development. Goal predicates track completion; safety checks constrain every accepted step toward it. Inspect both in the demo evidence.
