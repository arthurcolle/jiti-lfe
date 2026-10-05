#!/usr/bin/env python3
"""Offline tests for paid-request resume guarantees; no credentials or network."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("runway_audio", Path(__file__).with_name("runway_audio.py"))
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)


class ResumeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.output = Path(self.tmp.name)
        self.job = {"id": "test/scene", "route": "/text_to_speech", "seconds": 10, "speech": True,
                    "body": {"model": "eleven_v4", "promptText": "A real test."}}
        self.state = self.output / "state/test/scene.json"
        self.addCleanup(self.tmp.cleanup)

    def client(self):
        owner = self
        class Client:
            requests = 0
            def request(self, route, body):
                self.requests += 1
                state = json.loads(owner.state.read_text())
                assert state["status"] == "submitting"
                return {"id": "task-example"}
            def fetch(self, task_id):
                state = json.loads(owner.state.read_text())
                assert state["task_id"] == task_id
                return "https://example.invalid/ephemeral"
            def download(self, url, target):
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"raw audio")
        return Client()

    def normalize(self, raw, target, seconds, ffmpeg, ffprobe, speech):
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"normalized audio")
        return {"duration_seconds": 3.0, "raw_duration_seconds": 3.0, "atempo": 1.0, "truncated": False}

    def test_success_is_cached_and_sidecars_precede_paid_operations(self):
        client = self.client()
        with patch.object(audio, "normalize", self.normalize), contextlib.redirect_stdout(io.StringIO()):
            first = audio.generate(self.job, client, self.output, "ffmpeg", "ffprobe")
            second = audio.generate(self.job, client, self.output, "ffmpeg", "ffprobe")
        self.assertEqual(client.requests, 1)
        self.assertEqual(first["output_sha256"], second["output_sha256"])
        self.assertNotIn("ephemeral", self.state.read_text())

    def test_ambiguous_submission_is_not_retried(self):
        client = self.client()
        def fail(route, body):
            raise audio.AudioError("transport unavailable")
        client.request = fail
        with self.assertRaises(audio.AudioError):
            audio.generate(self.job, client, self.output, "ffmpeg", "ffprobe")
        client = self.client()
        with self.assertRaisesRegex(audio.AudioError, "ambiguous"):
            audio.generate(self.job, client, self.output, "ffmpeg", "ffprobe")
        self.assertEqual(client.requests, 0)

    def test_changed_script_requires_deliberate_new_generation(self):
        client = self.client()
        with patch.object(audio, "normalize", self.normalize), contextlib.redirect_stdout(io.StringIO()):
            audio.generate(self.job, client, self.output, "ffmpeg", "ffprobe")
        self.job["body"]["promptText"] = "A changed script."
        with self.assertRaisesRegex(audio.AudioError, "hash differs"):
            audio.generate(self.job, client, self.output, "ffmpeg", "ffprobe")
        self.assertEqual(client.requests, 1)


    def test_long_narration_is_rejected_instead_of_truncated(self):
        with patch.object(audio, "duration", return_value=14.0), patch.object(audio, "run") as converter:
            with self.assertRaisesRegex(audio.AudioError, ">1.3x"):
                audio.normalize(Path("raw.wav"), Path("out.wav"), 10, "ffmpeg", "ffprobe", True)
        converter.assert_not_called()

    def test_invalid_identifier_cannot_escape_audio_directory(self):
        self.job["id"] = "../../bad"
        with self.assertRaisesRegex(audio.AudioError, "Unsafe"):
            audio.generate(self.job, self.client(), self.output, "ffmpeg", "ffprobe")


if __name__ == "__main__":
    unittest.main()
