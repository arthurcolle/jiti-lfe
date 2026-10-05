#!/usr/bin/env python3
"""Generate resumable launch audio with Runway, without persisting secrets or URLs.

Official API reference: https://docs.dev.runwayml.com/api/
Model schema: https://github.com/runwayml/sdk-python/tree/main/src/runwayml/types
Usage terms: https://runwayml.com/terms-of-use (review for your account and use).

Task sidecars are written before submission and immediately after receiving an ID.
An ambiguous submission is never automatically retried: it may already have spent
credits. Successful task IDs are polled again to refresh expired download URLs.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

API_BASE = "https://api.dev.runwayml.com/v1"
API_VERSION = "2024-11-06"
DOCS = ["https://docs.dev.runwayml.com/api/", "https://github.com/runwayml/sdk-python/tree/main/src/runwayml/types", "https://runwayml.com/terms-of-use"]


class AudioError(RuntimeError):
    pass


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", dir=path.parent, delete=False, prefix=".audio-", encoding="utf-8") as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
        f.write("\n")
        tmp = f.name
    os.replace(tmp, path)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Runway:
    def __init__(self, key_file, timeout=600):
        try:
            self._key = Path(key_file).expanduser().read_text().strip()
        except OSError:
            raise AudioError("Unable to read configured Runway credential file") from None
        if not self._key or "\n" in self._key:
            raise AudioError("Runway credential file must contain one nonempty credential")
        self.timeout = timeout
        self.opener = urllib.request.build_opener(NoRedirect)

    def request(self, route, body=None):
        if not re.fullmatch(r"/(?:text_to_speech|sound_effect|tasks/[A-Za-z0-9_-]+)", route):
            raise AudioError("Invalid Runway API route")
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(API_BASE + route, data=data, headers={
            "Authorization": "Bearer " + self._key,
            "X-Runway-Version": API_VERSION,
            "Content-Type": "application/json",
        })
        try:
            with self.opener.open(req, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise AudioError(f"Runway API returned HTTP {exc.code}; response body withheld") from None
        except (urllib.error.URLError, TimeoutError, ValueError, OSError):
            raise AudioError("Runway API transport or response error; sensitive details withheld") from None

    def fetch(self, task_id):
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            result = self.request("/tasks/" + task_id)
            status = result.get("status")
            if status == "SUCCEEDED":
                output = result.get("output", [])
                if not output or not isinstance(output[0], str) or not output[0].startswith("https://"):
                    raise AudioError("Runway task returned no HTTPS audio output")
                return output[0]
            if status in {"FAILED", "CANCELLED", "CANCELED"}:
                raise AudioError(f"Runway task {status}; provider error details withheld")
            if status not in {"PENDING", "RUNNING", "THROTTLED"}:
                raise AudioError("Runway returned an unrecognized task state")
            time.sleep(2)
        raise AudioError("Runway polling deadline reached; rerun to resume existing task")

    def download(self, url, target):
        # Signed provider URLs are used only in memory, without API authorization.
        target.parent.mkdir(parents=True, exist_ok=True)
        temp = target.with_suffix(target.suffix + ".part")
        try:
            with urllib.request.urlopen(urllib.request.Request(url), timeout=60) as response, temp.open("wb") as output:
                total = 0
                while block := response.read(1024 * 1024):
                    total += len(block)
                    if total > 256 * 1024 * 1024:
                        raise AudioError("Generated audio exceeds download size limit")
                    output.write(block)
            if not total:
                raise AudioError("Generated audio download was empty")
            temp.replace(target)
        except (urllib.error.URLError, TimeoutError, OSError):
            temp.unlink(missing_ok=True)
            raise AudioError("Audio download failed; signed URL and details withheld") from None


def binary(name, override):
    if override:
        result = str(Path(override))
    else:
        result = shutil.which(name)
    if not result:
        raise AudioError(f"{name} is required; use --{name} or the development shell")
    return result


def run(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise AudioError("Local audio conversion failed; inspect input with ffprobe")
    return result.stdout


def duration(path, ffprobe):
    try:
        return float(run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", str(path)]).strip())
    except ValueError:
        raise AudioError("Unable to determine generated audio duration") from None


def normalize(raw, target, seconds, ffmpeg, ffprobe, speech):
    length = duration(raw, ffprobe)
    # Leave 150ms after speech. No narration is truncated to hit the shot duration.
    tempo = max(1.0, length / (seconds - 0.15)) if speech else 1.0
    if speech and tempo > 1.3:
        raise AudioError(f"Narration is {length:.2f}s for {seconds}s scene; needs >1.3x speed, edit script or timing")
    filters = ([f"atempo={tempo:.8f}"] if tempo > 1.0 else []) + ["loudnorm=I=-16:TP=-1.5:LRA=9"]
    if not speech:
        # The master preserves the model's actual arrangement and duration.
        filters += ["afade=t=in:st=0:d=0.1", f"afade=t=out:st={max(0,length-0.8):.5f}:d=0.8"]
    target.parent.mkdir(parents=True, exist_ok=True)
    run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(raw), "-af", ",".join(filters), "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(target)])
    actual = duration(target, ffprobe)
    if speech and actual > seconds + 0.025:
        raise AudioError("Normalized narration exceeds scene; audio retained for review")
    return {"raw_duration_seconds": length, "duration_seconds": actual, "atempo": tempo, "loudness_target_lufs": -16, "truncated": False}


SONG_PROMPT = """Create a complete original sung synth-pop SONG named Say the Word. Exactly 60 seconds, 128 BPM, 4/4, C major, 32 bars. This is sung MUSIC with a clear melodic human-style English lead vocal, not spoken narration. Warm rounded bass, crisp kick and clap, light eighth-note hats, plucked synth arpeggios, original memorable melody. Do not imitate an artist or quote any existing melody. Chorus chords C G Am F, two bars each. Verse Am F C G, two bars each. The lyrics must be sung intelligibly. Bar structure: bars1-4 instrumental intro (0-7.5s); bars5-12 verse (7.5-22.5s), each line spans two bars: 'A little spark, a line of light' / 'A thought becomes a thing tonight' / 'Another piece, another door' / 'We make it do a little more'. Bars13-20 chorus (22.5-37.5s), each line spans two bars: 'Say the word, watch it grow' / 'Piece by piece, see where it goes' / 'Keep it running, make it new' / 'One more thing that it can do'. Bars21-24 instrumental break (37.5-45s). Bars25-32 final chorus (45-60s), repeat the four chorus lines exactly, with a light vocal double. Clean final musical resolution at60seconds, no added tail. No speech, commentary, sound logos, or announcements. Deliver the complete musical arrangement with sung vocals."""
INSTRUMENTAL_PROMPT = """Create an original instrumental synth-pop music bed, exactly60seconds long,128BPM,4/4,Cmajor,32bars. Warm rounded bass, crisp restrained kick and clap, light eighth-note hats, soft plucked synthesizer arpeggios, simple memorable original synth lead melody. Friendly, curious, optimistic launch theme for building a Lisp application incrementally. Absolutely no voices, no singing, no words, no spoken narration. Do not imitate an artist or existing melody. Four-bar intro, eight-bar verse with Am F C G (two bars each), eight-bar chorus C G Am F (two bars each), four-bar instrumental break, eight-bar final chorus C G Am F. Clear pulse immediately, melody leaves space for explanatory narration, clean final musical resolution at60seconds with no tail. Music should work at low volume underneath speech."""


def tasks_from_manifest(manifest, selection, narration, music):
    jobs = []
    if music:
        for name, prompt in [("say-the-word-vocal-master", SONG_PROMPT), ("say-the-word-instrumental", INSTRUMENTAL_PROMPT)]:
            jobs.append({"id": "music/" + name, "route": "/sound_effect", "seconds": 60, "speech": False,
                         "body": {"model": "seed_audio", "promptText": prompt, "sampleRate": 48000, "outputFormat": "wav"}})
    if narration:
        known = {v["id"] for v in manifest["videos"]}
        if selection - known:
            raise AudioError("Unknown --only video ID")
        for video in manifest["videos"]:
            if selection and video["id"] not in selection:
                continue
            for scene in video["scenes"]:
                if not scene.get("narration"):
                    continue
                jobs.append({"id": video["id"] + "/" + scene["id"], "route": "/text_to_speech", "seconds": scene["duration"], "speech": True,
                             "body": {"model": "eleven_v4", "promptText": scene["narration"], "voice": {"type": "runway-preset", "presetId": "Maya"}, "speed": 1, "stability": 0.65, "seed": 42}})
    return jobs


def generate(job, client, output, ffmpeg, ffprobe):
    ident = job["id"]
    if not re.fullmatch(r"[a-zA-Z0-9_-]+/[a-zA-Z0-9_-]+", ident):
        raise AudioError("Unsafe manifest audio identifier")
    request_hash = hashlib.sha256(json.dumps({"route": job["route"], "body": job["body"]}, sort_keys=True).encode()).hexdigest()
    state_path = output / "state" / (ident + ".json")
    raw = output / "raw" / (ident + ".audio")
    target = output / (ident + ".wav")
    state = json.loads(state_path.read_text()) if state_path.exists() else None
    if state and state.get("request_sha256") != request_hash:
        raise AudioError("Existing request hash differs; move prior state deliberately before requesting another paid generation")
    if state and target.exists() and state.get("status") == "complete" and state.get("output_sha256") == digest(target):
        if ident == "music/say-the-word-instrumental":
            shutil.copyfile(target, output / "instrumental.wav")
        elif ident == "music/say-the-word-vocal-master":
            shutil.copyfile(target, output / "song.wav")
        print(f"Cached {ident}", flush=True)
        return state
    if not state:
        state = {"asset_id": ident, "request_sha256": request_hash, "status": "submitting", "provider": "Runway", "model": job["body"]["model"], "api_version": API_VERSION, "requested_duration_seconds": job["seconds"], "kind": "narration" if job["speech"] else "music", "settings": job["body"], "documentation": DOCS}
        save_json(state_path, state)
        response = client.request(job["route"], job["body"])
        task_id = response.get("id")
        if not isinstance(task_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", task_id):
            raise AudioError("Runway submission returned no valid task ID; inspect task dashboard before retrying")
        state.update(task_id=task_id, status="submitted")
        save_json(state_path, state)
        print(f"Submitted {ident}", flush=True)
    if not state.get("task_id"):
        raise AudioError("Previous submission outcome ambiguous; inspect Runway dashboard before retrying to prevent duplicate charges")
    if not raw.exists():
        url = client.fetch(state["task_id"])
        client.download(url, raw)
        state.update(status="downloaded", raw_sha256=digest(raw))
        save_json(state_path, state)
    details = normalize(raw, target, job["seconds"], ffmpeg, ffprobe, job["speech"])
    state.update(status="complete", output_sha256=digest(target), output_file=str(target), raw_file=str(raw), **details)
    save_json(state_path, state)
    if ident == "music/say-the-word-instrumental":
        shutil.copyfile(target, output / "instrumental.wav")
    elif ident == "music/say-the-word-vocal-master":
        shutil.copyfile(target, output / "song.wav")
    print(f"Ready {ident}: {details['duration_seconds']:.2f}s", flush=True)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("launch/manifest.json"))
    parser.add_argument("--key-file", type=Path, default=Path.home() / "runway")
    parser.add_argument("--output", type=Path, default=Path(".image-agent/launch/audio"))
    parser.add_argument("--only", help="Comma-separated video IDs for narration")
    parser.add_argument("--narration", action="store_true", help="Generate narration (both kinds if neither flag is set)")
    parser.add_argument("--music", action="store_true", help="Generate sung music and instrumental")
    parser.add_argument("--workers", type=int, choices=[1, 2, 3], default=3)
    parser.add_argument("--timeout", type=int, default=600, help="Finite polling timeout per task")
    parser.add_argument("--ffmpeg")
    parser.add_argument("--ffprobe")
    parser.add_argument("--dry-run", action="store_true", help="Validate and list requests without loading credentials or calling API")
    args = parser.parse_args()
    try:
        if args.timeout < 1 or args.timeout > 1800:
            raise AudioError("Timeout must be between1and1800seconds")
        manifest = json.loads(args.manifest.read_text())
        both = not args.narration and not args.music
        jobs = tasks_from_manifest(manifest, set(filter(None, (args.only or "").split(","))), args.narration or both, args.music or both)
        if args.dry_run:
            print(json.dumps({"requests": len(jobs), "characters": sum(len(j["body"]["promptText"]) for j in jobs), "assets": [j["id"] for j in jobs]}, indent=2))
            return 0
        ffmpeg, ffprobe = binary("ffmpeg", args.ffmpeg), binary("ffprobe", args.ffprobe)
        client = Runway(args.key_file, args.timeout)
        successes, failures = [], []
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(generate, job, client, args.output, ffmpeg, ffprobe): job["id"] for job in jobs}
            for future in concurrent.futures.as_completed(futures):
                ident = futures[future]
                try:
                    successes.append(future.result())
                except AudioError as exc:
                    message = str(exc)
                    failures.append({"asset_id": ident, "error": message})
                    print(f"Failed {ident}: {message}", flush=True)
                except Exception:
                    failures.append({"asset_id": ident, "error": "Unexpected local error; details withheld"})
                    print(f"Failed {ident}: unexpected local error; details withheld", flush=True)
        save_json(args.output / "generation-report.json", {"provider": "Runway", "api_version": API_VERSION, "successful": successes, "failures": failures, "complete": not failures, "documentation": DOCS})
        print(f"Complete: {len(successes)} assets; {len(failures)} failures", flush=True)
        return 1 if failures else 0
    except (AudioError, OSError, ValueError) as exc:
        print(str(exc) if isinstance(exc, AudioError) else "Local configuration error; details withheld", flush=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
