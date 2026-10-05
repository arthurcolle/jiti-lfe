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


def recover_model_application(output: Path) -> None:
    """Execute the accepted model-created app in a separate, credential-free SBCL."""
    path = output / "live-capture.json"
    capture = read_capture(path)
    if capture.get("meta", {}).get("passed") is not True:
        raise ValueError("Cannot verify recovery of an incomplete model capture")
    recovery_path = output / "recovery.json"
    if not recovery_path.exists():
        environment = {key: value for key, value in os.environ.items()
                       if key not in {"OPENAI_API_KEY", "OPENAI_API_KEY_FILE", "OPENAI_MODEL", "OPENAI_BASE_URL"}}
        subprocess.run(["sbcl", "--noinform", "--script", "scripts/launch/expense_capture.lisp",
                        "--recover", str(output)], cwd=ROOT, env=environment, check=True, timeout=60)
    event = read_capture(recovery_path)
    if event["process_id"] == capture["meta"]["process_id"]:
        raise ValueError("Recovery must execute in a distinct process")
    if event["view"]["status"] != "idle" or event["view"]["result"]["changed"]:
        raise ValueError("Recovery must execute without changing the accepted application")
    if not all(check["status"] == "PASS" for check in event["view"]["goal_checks"]):
        raise ValueError("Recovered application did not pass its caller checks")
    # Retain the original conversation bytes before adding independent recovery evidence.
    original = output / "model-conversation.json"
    if not original.exists():
        original.write_bytes(path.read_bytes())
    event.pop("prompt", None)  # This is a caller execution, not an invented chat request.
    event.update(verified=True, title="The model-built app runs in a fresh SBCL process",
                 verification_text="Separate SBCL recovered the accepted model-generated functions and ledger; caller checks passed.")
    capture["events"] = [e for e in capture["events"] if e["id"] != "fresh_recovery"] + [event]
    capture["meta"]["fresh_process_recovery_verified"] = True
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(capture, ensure_ascii=False, indent=2) + "\n")
    temporary.replace(path)
    print("PASS: the model-created application recovered and executed in a fresh process")


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
    parser.add_argument("--recover-only", action="store_true", help="Verify a saved successful model capture without API calls")
    args = parser.parse_args()
    output = args.output.resolve()
    if args.recover_only:
        recover_model_application(output)
        finish_artifacts(output)
        return 0
    configure()
    if not os.environ.get("OPENAI_MODEL") or not (
        os.environ.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY_FILE")
    ):
        parser.error("Configure OPENAI_MODEL and local API credentials before live capture")
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
            recover_model_application(output)
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
