# Repair the paused call

Runtime: 60 seconds. Formats: landscape, portrait.

Use actual capture evidence where listed. Always display its provenance. A diagram illustrates behavior; it is not a terminal recording.

## 000–012s — One report call enters the worker

Visual: One report call enters the worker

On screen: Marker: v1-active-frame / Entry count: 1 / Unsupported :transport

Caption: Recorded kernel execution; see provenance label.

Evidence: paused_call

Narration: A report starts with the local marker v-one active frame. Its entry counter is one. It then encounters a transport category its helper cannot label.

## 012–024s — The worker holds the active restart

Visual: The worker holds the active restart

On screen: Same worker / Same operation / Live restart remains available

Caption: Recorded kernel execution; see provenance label.

Evidence: paused_call

Narration: The condition pauses the attempt and exposes a live restart. The owning worker keeps that restart in its dynamic extent while the controller inspects the problem.

## 024–036s — Repair the helper and replace the report body

Visual: Repair the helper and replace the report body

On screen: category-label supports transport / New report marker: v2-new-frame / Shared provisional checkpoint

Caption: Recorded kernel execution; see provenance label.

Evidence: repair_definitions

Narration: Repair the category-label helper. Also define a new report body with a different marker. Those changes are provisional parts of the paused attempt until it completes safely.

## 036–048s — The original call continues

Visual: The original call continues

On screen: Original operation resumes / Result: v1-active-frame / Entry count still 1

Caption: Recorded kernel execution; see provenance label.

Evidence: repair_resume

Narration: Resume through the live restart. The report completes with v-one active frame and an entry count of one. That result proves the original invocation continued.

## 048–060s — The next call uses the new definition

Visual: The next call uses the new definition

On screen: New report invocation / Result: v2-new-frame / Entry count now 2

Caption: Recorded kernel execution; see provenance label.

Evidence: subsequent_call

Narration: Call the report again. Now it returns v-two new frame and the entry count reaches two. New calls use the replacement; existing frames keep their original bodies.
