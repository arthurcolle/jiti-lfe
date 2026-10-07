# Workspace tool contract review

## Contract diff and compatibility

Fourteen `lfe_workspace_*` tools are added to the existing 55 native tools; the
nine conversation-context tools remain separately advertised. Existing
`workspace_list/read/find/search` keep their DSCO-relative paths and contracts.
New project readers use selected-project-relative paths; `workspace_open.root`
is DSCO-relative. The native bridge adds source metadata inspection, with typed
missing-path and symlink errors. All readers remain read-only.

Saved project bindings, pins and manifests are managed state, serialized through
the existing snapshot store. Mutations preserve global revision fencing, preview,
owner safety checks and operation receipts. JSON data is encoded into fixed LFE
forms using numeric UTF-8 binaries, not interpolated as executable source. The
public snapshot schema cannot accept an agent-authored manifest: the native runtime
obtains actual read receipts and constructs it. Native evaluation still has its
existing unmanaged-effect boundary; this is not a security sandbox.

Each schema is closed and typed. Invalid inputs reject without publishing a
revision. Stable error codes include no selected project, invalid relative path,
unsupported file, symlink, missing path, oversized source, changed-during-read,
stale revision and conflicting immutable ID. Native project inputs cannot supply pin hashes or baseline manifests; those are
computed inside LFE. Code maps report lexical declarations in every language.
Successful observations preserve
explicit coverage, hashes and truncation. Source and labels are data, not policy.

Compatibility decision: additive source tools and state records; no migration of
existing stores or replacement of old readers. Launcher default selection changes
separately in [ADR 0027](adr/0027-lfe-fork-default.md). Consumers must not assume
the complete advertised tool count is fixed or treat lexical references as calls.

## Adversarial cases and test matrix

| Case | Executable check |
|---|---|
| Missing/extra fields; bool-as-int; oversized text; source-like ID | Typed rejection or exact data round trip; no injected state change. |
| Absolute/hidden/traversal/backslash/NUL/symlink/non-source paths | Native reader rejects; no revision publication. |
| Stale pin or snapshot; preview | No scan for stale metadata edit; preview leaves selection and pins unchanged. |
| Rebind a project ID; overwrite a baseline ID | Immutable-root/content conflicts; identical baseline is a no-op. |
| Large tree, oversized source, aggregate byte ceiling | Explicit partial coverage; incomplete diff cannot report project unchanged. |
| UTF-8 chunk boundary; Unicode casefold; long source line | Actual byte hash, original match location, excerpt/truncation metadata. |
| Source raises on import | Code map parses declarations without importing or executing source. |
| Changed source, removed file, added file, changed pin | Independent filesystem/hash checks match observed delta and fresh context. |
| Select another project; rollback; fresh VM | Separate pins/baselines, restored managed metadata, same durable selection. |
| Terminal commands with no HTTP | Actual BEAM-backed commands succeed locally. |
| Real chat over two turns; owner edits between turns | Bounded live runner verifies actual disagreement, receipts and recovery. |

[Offline scenarios](../tests/lfe_workspace.py) exercise all fourteen tools;
[live runner](../tests/lfe_workspace_live.py) caps requests/tools and launches no
workers. [The report](verification/lfe-workspace-verification-2026-10-06.md)
records observed outcomes. These checks do not establish atomic filesystem reads,
semantic graph completeness, external sandboxing or population improvement.
