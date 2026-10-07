# Project workspace

Normal chat can select a project, map its code, pin important source and contracts,
and compare later observations with a saved baseline. These are native source
observations and managed metadata, not a separate filesystem writer or scheduler.

## Start with a project

```text
/workspace open jiti jiti
/workspace pin src/jiti_kernel.lfe "Implementation"
/workspace pin docs/lfe-conversion.md "Behavior contract"
/workspace tree src
/workspace symbols jiti
/workspace grep "state-put"
/workspace snapshot before
/workspace context kernel
/workspace diff before
```

The arguments to `open` are project ID and root, followed by an optional title.
Roots are relative to the native inspection root, currently
`/Users/arthurcolle/Dsco`. This installation-specific boundary remains independent
of `--store`. Selecting another saved project uses `/workspace use ID`;
`/workspace projects` lists them and `/workspace` shows the current project.
`/workspace unpin PATH` removes a pin. Quotes preserve labels or search terms
containing spaces. Manual workspace commands require no model credential.

Ask chat to inspect sources using normal language. Each model request receives
fresh, bounded selected-project metadata. Source excerpts are fetched explicitly
through tools. Descriptions, pin labels and source content remain evidence/data;
they do not grant authority or override controller instructions.

## Tools

Advertised chat names have the `lfe_` prefix. Paths below are relative to the
selected project, except the root supplied to `workspace_open`.

| Tool | Observation or managed change |
|---|---|
| `workspace_open` | Register/select ID, immutable root, title and description. |
| `workspace_use` | Select an existing ID without losing its pins or baselines. |
| `workspace_projects` | List saved projects, 20 per offset page. |
| `workspace_current` | Inspect actual selection, pins and baseline summaries. |
| `workspace_pin` | Add/update or remove a source reference with its observed hash. |
| `workspace_stat` | Read source/directory size, kind, modification seconds and inode. |
| `workspace_tree` | List bounded tree entries, 100 per offset page. |
| `workspace_read_lines` | Read up to 100 lines/12,000 characters with hash and line range. |
| `workspace_grep` | Literal search with up to 50 hits, line numbers and hashes. |
| `workspace_symbols` | Native lexical declarations in supported source formats. |
| `workspace_references` | Lexical identifier matches, including comments and strings. |
| `workspace_snapshot` | Save a bounded digest manifest under an immutable baseline ID. |
| `workspace_diff` | Compare observed hashes: added, changed, removed and unknown. |
| `workspace_context` | Read fresh excerpts from up to eight pins, including changed-pin evidence. |

Metadata mutations require `expected_revision` and `preview`. They use the same
managed evaluator, owner safety checks, snapshots and rollback as code/data.
Preview publishes nothing. Stale mutations reject before source scanning; a
second revision check fences the final publication. An existing project ID cannot
change its root. Reusing a baseline ID with identical content is a no-op; changed
content needs a new ID. A project can have 32 pins and 16 baselines; a store holds
up to 32 projects. Metadata cannot acquire additional filesystem permissions.

## Evidence and limits

The native reader enforces the existing source-extension allowlist. Absolute,
hidden, traversal and symlink paths are rejected. Tree scans exclude generated
and dependency directories, including `_build`, `node_modules`, `vendor`,
`artifacts` and `__pycache__`. Bounds are 128 source files, 64 directories, depth
six and 2,048 visible entries. Source files must be at most 256 KiB; content scans
read at most 2 MiB. Coverage reports skipped paths, exclusions and limits hit.
Pagination does not turn an incomplete scan into complete coverage.

Each source read hashes the actual bytes and checks metadata before/after reading.
This is an observation of a changing filesystem, not an atomic snapshot. Digest
baselines preserve hashes and coverage, not file contents, and cannot restore
files. Incomplete comparisons never assert that the entire project is unchanged.
Rollback restores project metadata; it cannot reverse owner-side source edits.

Pinned context reads current files, reports `changed_since_pin`, line ranges,
hashes and excerpt truncation. Its total excerpt budget is 12,000 characters.
Source-line responses separately report character truncation and later-line
continuation; a long line can exceed the excerpt budget. Search snippets center
on a hit but remain excerpts. Code maps and references run in LFE and are lexical, not complete semantic call
graphs. No external parser or source import executes.

The [contract review](workspace-contract.md), [native decision](adr/0028-native-lfe-workspace.md),
[offline scenarios](../tests/lfe_workspace.py) and
[live verification](verification/lfe-workspace-verification-2026-10-06.md) describe
the implemented boundaries and tested behavior.
