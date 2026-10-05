# Jiti launch production

This package explains Jiti as **an application you grow by talking to it**. The flagship example starts with an empty managed expense ledger and no expense-tracker functions, then adds and composes useful functions inside a running Lisp image. The runtime, adapter, and caller-owned checks exist at startup.

[manifest.json](manifest.json) is the editable source of truth for ten videos, 54 distinct scenes, and 12 minutes 15 seconds of primary footage. [scripts/](scripts/) contains the readable timed narration and storyboards. [music/say-the-word.md](music/say-the-word.md) contains the original lyric sheet, bar-accurate music brief, and generation prompt.

## Deliverables

[kernel-diagrams/](kernel-diagrams/) contains editable SVGs explaining the model/tool loop, controller and worker, live repair, and managed recovery. Rebuild PNG exports and mobile review images with `devenv shell -- python3 launch/kernel-diagrams/render.py`. [diagrams/](diagrams/) contains additional figures illustrating the expense example.

| ID | Video | Duration | Formats |
|---|---|---:|---|
| 01 | Grow an app by talking to it | 90 s | Landscape |
| 02 | What actually happens when you ask? | 120 s | Landscape |
| 03 | Inside the running Lisp image | 240 s | Landscape |
| 04 | Your first function | 30 s | Landscape + portrait |
| 05 | Teach once, combine later | 40 s | Landscape + portrait |
| 06 | Close it. Your app remains. | 35 s | Landscape + portrait |
| 07 | Try a change. Undo a change. | 45 s | Landscape + portrait |
| 08 | Repair the paused call | 60 s | Landscape + portrait |
| 09 | Who decides whether it works? | 45 s | Landscape + portrait |
| 10 | Say the Word | 30 s | Landscape + portrait |

Production targets are 1920×1080 landscape and 1080×1920 portrait at 24 FPS, with narration, an instrumental bed, phrase-timed captions, and a distinct thumbnail for each video. The manifest explicitly identifies which scenes need captured evidence and which are explanatory diagrams. Renderer output and audio metadata are the authority on which assets have actually been generated.

## Reproducible production

Run the application interactively:

```sh
devenv shell -- image-repl --program examples/expense-tracker.lisp --store .image-agent/workspaces/expenses/
```

Start by asking: “Define add-expense(amount, category). Store entries as property lists with :amount in positive integer cents and :category as a keyword in the :expenses managed table entry. Then record 450 cents for :coffee.” Next ask for `total-expenses()`, `spending-by-category()` returning an association list, and `budget-report(budget-cents)` returning `:spent`, `:remaining`, and `:by-category` while reusing the earlier functions. These interfaces are the adapter's caller-owned acceptance contract; no implementation is supplied at startup.

Create recordings in fresh directories, generate audio once, then rerender entirely from saved assets:

```sh
devenv shell -- sbcl --noinform --script scripts/launch/expense_capture.lisp .image-agent/launch/scripted
devenv shell -- launch-capture .image-agent/launch/live
python3 scripts/launch/assemble_evidence.py --scripted .image-agent/launch/scripted/capture.json --live .image-agent/launch/live/live-capture.json --output .image-agent/launch/evidence.json
devenv shell -- launch-audio
# Verify the sung master, then prepare its local trailer edit:
devenv shell -- launch-audio --edit-trailer
devenv shell -- launch-render
devenv shell -- launch-package
devenv shell -- test-launch
```

The batch render creates `artifacts/launch/index.html`, ten horizontal videos, seven portrait versions, thumbnails, captions, transcripts, and retained source frames. Open the gallery locally to review. Capture and audio generation are separate explicit commands; `launch-render` uses `.image-agent/launch/evidence.json` and saved audio and never makes network requests. Existing recordings are preserved rather than overwritten.

`launch-package` checks all 17 exports for their expected duration, dimensions, audio, and caption files. It copies the original song, narration, raw generation assets, captures, and editable sources into the deliverable folder, then records file hashes in `package-report.json`.

`launch-audio` reads the Runway credential from `~/runway` by default; `--key-file` selects a different local file. It saves task IDs and request hashes to resume interrupted generation without silently spending again. Credentials and signed download URLs are never exported. The audio generator's metadata records the actual model, voice, duration, and any timing adjustments.

Live capture verifies recovery after closing its original worker. To verify an existing successful capture again without model requests, run `devenv shell -- launch-capture .image-agent/launch/live --recover-only`; the original conversation remains in `model-conversation.json`.

The implementation entry points are the expense-demo scripts under `scripts/launch/` and the Python renderer at `scripts/launch/render.py`. Use their `--help` output for current capture and render arguments. The renderer must rebuild from saved evidence and audio; a re-render must not silently make more model calls.

1. Capture a clean deterministic expense session and retain its raw output, accepted definitions, result values, and checks.
2. Capture an actual model conversation for incremental generation when the configured provider is available. Preserve the exact definitions and replies that occurred.
3. Bind evidence IDs to the saved events. Narration and diagrams may explain an action, but a transcript must never invent a model reply or terminal result.
4. Generate narration and music through the configured Runway provider, recording actual status and provider metadata. Then build landscape and portrait compositions from the manifest. Keep any fallback instrumental explicitly labeled.
5. Review the generated videos, captions, audio, and source evidence together. Distribute the raw evidence and editable production sources alongside the exports.

