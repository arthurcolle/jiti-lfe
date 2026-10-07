# Repository instructions

This fork runs the LFE backend by default and retains the cooperative live SBCL
image-repair kernel behind `--legacy`. Preserve SBCL active restart dynamic
extent and worker ownership. LFE evaluates isolated actions and retries the whole
action after repair; never claim it preserves an unwound stack. Keep application behavior in LFE; Python is retained for existing client and
test scaffolding. Preserve managed
code/data rollback and the distinction between goal predicates and safety checks
in both backends.

When work introduces, changes, or supersedes an architectural decision, use
**$maintain-adrs** and read [its instructions](skills/maintain-adrs/SKILL.md).
Keep [ADRs](docs/adr/) consistent with implementation and verification. Each ADR
captures one decision and its rationale; supersede changed decisions instead of
rewriting historical choices.

Run `make test` for LFE changes, `devenv shell test` for kernel changes and
`python3 scripts/check-adrs.py` for ADR changes. Run `devenv shell test-live` when
modifying the Responses integration and local credentials are configured.
Property failures must produce a replayable minimized trace. Do not put
credentials in source, events, failure artifacts, or ADRs.

Use `dsco <agent@distributed.systems>` as both author and committer for automated
code commits. This checkout's `fork` remote is the owned `jiti-lfe` repository;
`origin` is upstream Jiti. Check branch and remote before publishing.

Keep generated stores, `.swarm` worker logs, crash dumps, build outputs and
disposable test fixtures out of Git. Retain concise verification reports in
[docs/verification](docs/verification/) and deliberate evidence exports in
[docs/evidence](docs/evidence/). Preserve legacy source and historical evidence.
