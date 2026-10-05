#!/usr/bin/env python3
"""Tests for timing, capture provenance, and the actual media render boundary."""

import copy
import json
import shutil
import subprocess
import tempfile
import unittest
import wave
from pathlib import Path

import render


def fixture():
    scene = {"id":"proof","title":"A saved result","duration":2,
             "narration":"Read the saved result. See how the next step uses it.",
             "visual":{"kind":"capture","headline":"A saved result","lines":[],"caption":"Test fixture"},
             "evidence_ids":["result"]}
    manifest = {"schema_version":1,"fps":12,"videos":[
        {"id":"test","title":"Render fixture","duration":2,"orientations":["landscape","portrait"],"scenes":[scene]}]}
    evidence = {"meta":{"mode":"deterministic-seed"},"sections":{"result":{"lines":["(sum '(1 2 3))","=> 6"]}}}
    return manifest,evidence


class TimingTests(unittest.TestCase):
    def test_words_survive_captions_and_all_time_is_covered(self):
        manifest,_ = fixture()
        scene = manifest["videos"][0]["scenes"][0]
        scene["narration"] *= 30
        cues = render.scene_captions(scene)
        self.assertEqual(" ".join(text for _,_,text in cues).split(),scene["narration"].split())
        self.assertEqual(cues[0][0],0)
        self.assertAlmostEqual(cues[-1][1],2)
        for previous,current in zip(cues,cues[1:]):
            self.assertAlmostEqual(previous[1],current[0])
        slices = render.scene_slices(scene)
        self.assertAlmostEqual(sum(b-a for a,b,*_ in slices),2)

    def test_caption_timing_respects_measured_narration(self):
        manifest,_ = fixture()
        scene = manifest["videos"][0]["scenes"][0]
        scene["_caption_duration"] = 1.2
        self.assertAlmostEqual(render.scene_captions(scene)[-1][1],1.2)
        self.assertEqual(render.scene_slices(scene)[-1][-1],"")

    def test_unsubstantiated_capture_is_rejected(self):
        manifest,evidence = fixture()
        del evidence["sections"]["result"]
        with self.assertRaisesRegex(ValueError,"missing execution evidence"):
            render.validate_manifest(manifest,evidence)

    def test_duration_and_duplicate_identifiers_are_rejected(self):
        manifest,evidence = fixture()
        manifest["videos"][0]["duration"] = 3
        with self.assertRaisesRegex(ValueError,"scenes total"):
            render.validate_manifest(manifest,evidence)
        manifest,evidence = fixture()
        manifest["videos"].append(copy.deepcopy(manifest["videos"][0]))
        with self.assertRaisesRegex(ValueError,"duplicate video"):
            render.validate_manifest(manifest,evidence)

    def test_credentials_cannot_enter_export(self):
        manifest,evidence = fixture()
        evidence["sections"]["result"]["lines"].append("Bearer " + "x"*30)
        with self.assertRaisesRegex(ValueError,"credential"):
            render.validate_manifest(manifest,evidence)

    def test_timestamp_carries_milliseconds(self):
        self.assertEqual(render.timestamp(59.9996),"00:01:00,000")

    def test_partial_rerender_retains_only_matching_sources(self):
        previous = {"manifest_sha256":"m","evidence_sha256":"e","outputs":[
            {"id":"a","orientation":"landscape","file":"old-a"},
            {"id":"b","orientation":"portrait","file":"old-b"}]}
        current = {"manifest_sha256":"m","evidence_sha256":"e","outputs":[
            {"id":"a","orientation":"landscape","file":"new-a"}]}
        merged,matched = render.merge_report(previous,current)
        self.assertTrue(matched)
        self.assertEqual([item["file"] for item in merged["outputs"]],["new-a","old-b"])
        current["evidence_sha256"] = "different"
        merged,matched = render.merge_report(previous,current)
        self.assertFalse(matched)
        self.assertEqual([item["file"] for item in merged["outputs"]],["new-a"])


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"),"FFmpeg is required")
class RenderIntegrationTests(unittest.TestCase):
    def test_real_mp4_both_orientations_and_caption_exports(self):
        manifest,evidence = fixture()
        with tempfile.TemporaryDirectory(prefix="jiti-render-test-") as directory:
            target = Path(directory)
            records = render.render_video(manifest["videos"][0],evidence,target,None,None,
                                          shutil.which("ffmpeg"),shutil.which("ffprobe"),12,0.2)
            self.assertEqual(len(records),2)
            for record in records:
                output = target/record["file"]
                result = subprocess.run([shutil.which("ffprobe"),"-v","error","-show_streams","-of","json",str(output)],
                                        text=True,capture_output=True,check=True)
                streams = json.loads(result.stdout)["streams"]
                video = next(stream for stream in streams if stream["codec_type"] == "video")
                audio = next(stream for stream in streams if stream["codec_type"] == "audio")
                self.assertEqual(video["width"],record["width"])
                self.assertEqual(video["height"],record["height"])
                self.assertEqual(video["codec_name"],"h264")
                self.assertEqual(audio["codec_name"],"aac")
                self.assertAlmostEqual(record["duration"],2,delta=0.15)
                self.assertTrue((target/record["thumbnail"]).is_file())
            self.assertIn("00:00:02,000",(target/"test.srt").read_text())
            self.assertIn("Read the saved result",(target/"test.txt").read_text())
            self.assertTrue((target/"test.vtt").read_text().startswith("WEBVTT"))

    def test_song_replaces_missing_narration_for_music_trailer(self):
        manifest,evidence = fixture()
        video = manifest["videos"][0]
        video["kind"] = "music"
        video["orientations"] = ["landscape"]
        with tempfile.TemporaryDirectory(prefix="jiti-song-test-") as directory:
            target = Path(directory)
            song = target/"song.wav"
            with wave.open(str(song),"wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(8000)
                stream.writeframes(b"\0\0"*16000)
            records = render.render_video(video,evidence,target,None,None,
                                          shutil.which("ffmpeg"),shutil.which("ffprobe"),12,0.2,song=song)
            self.assertEqual(records[0]["audio"],"song")
            self.assertEqual(records[0]["narration"],"not-applicable")
            self.assertEqual(records[0]["missing_narration_scenes"],[])


if __name__ == "__main__":
    unittest.main()
