# What actually happens when you ask?

Runtime: 120 seconds. Formats: landscape.

Use actual capture evidence where listed. Always display its provenance. A diagram illustrates behavior; it is not a terminal recording.

## 000–015s — A request becomes a concrete operation

Visual: A request becomes a concrete operation

On screen: Your request / Controller + registered tools / Owning worker / Application

Caption: Explanatory diagram

Narration: You type: let me record an expense with an amount and category. The model sees the application catalogue and the tools available to it. A request can become development, execution, or inspection.

## 015–030s — The application starts with a small contract

Visual: The application starts with a small contract

On screen: Empty ledger / Integer cents / Caller-owned checks / No expense functions

Caption: Recorded kernel execution; see provenance label.

Evidence: empty_catalogue

Narration: Our example starts with a ledger and caller-owned checks. Amounts are integer cents. Categories describe each entry. Expense functions are absent, so the first request really adds a capability to this application.

## 030–045s — A definition becomes a reusable function

Visual: A definition becomes a reusable function

On screen: Develop a definition / Check the result / Publish accepted changes / Inspect function source

Caption: Recorded kernel execution; see provenance label.

Evidence: define_expense

Narration: The controller submits a Lisp definition through the development tool. The worker evaluates it inside the application. Once accepted, the function appears in the catalogue, with its arguments, documentation, and source available for inspection.

## 045–060s — Calling the function changes managed state

Visual: Calling the function changes managed state

On screen: (add-expense 450 :coffee) / Ledger: coffee, 450 cents / Accepted data change → revision

Caption: Recorded kernel execution; see provenance label.

Evidence: record_expense

Narration: Now call add-expense with four hundred fifty cents and coffee. The worker updates the managed ledger. This is an execution of a real function. Its accepted state can be stored and recovered later.

## 060–075s — Read the accumulated application state

Visual: Read the accumulated application state

On screen: 450 + 3200 + 1800 / 5450 cents / Pure reads need no new revision

Caption: Recorded kernel execution; see provenance label.

Evidence: spending_total

Narration: Add groceries and transport, then ask for a total. The new total-expenses function reads the same ledger. The result is five thousand four hundred fifty cents: fifty-four dollars and fifty cents.

## 075–090s — Compose ordinary Lisp functions

Visual: Compose ordinary Lisp functions

On screen: budget-report / total-expenses / spending-by-category / Existing ledger

Caption: Recorded kernel execution; see provenance label.

Evidence: budget_report

Narration: A budget report can call total-expenses and spending-by-category. It does not need another special pipeline language. The application grows a vocabulary of useful functions that you, or the conversational controller, can reuse.

## 090–105s — Make the machinery inspectable

Visual: Make the machinery inspectable

On screen: /functions · /describe / /operations: attempts / /history: accepted revisions

Caption: Explanatory diagram

Narration: Inspect the catalogue, read a function, and review operation history. Operations record attempts; revisions identify accepted code or data changes. An unsuccessful attempt can be useful evidence without becoming a new application version.

## 105–120s — Keep accepted work across sessions

Visual: Keep accepted work across sessions

On screen: Same workspace / Recovered definitions / Recovered ledger / New process and call stacks

Caption: Recorded kernel execution; see provenance label.

Evidence: fresh_recovery

Narration: Closing the process ends its active calls. Reopening the same workspace recovers accepted managed code and data. Conversation memory has its own lifetime. The useful artifact you have built is the evolving Lisp application.
