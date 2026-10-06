# LFE toolkit contract review

Date: 2026-10-06. Additive interface; no existing tool is renamed or removed.
The 31 schemas live in `scripts/lfe_toolkit.py`; structured results are nested
under `data`. Existing status/revision/goal/token fields retain their meaning.
Clients ignoring `data` can still read the core protocol. Generic source tools
remain cooperative. No shell, credential, network or workspace-write tool is added.

## Contract diff

| Surface | New contract | Side effects / retries |
|---|---|---|
| `state_list/get` | Atom/binary keys, 50-entry pages, bounded printed/JSON values, explicit `found` | Read-only; unknown atom reads never intern |
| `state_put/delete/increment/compare_set/append/merge/patch` | Exact fields, JSON values, required revision, explicit preview; patches up to 32 edits | Normal managed safety/publication; stale retry rejected; failed patch restores all edits |
| `function_search/source` | Name/arity lookup without interning; search pages 50, source pages 4000 characters | Read-only; source is normalized original form |
| `function_define/call/forget` | Structured names/arguments, literal JSON call arguments, required revision and preview | Managed code/data; explicit source remains cooperative; callers retained and inspected before forgetting |
| `function_test/expression_check` | Up to 32 cases; true plus unchanged candidate for a predicate | Restore provisional code/data; observations do not undo external effects or certify independent usefulness |
| `job_start` | Named ID, source <=32 KiB, timeout 1..60000ms, required revision | Owner-manager key/hash fencing and durable accepted receipt; no preview; external effect may outlive rejected publication |
| `job_list/status/reconcile/wait/cancel` | Separate recorded/observed status and handles; wait <=30000ms outside evaluator | Reconciliation only records observations; unknown does not overwrite terminal evidence or replay; cancellation uses existing owned handle |
| `note_put/get/list/search/delete` | Text <=32 KiB, up to 16 tags, provenance, pages of 20 | Managed persistence; revision/preview for edits; content is data and must contain no credentials |
| `tools_list/describe` | Effective advertised tools only; pages of 25, exact schema | No grant or enable operation; dispatch also rejects unadvertised tools |
| `workspace_find/search` | Existing visible source paths/types; 100 directories, depth 6, 50 matches; file search <=48000 bytes | Read-only, no shell; explicit truncation and encoding/offset accuracy; hidden/traversal/symlink paths rejected |

Every field is required; unknown/missing fields fail before execution. Boolean
fields require JSON booleans, integer fields exclude booleans. Nested object schemas
disable additional properties. JSON data rejects malformed Unicode, nonfinite
numbers, depth >16, more than 1024 nodes or 32 KiB. Combined adapter arguments are
bounded at 128 KiB. Definition arguments/call arrays have at most 16 members.
The outer managed evaluation retains its owner-configured deadline (default 1s).
Model requests retain their configured timeout and explicit tool/request ceilings
in live verification. A function test can time out the outer evaluation and retain
the existing explicit pause/abort protocol; it does not swallow worker deadlines.

Native rejection codes include `stale_revision`, `state_key_not_found`,
`integer_required`, `list_required`, `object_required`, `function_not_found`,
`function_has_callers`, `reserved_function`, `invalid_definition`,
`job_id_conflict`, `job_start_rejected`, `job_handle_unknown`, and JSON size/depth/node
codes. Other conditions become `native_evaluation_failed`, with no condition values,
source or credentials. Existing safety failures and controller failures retain
their existing protocol. Native inspection failures use controller rejection.

Mutations retain operation IDs and durable diagnostic metadata: hashes and byte
counts, not source, values or conditions. Tool results necessarily contain explicitly
requested data and artifacts; do not submit credentials to state, functions or notes.
Unknown completion after controller/publication failure requires inspection before
any further action. Named admission fencing covers the current manager and accepted
durable records; it does not claim durable exactly-once external effects.

## Adversarial cases and test matrix

| Case | Verification |
|---|---|
| Missing/extra fields, bool-as-int, int-as-bool, empty test cases | Frontend schema rejection without revision change |
| Malformed JSON, NaN, surrogate, oversized/deep/large-node payload | Preflight rejection before native evaluation |
| Source-like ID/function name and literal string argument | Exact data/symbol round trip, no injected state write |
| Unknown atom-key reads | Actual VM atom count unchanged after warmed lookups |
| Duplicate stale increment; mismatched compare/set | No duplicate edit; unmatched compare creates no revision |
| Failed later patch action; preview | Earlier provisional edits discarded; committed state unchanged |
| Mutating function/predicate; exception | Failed observation and restored provisional state; no publication |
| Reserved function; invalid definition; identifiable callers | Stable rejection; callers retained |
| Large normalized function source | Complete ordered pagination beyond old display cap |
| Duplicate job; conflicting ID; rollback; safety-rejected launch | Same owned handle/count for identical request; conflicting request rejected |
| Wait zero/timeout; cancellation; job-local writes | Bounded frontend wait; owned stop; background cannot publish state |
| Fresh VM with outstanding and completed jobs | Unknown observation, historical result retained, no replacement workers |
| Notes after restart | Same text/tags/provenance from managed store |
| Restricted advertised tools | Discovery does not reveal/enable others; dispatch rejects them |
| Traversal, absolute path, hidden credentials, source search | Existing inspection restrictions, UTF-8 chunk reconstruction and truthful pagination/truncation |
| Real model using ten distinct new tools | Explicit bounded live runner plus independent state/result checks and fresh-VM recovery |

Executable matrix: [offline BEAM scenarios](../tests/lfe_toolkit.py),
[bounded live smoke](../tests/lfe_toolkit_live.py). These tests establish protocol
behavior, not long-term farm improvement or an external security sandbox.
