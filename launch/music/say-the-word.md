# Say the Word

Original launch theme for Jiti. A bright, singable synth-pop song about incrementally building a running application. Lyrics and composition brief below are newly written for this project; do not imitate a named recording artist or reuse an existing melody.

The delivery target is a sung 60-second master, a 30-second vocal trailer edit, and an instrumental bed. A synthesized instrumental is a useful local production asset. It is not a completed sung master. Keep the vocal deliverable marked pending until the configured Runway music provider has produced it and its usage terms have been recorded. Keep the API credential in its local configuration file; it is not an input to any scene, transcript, or artifact.

## Composition

- Tempo: exactly 128 BPM, 4/4. One bar is 1.875 seconds; 32 bars are 60 seconds.
- Key: C major. Chorus progression: C–G–Am–F, two bars per chord. Verse progression: Am–F–C–G, two bars per chord.
- Sound: warm rounded bass, crisp kick and clap, restrained eighth-note hats, a soft plucked synth arpeggio, and an original lead motif. Avoid notification sounds that could be mistaken for application feedback.
- Vocal: warm, conversational English; one clear lead, a light double on the final chorus, no imitation of a particular artist. Keep every word intelligible.
- Hook: a short rising phrase on “Say the word,” resolving on “watch it grow.” Leave room between lines for the viewer to read the application results.
- Suggested original chorus pitch contour in scale degrees, freely adapted to the syllables: `3 3 5 | 6 5 3`, `2 2 5 | 4 3 2`, `1 3 5 | 6 5 3`, `4 4 3 | 2 1`. The melody must be newly composed rather than matched to an existing song.

## 60-second sung master

| Bars | Time | Section | Words / direction |
|---|---|---|---|
| 1–4 | 0.0–7.5 | Intro | Instrumental hook. Establish pulse immediately; leave a clean opening for the empty catalogue. |
| 5–6 | 7.5–11.25 | Verse | “A little spark, a line of light” |
| 7–8 | 11.25–15.0 | Verse | “A thought becomes a thing tonight” |
| 9–10 | 15.0–18.75 | Verse | “Another piece, another door” |
| 11–12 | 18.75–22.5 | Verse | “We make it do a little more” |
| 13–14 | 22.5–26.25 | Chorus | “Say the word, watch it grow” |
| 15–16 | 26.25–30.0 | Chorus | “Piece by piece, see where it goes” |
| 17–18 | 30.0–33.75 | Chorus | “Keep it running, make it new” |
| 19–20 | 33.75–37.5 | Chorus | “One more thing that it can do” |
| 21–24 | 37.5–45.0 | Break | Instrumental; make space for the pause → repair → resume sequence. |
| 25–26 | 45.0–48.75 | Chorus | “Say the word, watch it grow” |
| 27–28 | 48.75–52.5 | Chorus | “Piece by piece, see where it goes” |
| 29–30 | 52.5–56.25 | Chorus | “Keep it running, make it new” |
| 31–32 | 56.25–60.0 | Chorus | “One more thing that it can do” — resolve and end cleanly at 60 seconds. |

## 30-second trailer edit

Sixteen bars, beginning directly on the chorus. Use master bars 13–20 followed by bars 25–32, with a musically clean edit. This produces two passes through the hook in exactly thirty seconds. Arrange the final pass with a brief stop before the final resolution so the Jiti title is readable. Preserve the final duration rather than appending a reverb tail.

The six five-second trailer scenes deliberately do not all coincide with bar boundaries; the visuals follow the story while the song holds its regular pulse. Place the highest emphasis at the first useful result, the resumed call, and the final title.

## Generation prompt

> Create an original 60-second bright synth-pop launch song called “Say the Word,” exactly 128 BPM in 4/4, C major, 32 bars. Warm bass, crisp restrained drums, plucked arpeggios, memorable newly composed melody. Friendly intelligible English sung vocal with no artist imitation. Follow the supplied bar-by-bar lyric sheet exactly. Four-bar instrumental intro, eight-bar verse, eight-bar chorus, four-bar instrumental break, eight-bar final chorus. End cleanly at 60 seconds. Supply separate instrumental and vocal stems when supported. No spoken commentary, watermark announcements, or extra lyrics.

## Mix and acceptance

Use the instrumental beneath the nine narrated videos. Keep narration intelligible on laptop and phone speakers, and lower the music further during source or restart explanations. Reserve sung vocals for the musical trailer. Do not run sung lyrics under technical narration.

Deliver uncompressed audio masters when the provider supports them, plus compressed preview assets. Record actual provider, voice, generation settings, source files, and usage terms in the production metadata. Verify durations, clear lyrics, clean edit points, clipping, and intelligibility by listening. A local synthesized theme should be described as an original instrumental in titles and metadata until a sung version exists.
