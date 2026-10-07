# Development workflow

This checkout publishes to `arthurcolle/jiti-lfe` through `fork`. `origin` points
to upstream `ghuntley/jiti`. The fork's default branch is
`goal-oriented-planning`; check current refs before publishing. Its launcher is
LFE by default; `--legacy` selects the retained SBCL frontend.

## Repository map

| Path | Purpose |
|---|---|
| `src/*.lfe` | LFE controller, managed evaluator/store, owned jobs, plans and workspace records. |
| `src/*.lisp`, `image-agent.asd` | Inherited SBCL kernel and world adapters. |
| `scripts/lfe_*.py` | LFE terminal, Responses transport and typed protocol adapters; workspace logic lives in LFE. |
| `scripts/legacy_repl.py` | SBCL terminal and chat frontend. |
| `tests/` | Offline, generated/property and explicit bounded live checks. |
| `docs/adr/` | Architectural choices and reciprocal supersession history. |
| `docs/verification/`, `docs/evidence/` | Retained verification reports and compact evidence exports. |
| `launch/` | Source assets for the historical SBCL demonstrations. |
| `.jiti/`, `.image-agent/` | Ignored local durable stores and live receipts. |
| `_build/` | Ignored pinned LFE checkout and compiled BEAM output. |

Build with `make build`, verify LFE with `make test`, and validate ADRs with
`python3 scripts/check-adrs.py`. Kernel changes also require `devenv shell test`;
Responses integration changes with configured credentials require
`devenv shell test-live`. If the development environment is absent, report that
gate as unavailable rather than calling the LFE checks SBCL verification.
Live scripts require explicit invocation, fresh output directories and configured
credentials. Their small runs establish execution, not sustained improvement.

Property failures must retain a minimized replayable trace. Keep credentials out
of code, state, events, test artifacts and ADRs. Workspace fixtures belong in
ignored temporary directories and must be removed after their run.

## Commits and publication

Use `dsco <agent@distributed.systems>` for both author and committer of automated
code changes. Per-command configuration sets the committer without changing a
machine-wide identity:

```sh
git -c user.name=dsco -c user.email=agent@distributed.systems commit \
  --author='dsco <agent@distributed.systems>' -m 'Describe the resulting behavior'
git show --no-patch --format=fuller HEAD
git push fork HEAD:goal-oriented-planning
```

Review the staged diff and the actual remote first; preserve unrelated local
work. Do not include `.swarm` transcripts, crash dumps, generated media, build
outputs or local stores. The 2026-10-06 cleanup archived the two formerly tracked
worker logs and the crash dump under `.jiti/cleanup-archive-20261006/`, with hashes
and sizes in its manifest. Historical source and verification evidence remain.

Follow [AGENTS.md](../AGENTS.md) and the
[ADR maintenance skill](../skills/maintain-adrs/SKILL.md) when architecture changes.
