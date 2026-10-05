# Kernel diagrams

These four figures explain the general conversational Lisp application and its kernel. The expense example is not used as the organizing structure.

Run `devenv shell -- python3 launch/kernel-diagrams/render.py` from the repository root. The generator reuses the established drawing primitives in `launch/diagrams/render.py`, writes editable SVG sources here, and writes matching high-resolution PNGs, 375-pixel mobile previews and a contact sheet under `artifacts/launch/kernel-diagrams/`.

`manifest.json` contains diagram keys, dimensions, paths, alt text and captions. `conversation` is the model/tool loop; `composition` shows kernel ownership; `repair` shows the live repair protocol; `persistence` shows recovery and revision history.

The figures describe the implementation documented by README and ADRs 0001, 0002, 0003, 0004, 0006, 0007, 0009 and 0010. The repair figure uses generic function labels for the separately scripted repair capture. It does not portray an autonomous model repairing that call. Revision numbers are illustrative.
