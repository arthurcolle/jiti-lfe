#!/usr/bin/env python3
"""Capture genuine model chat using the existing local OpenAI configuration."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from local_openai import configure  # noqa: E402
from assemble_evidence import assemble, read_capture  # noqa: E402


def finish_artifacts(output: Path) -> None:
    """Derive readable artifacts from the actual successful recording."""
    path = output / "live-capture.json"
    capture = read_capture(path)
    evidence = assemble(None, path)
    (output / "evidence.json").write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
    lines = ["JITI — ACTUAL MODEL CONVERSATION", f"Model: {capture['meta']['model']}", ""]
    for event in capture["events"]:
        lines.append(f"[{event['id']}] {event['title']}")
        if event.get("prompt"):
            lines.append("User: " + event["prompt"])
        for tool in event.get("tool_calls", []):
            lines.extend(["Tool: " + tool["name"], "Arguments: " + tool["arguments"],
                          "Actual tool result: " + json.dumps(tool["result"], ensure_ascii=False)])
        if event.get("reply"):
            lines.append("Model: " + event["reply"])
        if event.get("result_text"):
            lines.append("Caller execution result: " + event["result_text"])
        if event.get("verification_text"):
            lines.append(event["verification_text"])
        lines.append("")
    (output / "transcript.txt").write_text("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="Fresh output directory")
    args = parser.parse_args()
    configure()
    if not os.environ.get("OPENAI_MODEL") or not (
        os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY_FILE")
    ):
        parser.error("Configure OPENAI_MODEL and local API credentials before live capture")
    output = args.output.resolve()
    if output.exists():
        parser.error("Output directory must be fresh; existing recordings are preserved")
    process = subprocess.Popen(
        ["sbcl", "--noinform", "--script", "scripts/launch/chat_capture.lisp", str(output)],
        cwd=ROOT,
        start_new_session=True,
    )
    try:
        status = process.wait(timeout=600)
        if status == 0:
            finish_artifacts(output)
        return status
    except (subprocess.TimeoutExpired, KeyboardInterrupt):
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        print("Live capture stopped; accepted revisions and recorded events are preserved.", file=sys.stderr)
        return 124


if __name__ == "__main__":
    raise SystemExit(main())
