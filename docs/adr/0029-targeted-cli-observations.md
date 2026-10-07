# 0029: Targeted observations in the LFE developer interface

Status: Accepted
Date: 2026-10-06

## Context

Every bridge response contains a bounded printed copy of the entire managed state.
Showing it after each manual operation buries the operation's result. Repeating it
in every model tool result also consumes the chat working budget without providing
fresh evidence relevant to most operations. `goal=false` on an inspection response
does not mean the inspected application failed a goal or a safety check.

## Decision

Default terminal output to a concise operation receipt and bounded returned value.
Successful chat tools show one activity line; the assistant explains their actual
outcomes. Failures and pending repairs remain visible immediately.
Expose state key discovery and targeted reads through `/state`, alongside functions,
plans, jobs and notes inspection. Provide capability and contract counts on status;
show goal outcomes only for evaluated actions with configured goal predicates.
Keep `/details` local and raw, and preserve the bridge's existing `state`, `value`,
revision, token, operation ID and goal fields for JSON consumers.

Project model receipts by removing the repeated whole-state field and its duplicate
raw value when a native pretty view exists. Explicitly label omitted state and
bounded views. Preserve operation identity, pending tokens, reasons and typed tool
data. Render actual terms in LFE; the Python frontend does not parse or guess the
meaning of truncated printed terms. Printable integer lists use LFE string notation;
this is presentation, not a conversion of the stored value's type. Successful
evaluations also expose the existing native bounded JSON view when representable;
terminal/model consumers can use this typed field to show numeric arrays directly.

## Rationale

Increasing the chat limit would postpone repeated-state growth. Decoding printed
binary syntax in Python cannot recover elided contents or reliably determine the
application meaning of a list. Targeted existing native inspection tools reduce
both terminal noise and model input while retaining the owner and evaluator. A raw
mode remains useful for debugging and compatibility; making it the default imposed
that debugging burden on every developer interaction.

## Consequences

Chat must explicitly inspect application data it needs. A shortened display is
incomplete evidence and cannot certify success. Local automatic compaction remains
lossy and may refuse an oversized current prompt; it never resets the application
or replays actions. Jobs continue to separate saved receipts from current runtime
observations. Existing safety, publication, rollback and whole-action LFE repair
semantics are unchanged. The inherited SBCL interface and live restart ownership
remain governed by their existing decisions.

Related: [structured SBCL terminal](0011-structured-terminal-frontend.md),
[typed toolkit](0024-typed-managed-toolkit.md), [LFE default](0027-lfe-fork-default.md).

Implementation: [frontend](../../scripts/lfe_repl.py),
[bridge](../../src/jiti_bridge.lfe), [native value view](../../src/jiti_toolkit.lfe).
Verification: [real developer workflows and receipt fidelity](../../tests/lfe_display_test.py),
[context compaction](../../tests/test_lfe_chat_compaction.py).
