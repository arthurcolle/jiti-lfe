---
name: maintain-adrs
description: Maintain this repository's Architectural Decision Records when implementation introduces, changes, or supersedes an architectural decision, keeping each ADR focused on one decision and its rationale.
---

Maintain ADRs in `docs/adr/`. Read `AGENTS.md`, the relevant records, and implementation or verification evidence before writing. Keep ADR changes with the implementation changes they explain.

Each ADR captures **one architectural decision and its rationale**. Use a stable numbered filename and include title, status, date, context, decision, rationale (meaningful alternatives and tradeoffs), consequences, and links to implementation, tests, and related decisions. An ADR records why a choice was made, not a work log or implementation inventory.

Choose the update based on the actual change:

- A routine fix implementing an existing decision needs no new ADR. Correct an obsolete implementation link or inaccurate consequence when necessary.
- Clarifying facts, documenting a demonstrated limitation, or correcting a consequence can update an existing record. Preserve its original decision and historical rationale.
- A materially different decision needs a new record. Mark the prior record `Superseded`, add its `Superseded by:` link, and add the reciprocal `Supersedes:` link in the new record. Never silently rewrite an accepted choice to make history resemble the present.
- A decision not yet accepted is `Proposed`. Distinguish intended behavior from implemented behavior and known gaps. Do not claim tests or implementations exist without evidence.

Allocate the next unused numeric ID. Split unrelated decisions into separate records. Explain actual alternatives considered; never invent reasons or alternatives to fill a template. Keep the record concise.

After updating, run `python3 scripts/check-adrs.py`. Review the changed records against the actual implementation and test results: structural validation cannot establish that their rationale is truthful. Mention relevant ADR changes in the implementation report.

Examples of classification: fixing stale restart-ID rejection follows the live-repair ADR; documenting that cached function objects retain old code updates that ADR's consequences; moving restart execution to another process requires a new decision with reciprocal supersession links.
