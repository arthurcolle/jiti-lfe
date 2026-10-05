# Try a change. Undo a change.

Runtime: 45 seconds. Formats: landscape, portrait.

Use actual capture evidence where listed. Always display its provenance. A diagram illustrates behavior; it is not a terminal recording.

## 000–012s — Preview a temporary change

Visual: Preview a temporary change

On screen: Preview an extra expense / Inspect its temporary result / Original ledger restored

Caption: Recorded kernel execution; see provenance label.

Evidence: preview_restore

Narration: Preview adding another expense. You can inspect the temporary result, then the managed ledger returns to its earlier state. The trial does not become an accepted revision.

## 012–028s — Accept a change into history

Visual: Accept a change into history

On screen: Execute change / Check managed state / Publish accepted revision / Inspect /operations and /history

Caption: Recorded kernel execution; see provenance label.

Evidence: accepted_change

Narration: Execute a change normally and let caller checks validate it. Safe managed changes can become an accepted revision. Operation history records the attempt; revision history records the new application state. These histories tell different parts of the story.

## 028–045s — Restore earlier state and preserve history

Visual: Restore earlier state and preserve history

On screen: Earlier accepted state / Rollback → new revision / Code and data restored / History preserved

Caption: Recorded kernel execution; see provenance label.

Evidence: rollback_history

Narration: Now roll back to the earlier revision. Jiti restores its managed definitions and data and publishes another revision. The intervening history remains inspectable. Preview is for trying a change; rollback is for restoring an already accepted state.
