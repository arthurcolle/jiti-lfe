#!/usr/bin/env python3
"""Offline checks that launch excerpts retain the provenance and exact tool view."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "launch"))
from assemble_evidence import assemble  # noqa: E402


class EvidenceScenarios(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.scripted = self.root / "scripted.json"
        self.live = self.root / "live.json"
        self.scripted.write_text(json.dumps({"events": [
            {"id": "define_expense", "source": "(defun add-expense () :scripted)", "view": {"status": "idle"}},
            {"id": "paused_call", "source": "(render-budget-report)", "view": {"status": "paused", "condition": "Unsupported category"}},
        ]}))
        self.live_record = {"meta": {"passed": True}, "events": [{
            "id": "record_expense", "verified": True, "prompt": "Let me record expenses. Follow the caller contract.",
            "result_text": "((:AMOUNT 450 :CATEGORY :COFFEE))", "view": {"status": "idle", "revision": "final-revision"},
            "tool_calls": [{"name": "develop_form", "arguments": json.dumps({"source": "(defun add-expense () :live)"}),
                            "result": {"status": "idle", "revision": "definition-revision", "result": {"values": [{"text": "ADD-EXPENSE"}]}}}],
        }]}
        self.live.write_text(json.dumps(self.live_record))

    def tearDown(self):
        self.directory.cleanup()

    def test_mixed_provenance_and_actual_definition_view(self):
        result = assemble(self.scripted, self.live)
        self.assertEqual("mixed", result["meta"]["mode"])
        definition = result["sections"]["define_expense"]
        self.assertEqual("live-model", definition["mode"])
        self.assertEqual("record_expense", definition["event_id"])
        self.assertEqual(0, definition["tool_call_index"])
        self.assertIn("Revision: definition-revision", definition["lines"])
        self.assertNotIn("Revision: final-revision", definition["lines"])
        self.assertEqual("scripted-kernel", result["sections"]["paused_call"]["mode"])
        self.assertIn("Lisp: (defun add-expense () :live)", definition["lines"])

    def test_live_only_has_live_metadata(self):
        self.assertEqual("live-model", assemble(None, self.live)["meta"]["mode"])

    def test_unverified_capture_is_rejected(self):
        self.live_record["meta"]["passed"] = False
        self.live.write_text(json.dumps(self.live_record))
        with self.assertRaisesRegex(ValueError, "not passed"):
            assemble(self.scripted, self.live)

    def test_failed_attempt_does_not_override_verified_script(self):
        self.live_record["events"][0]["verified"] = False
        self.live.write_text(json.dumps(self.live_record))
        self.assertEqual("scripted-kernel", assemble(self.scripted, self.live)["sections"]["define_expense"]["mode"])


if __name__ == "__main__":
    unittest.main()