Do not treat this README or the requested-deliverable table as evidence that a particular render or remote audio generation finished. Generated manifests and files should record actual status. No publishing step is included.

## Evidence contract

Scenes reference these logical IDs: `empty_catalogue`, `record_expense`, `spending_total`, `category_totals`, `budget_report`, `preview_restore`, `rollback_history`, `fresh_recovery`, `paused_call`, `repair_resume`, `subsequent_call`, `caller_checks`, and `safety_rejection`, `define_expense`, `define_report`, `accepted_change`, and `repair_definitions`.

A capture supplies the real event and provenance. The deterministic reproduction uses supplied definitions to make kernel behavior repeatable. An actual model session records definitions created by the configured model. Label these sources explicitly on screen and in metadata. If a requested ID is absent, the renderer should visibly report missing evidence or reject a strict final render; it must not fabricate success.

The known ledger contains coffee 450 cents, groceries 3200 cents, and transport 1800 cents. Its total is 5450 cents. A 6000-cent budget leaves 550 cents. Repair evidence uses `v1-active-frame` on the existing report invocation and `v2-new-frame` on the next invocation; the corresponding entry counts are 1 and 2. Use actual result values and operation identities to substantiate these claims.

## Editorial checks

- Keep a provenance label legible on every captured-evidence scene. Explicitly mark diagrams and any accelerated footage.
- Show the initial catalogue, a new function, and an actual result early. Let the viewer inspect readable code rather than hiding all machinery behind animation.
- Keep caller-owned goals distinct from safety invariants. A false goal may allow useful safe progress; a failed invariant rejects an attempt.
- Explain preview as restoration of managed state. Explain rollback as a new accepted revision that restores earlier managed state and preserves history.
- Explain recovery as importing accepted code and data into a fresh process. Live call stacks and active restarts belong to the running process.
- Show the original frame continuing after repair and a subsequent invocation entering the replacement definition. Avoid implying that an active frame changes its own body.
- Keep credentials out of prompts shown on screen, raw capture, generated media, and metadata.
- Listen to narration and music on small speakers. A locally synthesized instrumental is labeled as instrumental. The sung master remains pending until real vocal audio exists.

## Manifest interface

The top level contains `schema_version`, `project`, `fps`, `videos`, `audio`, and delivery metadata. Each video has a stable `id`, `title`, integer `duration`, `orientations`, `kind`, and ordered `scenes`. Scene durations must sum to the video duration. Each scene has an `id`, `title`, integer `duration`, `narration`, `visual`, and `evidence_ids`.

`visual` contains `kind` (`capture`, `diagram`, `code`, or `title`), `description`, `headline`, `lines`, and `caption`. Headlines are at most 65 characters, line lists contain at most five entries, and scenes last at least five seconds. Empty narration denotes music-only footage. The music brief specifies exactly 32 bars at 128 BPM for a 60-second master and 16 bars for a 30-second trailer.

## Runway audio generation

`python3 scripts/launch/runway_audio.py` generates scene narration and the original music using the configured local Runway credential file. The default file is `~/runway`; `--key-file` selects another local file. Credential contents stay in memory. Do not put credentials into the manifest, prompts, or command arguments.

Use `--narration --only 01-grow-an-app` to generate one video's speech, or `--music` for the vocal master and instrumental. `--dry-run` lists intended assets without reading credentials or making a request. `--workers` is limited to three concurrent tasks. FFmpeg and ffprobe are required; use the development shell or supply `--ffmpeg` and `--ffprobe` paths.

Audio is saved under `.image-agent/launch/audio/`, with raw model generations under `raw/` and safe task/provenance records under `state/`. A task ID and request hash are saved before polling. Rerunning resumes existing tasks and reuses verified files; a changed request or an ambiguous submission stops that asset to prevent accidental repeat charges. No authorization headers, signed output URLs, or provider error bodies enter saved metadata. Offline resume checks run with `python3 scripts/launch/test_runway_audio.py`.

Narration uses Runway's `eleven_v4` model and Maya preset, normalized to a target of −16 LUFS. The script allows at most 1.3× time compression to fit a scene and never truncates speech. Music uses `seed_audio`; it preserves the generated master duration and records the measured duration. The requested 60-second sung master and instrumental each have their own original prompt. The current production generated both 60-second masters and all 48 narration scenes successfully. Offline transcription verified the sung lyrics. The reviewed 30-second trailer repeats the full final chorus at 42–60 seconds twice with 1.2× time compression; transcription recovered all four lines twice, including the first and final words. Rebuild that edit locally with `python3 scripts/launch/runway_audio.py --edit-trailer`, which makes no provider request. The initial 45-second cut clipped the opening phrase and was rejected. This recipe applies to the reviewed generated master; inspect any replacement performance before claiming lyric alignment. Keep the full vocal master, instrumental, raw sources, and generation metadata available for review.

Provider references: [Runway API](https://docs.dev.runwayml.com/api/), [official model schemas](https://github.com/runwayml/sdk-python/tree/main/src/runwayml/types), and [Runway terms](https://runwayml.com/terms-of-use). The metadata records the provider and settings; users should consult the provider's terms for the account and intended distribution.
