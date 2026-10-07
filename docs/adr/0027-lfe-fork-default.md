# 0027: LFE as the fork default

Status: Accepted
Date: 2026-10-06
Supersedes: [0015: Isolated experimental LFE evaluation](0015-experimental-lfe-evaluation.md)

## Context

This repository is the owned `jiti-lfe` fork. Its active functionality and build
path are LFE, but the plain launcher and README still selected SBCL. Normal chat
therefore depended on an extra backend flag and conflicting setup instructions.

## Decision

Default `scripts/repl.py` to LFE. Retain `--lfe` as a compatible explicit selector
and expose the unchanged SBCL frontend through `--legacy`. Keep the named
`image-repl` development command and SBCL tests explicitly on `--legacy`.
Document LFE first and retain the SBCL guide separately.

## Rationale

Keeping SBCL as the default preserves upstream convention but obscures this
fork's product and the user's normal-chat path. Removing SBCL would discard its
distinct restart semantics and historical implementation. Explicit legacy routing
retains those semantics without making them the fork's default. This changes
selection, not the LFE evaluator's architecture.

## Consequences

Unqualified launcher calls now create/reopen `.jiti/default` with LFE semantics.
Existing SBCL users must use `--legacy` or `image-repl`; their stores are not
imported into LFE. Conflicting selectors reject. The isolated monitored evaluator,
provisional repair and whole-action retry from 0015 remain unchanged. Active
restart dynamic extent remains specific to the SBCL backend.

Implementation: [launcher](../../scripts/repl.py), [commands](../../Makefile),
[development environment](../../devenv.nix), [README](../../README.md).
Verification: [real LFE and dispatch probes](../../tests/lfe_launcher.py),
[explicit SBCL CLI tests](../../tests/cli_scenarios.py),
[explicit SBCL terminal tests](../../tests/terminal_scenarios.py).
The dispatch probes do not substitute for running the SBCL suite, which requires
the configured development environment. Related: [SBCL guide](../sbcl.md).
