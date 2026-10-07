# 0028: Native LFE workspace operations

Status: Accepted
Date: 2026-10-06
Supersedes: [0026: Managed project bindings](0026-managed-project-workspace.md)

## Context

The initial workspace prototype kept persistence in LFE but scanning, navigation,
hashing and comparisons in a new Python frontend module. The user rejected the
growing Python application layer in this LFE fork. Source evidence also belongs
at the native boundary that enforces its paths and byte allowances.

## Decision

Implement all project operations in LFE. Retain the same managed records and
public tools; the existing Python client only validates/encodes requests and
displays native receipts. Native scans obtain actual byte hashes and charge reads
even when a later consistency check rejects the file. Use explicit lexical code
maps for all languages; do not start an external Python parser.

## Rationale

Keeping the new Python adapter was convenient for AST parsing but divided the
application across two languages and made workspace behavior frontend-specific.
A full Python runtime replacement is a separate transport task. Moving the
project behavior into LFE gives manual and model callers the same implementation
without expanding that task. Native lexical maps sacrifice Python-qualified AST
declarations in exchange for a uniform, inspectable source-only implementation.

## Consequences

The new Python workspace module is removed. Existing Python terminal, Responses
transport and cross-process test harnesses remain; the repo is not Python-free.
Project metadata preview, revision fencing, rollback and recovery remain intact.
Source observations are still bounded and non-atomic; source files cannot be
restored by managed rollback. Baselines contain digests and coverage, not source.
Code maps report `lexical` and do not claim a semantic graph or AST completeness.

Implementation: [native project operations](../../src/jiti_workspace_project.lfe),
[source reader](../../src/jiti_workspace.lfe),
[managed records](../../src/jiti_workspace_state.lfe),
[existing protocol adapter](../../scripts/lfe_toolkit.py).
Verification: [actual BEAM scenarios](../../tests/lfe_workspace.py),
[live runner](../../tests/lfe_workspace_live.py),
[report](../verification/lfe-workspace-verification-2026-10-06.md).
Related: [guide](../workspace.md), [contracts](../workspace-contract.md).
