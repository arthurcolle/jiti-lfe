# 0013: Conversation compaction independent of worker state

Status: Accepted
Date: 2026-10-05

## Context

The interactive controller originally discarded history after 65,536 serialized characters, sometimes stopping an unfinished tool loop. Instructions also repeated the latest tool payload. The worker retained its world and suspended restarts, but the model lost user intent and unfinished work. The configured gateway may not implement native OpenAI context endpoints.

## Decision

Manage a token-budgeted conversation in the chat controller, independent of the kernel's managed world and worker. Compact automatically at complete call/result boundaries and continue the current prompt with unchanged tool counters and call identity tracking. Prefer native stateless compaction, retaining its canonical output intact; on explicit incompatibility, use a bounded tool-free summary retaining the latest user prompt and two recent complete exchanges. Publish replacement context only after validating pairing, prompt retention, and sufficient size reduction. Keep conversation memory session-only.

## Rationale

Increasing the character limit only postpones history growth and misses instruction/tool overhead. Resetting the worker would lose active restart dynamic extent. Native compaction carries opaque model state, while an ordinary Responses summary supports gateways with only the existing endpoint. Keeping both behind the injected chat transport preserves the generic world/session interface and deterministic offline verification. Summaries can lose detail, so they cannot replace fresh worker state, caller-owned checks, or actual tool results.

## Consequences

Compaction adds model usage and latency but spends no worker actions and does not mutate revisions, checkpoints, or restart menus. The configured working window reserves response headroom and includes instructions and tools; it is not discovery of the model's maximum window. Near the threshold, exact input counting is attempted when supported, with a byte-aware, usage-calibrated estimate otherwise. Instructions carry a lean current-state projection rather than duplicated tool output. Failed or ineffective compaction preserves the transcript; confirmed provider overflow permits one compact-and-retry attempt. `/compact`, `/context`, and explicit `/context clear` expose control and statistics in both terminal interfaces. Model switching still clears conversation memory. Response envelopes and tool arguments retain separate bounded parsers. Credentials, provider error bodies, and opaque compaction content are excluded from status events and failure artifacts.

Related: [interactive control](0006-interactive-tool-control.md), [worker ownership](0001-worker-owned-live-repair.md), [structured terminal](0011-structured-terminal-frontend.md).

Implementation: [context controller](../../src/context.lisp), [chat loop](../../src/chat.lisp), [REPL](../../src/cli.lisp), [terminal frontend](../../scripts/terminal_ui.py). Verification: [context protocol, minimized history replay, and live memory tests](../../tests/context-suite.lisp), [terminal scenarios](../../tests/terminal_scenarios.py).
