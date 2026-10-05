# Application diagrams

Four original vector diagrams explain growing a Lisp application through
conversation. `manifest.json` records each SVG source, PNG
export, export dimensions, alt text and suggested caption.

Regenerate from the repository root:

```sh
devenv shell -- python3 launch/diagrams/render.py
```

The renderer writes editable SVGs here and matching 2× PNGs under
`artifacts/launch/diagrams/`. Each PNG also has a 375-pixel mobile preview; the
contact sheet is for review, not publication. SVG and PNG use the same drawing
primitives and DejaVu fonts. SVG labels remain editable text.

Evidence:

- Figures 1 and 2 summarize `.image-agent/launch/live/live-capture.json` and
  `.image-agent/launch/live/generated-source.lisp` from the actual model run.
  Requests in figure 1 are condensed, not literal quotations.
- Figure 3 describes the separate author-scripted repair in
  `.image-agent/launch/scripted/capture.json`. It does not claim that the model
  initiated this repair. Controller requests run on the worker; the original
  report frame remains active until its restart resumes it.
- Figure 4 reflects fresh-process recovery in the live run and the
  history-preserving rollback contract in `docs/adr/0007-history-preserving-rollback.md`.
  Its revision numbers are illustrative. It does not depict stack persistence
  or recovery of unmanaged external resources.
