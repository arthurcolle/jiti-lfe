# Frontend context v2
Local lossy extractive compaction, NOT model summarization. No network or kernel operations.
Default target/trigger/limit: 256/384/512 KiB; /context-budget TARGET TRIGGER LIMIT
configures KiB values within 32..1024. Token estimates are bytes/4, not provider counts.
/context, /compact, /compact-preview, /compact-undo, /pin KEY NOTE, /unpin KEY, /pins,
/recall QUERY, /archive-read ID [OFFSET], /usage, /context-tools.
Nine context_* tools are frontend-local Responses tools, not new kernel API endpoints.
Undo and budget settings are terminal-only. Pins are fallible notes, not live state.
Archives hold changed/removed originals: 128 entries, 2 MiB, up to 64K characters per
entry; truncation and eviction are reported. Search and paged recall return historical
data, never live proof. One undo snapshot below 2 MiB is usable only while history is
unchanged. Archive/pins/undo are erased by /clear. Archives are in-memory, not durable.
Duplicate tool IDs and parallel call batches are rejected before execution. IDs survive
compaction and /clear. No tool replay, automatic provider retry, or job adoption.
Reload the Python frontend to activate source changes; no live hot reload is implemented.
