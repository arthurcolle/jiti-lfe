#!/usr/bin/env python3
"""Validate and collect portable launch deliverables without network requests."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from render import write_gallery


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/launch"))
    parser.add_argument("--capture-root", type=Path, default=Path(".image-agent/launch"))
    args = parser.parse_args()
    output = args.output
    manifest = json.loads((output / "manifest.json").read_text())
    report = json.loads((output / "render-report.json").read_text())
    expected = {(v["id"], orientation): v for v in manifest["videos"] for orientation in v["orientations"]}
    actual = {(record["id"], record["orientation"]): record for record in report["outputs"]}
    if set(expected) != set(actual) or len(actual) != len(report["outputs"]):
        raise ValueError("The complete set of video exports is required before packaging")
    for key, record in actual.items():
        if record["narration"] not in {"complete", "not-applicable"}:
            raise ValueError("Incomplete narration: " + record["id"])
        path = output / record["file"]
        probe = json.loads(subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)], text=True))
        video = next(s for s in probe["streams"] if s["codec_type"] == "video")
        audio = next(s for s in probe["streams"] if s["codec_type"] == "audio")
        dimensions = (1920, 1080) if key[1] == "landscape" else (1080, 1920)
        if (video["width"], video["height"]) != dimensions or video["codec_name"] != "h264" or audio["codec_name"] != "aac":
            raise ValueError("Incorrect media format: " + str(path))
        if abs(float(probe["format"]["duration"]) - expected[key]["duration"]) > .2:
            raise ValueError("Incorrect media duration: " + str(path))
        for suffix in (".srt", ".vtt", ".txt"):
            if not (output / record["id"]).with_suffix(suffix).is_file():
                raise ValueError("Missing caption or transcript: " + record["id"])
    # Preserve request metadata, original audio, exact source code, and transcripts.
    shutil.copytree(args.capture_root / "audio", output / "audio", dirs_exist_ok=True)
    for name in ("live", "scripted"):
        shutil.copytree(args.capture_root / name, output / "sources" / "captures" / name, dirs_exist_ok=True)
    shutil.copytree("launch", output / "sources" / "editorial", dirs_exist_ok=True)
    shutil.copytree("scripts/launch", output / "sources" / "pipeline", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copy2("examples/expense-tracker.lisp", output / "sources" / "expense-tracker.lisp")
    write_gallery(output, report["outputs"])
    metadata = {"verified_video_exports": len(actual), "unique_videos": len(manifest["videos"]),
                "video_format": "H.264 / AAC", "source_capture_provenance": "sources/captures/",
                "generation_report": "audio/generation-report.json", "files": {}}
    for path in sorted(output.rglob("*")):
        if path.is_file() and path.name != "package-report.json":
            metadata["files"][str(path.relative_to(output))] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    (output / "package-report.json").write_text(json.dumps(metadata, indent=2) + "\n")
    print(f"Packaged {len(actual)} verified videos, audio, captures, and editable sources: {output}")


if __name__ == "__main__":
    main()
