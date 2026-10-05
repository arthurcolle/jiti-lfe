#!/usr/bin/env python3
"""Exercise launch capture against SBCL; no API credentials or model requests.

Run from the repo root: devenv shell -- python3 tests/launch_capture_scenarios.py
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="jiti-launch-test-") as temporary:
        output = Path(temporary) / "capture"
        command = ["sbcl", "--noinform", "--script", "scripts/launch/expense_capture.lisp", str(output)]
        subprocess.run(command, check=True, timeout=90, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        capture = json.loads((output / "capture.json").read_text())
        events = {event["id"]: event for event in capture["events"]}
        assert "not a model conversation" in capture["provenance"]
        assert events["empty_catalogue"]["view"]["result"]["catalogue_count"] == 0
        assert events["spending_total"]["result_text"] == "5450"
        assert "550" in events["budget_report"]["result_text"]
        assert events["preview_restore"]["view"]["result"]["commit"] == "restored"
        assert events["safety_rejection"]["view"]["result"]["reason"] == "UNSAFE"
        assert events["safety_rejection"]["view"]["revision"] == events["budget_report"]["view"]["revision"]
        assert events["rollback_history"]["view"]["revision"] != events["accepted_change"]["view"]["revision"]
        assert events["paused_call"]["view"]["status"] == "paused"
        assert events["paused_call"]["view"]["operation_id"] == events["repair_resume"]["view"]["operation_id"]
        assert '"v1-active-frame" :ENTRIES 1' in events["repair_resume"]["result_text"]
        assert '"v2-new-frame" :ENTRIES 2' in events["subsequent_call"]["result_text"]
        assert events["fresh_recovery"]["process_id"] != capture["process_id"]
        assert events["fresh_recovery"]["view"]["result"]["changed"] is False
        assert events["fresh_recovery"]["view"]["result"]["functions"] == []
        assert all(check["status"] == "PASS" for check in events["caller_checks"]["view"]["goal_checks"])
        assert events["caller_checks"]["result_text"] is None
        assert len(capture["verification"]) >= 16
        before = (output / "capture.json").read_bytes()
        repeated = subprocess.run(command, timeout=30, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        assert repeated.returncode != 0, "capture must refuse to overwrite an existing recording"
        assert (output / "capture.json").read_bytes() == before
    print("PASS: launch scenarios, fresh-process recovery, evidence integrity, and overwrite protection")


if __name__ == "__main__":
    main()
