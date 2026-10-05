# Teach once, combine later

Runtime: 40 seconds. Formats: landscape, portrait.

Use actual capture evidence where listed. Always display its provenance. A diagram illustrates behavior; it is not a terminal recording.

## 000–010s — Start with functions you already have

Visual: Start with functions you already have

On screen: Coffee $4.50 / Groceries $32.00 / Transport $18.00

Caption: Recorded kernel execution; see provenance label.

Evidence: spending_total, category_totals

Narration: Our ledger already has three expenses. We have functions to record them, total them, and group spending by category.

## 010–020s — Ask for a budget report

Visual: Ask for a budget report

On screen: “Combine those into a budget report.” / total-expenses / spending-by-category

Caption: Explanatory diagram

Narration: Now ask for a sixty dollar budget report. The useful move is to compose the functions the application already knows.

## 020–030s — Ordinary function calls do the work

Visual: Ordinary function calls do the work

On screen: budget-report(6000) / Calls total-expenses / Calls spending-by-category

Caption: Recorded kernel execution; see provenance label.

Evidence: define_report, budget_report

Narration: Budget-report calls those existing functions and calculates the remainder. This composition becomes another named function you can inspect and call again.

## 030–040s — The application gains a vocabulary

Visual: The application gains a vocabulary

On screen: Budget $60.00 / Spent $54.50 / Remaining $5.50

Caption: Recorded kernel execution; see provenance label.

Evidence: budget_report

Narration: Fifty-four dollars and fifty cents spent. Five dollars and fifty cents left. Each new function becomes a building block for the next request.
