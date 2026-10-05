#!/usr/bin/env python3
"""Render reviewable Jiti launch films from a manifest and saved execution evidence.

No model calls happen here. Pillow composes readable keyframes; FFmpeg produces
the films. Captures are literal excerpts from the supplied evidence JSON and
diagrams are explicitly labelled. See --help for rendering and validation.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import html
import json
import math
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BG = "#101521"
PANEL = "#192232"
INK = "#F4F5F8"
MUTED = "#AAB8CE"
ACCENT = "#77E4B4"
ORANGE = "#FFAA75"
SAFE_ID = re.compile(r"^[a-zA-Z0-9_-]+$")
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")
SECRET = re.compile(r"(?:sk-[A-Za-z0-9_-]{20,}|Bearer\s+[A-Za-z0-9_.-]{20,})")


def read_json(path):
    return json.loads(Path(path).read_text())


def validate_manifest(manifest, evidence):
    """Fail before rendering when a scene cannot substantiate its capture."""
    if manifest.get("schema_version") != 1:
        raise ValueError("Expected manifest schema_version 1")
    if not 1 <= manifest.get("fps", 24) <= 60:
        raise ValueError("fps must be between 1 and 60")
    sections = evidence.get("sections", {})
    video_ids = set()
    for video in manifest["videos"]:
        vid = video["id"]
        if not SAFE_ID.fullmatch(vid) or vid in video_ids:
            raise ValueError(f"Invalid or duplicate video id: {vid}")
        video_ids.add(vid)
        if not video.get("scenes"):
            raise ValueError(f"{vid}: no scenes")
        if set(video.get("orientations", ["landscape"])) - {"landscape", "portrait"}:
            raise ValueError(f"{vid}: unsupported orientation")
        total = sum(scene["duration"] for scene in video["scenes"])
        if abs(total - video["duration"]) > 0.001:
            raise ValueError(f"{vid}: scenes total {total}s, expected {video['duration']}s")
        scene_ids = set()
        for scene in video["scenes"]:
            sid = scene["id"]
            if not SAFE_ID.fullmatch(sid) or sid in scene_ids:
                raise ValueError(f"{vid}: invalid or duplicate scene id {sid}")
            scene_ids.add(sid)
            if scene["duration"] <= 0:
                raise ValueError(f"{vid}/{sid}: duration must be positive")
            kind = scene["visual"]["kind"]
            if kind not in {"capture", "diagram", "code", "title", "steps"}:
                raise ValueError(f"{vid}/{sid}: unknown visual kind {kind}")
            if kind == "capture" and not scene.get("evidence_ids"):
                raise ValueError(f"{vid}/{sid}: a capture needs evidence_ids")
            for eid in scene.get("evidence_ids", []):
                if eid not in sections:
                    raise ValueError(f"{vid}/{sid}: missing execution evidence {eid!r}")
                if not evidence_lines(sections[eid]):
                    raise ValueError(f"{vid}/{sid}: empty execution evidence {eid!r}")
    if SECRET.search(json.dumps([manifest, evidence])):
        raise ValueError("Possible credential in manifest or evidence; refusing to export")


def evidence_lines(section):
    if isinstance(section, list):
        lines = section
    elif isinstance(section, str):
        lines = section.splitlines()
    else:
        lines = section.get("lines", section.get("text", ""))
        if isinstance(lines, str):
            lines = lines.splitlines()
    return [ANSI.sub("", str(line)).replace("\t", "  ") for line in lines]


def caption_chunks(text, limit=92):
    """Keep complete words and distribute captions by spoken word count."""
    words = text.split()
    chunks, current = [], []
    for word in words:
        if current and len(" ".join(current + [word])) > limit:
            chunks.append(" ".join(current))
            current = []
        current.append(word)
    if current:
        chunks.append(" ".join(current))
    return chunks


def scene_captions(scene, start=0.0):
    text = scene.get("narration") or scene["visual"].get("caption") or ""
    chunks = caption_chunks(text)
    total = sum(len(chunk.split()) for chunk in chunks)
    cursor = start
    result = []
    for chunk in chunks:
        length = scene.get("_caption_duration", scene["duration"]) * len(chunk.split()) / total
        result.append((cursor, cursor + length, chunk))
        cursor += length
    return result


def video_captions(video):
    result, cursor = [], 0.0
    for scene in video["scenes"]:
        result.extend(scene_captions(scene, cursor))
        cursor += scene["duration"]
    return result


def timestamp(seconds, separator=","):
    ms = round(seconds * 1000)
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    secs, ms = divmod(ms, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02}{separator}{ms:03}"


def write_captions(video, target):
    cues = video_captions(video)
    srt = "\n\n".join(
        f"{i}\n{timestamp(a)} --> {timestamp(b)}\n{text}"
        for i, (a, b, text) in enumerate(cues, 1)
    )
    target.with_suffix(".srt").write_text(srt + "\n")
    vtt = "WEBVTT\n\n" + "\n\n".join(
        f"{timestamp(a, '.')} --> {timestamp(b, '.')}\n{text}" for a, b, text in cues
    )
    target.with_suffix(".vtt").write_text(vtt + "\n")
    paragraphs = [video["title"], "=" * len(video["title"]), ""]
    for scene in video["scenes"]:
        paragraphs.extend([scene["title"], scene.get("narration", ""), ""])
        if scene.get("evidence_ids"):
            paragraphs.extend(["Evidence: " + ", ".join(scene["evidence_ids"]), ""])
    target.with_suffix(".txt").write_text("\n".join(paragraphs))


def find_font(name):
    candidates = [
        Path("/usr/share/fonts/truetype/dejavu") / name,
        Path("/usr/share/fonts/TTF") / name,
    ]
    candidates += [Path(p) for p in glob.glob(f"/nix/store/*dejavu*/share/fonts/truetype/{name}")]
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError(f"Cannot find {name}; install DejaVu fonts")


class Composer:
    """Lay out each aspect ratio independently; never crop a landscape film."""

    def __init__(self, width, height):
        from PIL import Image, ImageDraw, ImageFont

        self.Image, self.ImageDraw, self.ImageFont = Image, ImageDraw, ImageFont
        self.w, self.h = width, height
        self.portrait = height > width
        self.scale = width / (1080 if self.portrait else 1920)
        self.font_path = find_font("DejaVuSans.ttf")
        self.mono_path = find_font("DejaVuSansMono.ttf")
        self.fonts = {}

    def font(self, size, mono=False):
        key = (max(8, round(size * self.scale)), mono)
        if key not in self.fonts:
            self.fonts[key] = self.ImageFont.truetype(self.mono_path if mono else self.font_path, key[0])
        return self.fonts[key]

    def wrap(self, draw, text, font, width):
        if not text:
            return [""]
        result, line = [], ""
        for word in text.split():
            candidate = (line + " " + word).strip()
            if draw.textlength(candidate, font=font) <= width:
                line = candidate
            else:
                if line:
                    result.append(line)
                # Long Lisp identifiers must stay inside the panel too.
                line = ""
                for char in word:
                    if line and draw.textlength(line + char, font=font) > width:
                        result.append(line)
                        line = ""
                    line += char
        if line:
            result.append(line)
        return result

    def text(self, draw, xy, text, size, color=INK, width=None, mono=False, max_lines=None):
        font = self.font(size, mono)
        lines = self.wrap(draw, text, font, width or self.w) if width else [text]
        if max_lines and len(lines) > max_lines:
            lines = lines[:max_lines]
            last = lines[-1]
            while draw.textlength(last + "…", font=font) > (width or self.w):
                last = last[:-1]
            lines[-1] = last.rstrip() + "…"
        x, y = xy
        leading = round(size * self.scale * 1.3)
        for line in lines:
            draw.text((x, y), line, font=font, fill=color)
            y += leading
        return y

    def frame(self, video, scene, evidence, phase, phase_count, caption, index, total):
        image = self.Image.new("RGB", (self.w, self.h), BG)
        draw = self.ImageDraw.Draw(image)
        s = self.scale
        margin = round((64 if self.portrait else 96) * s)
        content_w = self.w - margin * 2
        # Intentional spacious branding and discrete scene navigation.
        draw.rounded_rectangle((margin, 44*s, margin+76*s, 94*s), radius=12*s, fill=ACCENT)
        self.text(draw, (margin+12*s, 47*s), "(λ)", 32, BG)
        self.text(draw, (margin+98*s, 43*s), "jiti", 36)
        self.text(draw, (margin+190*s, 55*s), "GROW A RUNNING APPLICATION", 18, MUTED)
        for n in range(total):
            width = (content_w - (total-1)*8*s) / total
            x = margin + n * (width+8*s)
            draw.rounded_rectangle((x, 127*s, x+width, 132*s), radius=2*s,
                                   fill=ACCENT if n <= index else PANEL)
        headline = scene["visual"].get("headline") or scene["title"]
        title_y = 169*s if self.portrait else 160*s
        title_end = self.text(draw, (margin, title_y), headline,
                              62 if self.portrait else 64, width=content_w, max_lines=3 if self.portrait else 2)
        kind = scene["visual"]["kind"]
        label = {"capture": "RECORDED EXECUTION · EXCERPT", "diagram": "EXPLANATORY DIAGRAM",
                 "code": "CODE WALKTHROUGH", "title": "JITI · LIVE LISP", "steps": "EXPLANATORY DIAGRAM"}[kind]
        if kind == "capture":
            sources = [evidence["sections"][eid] for eid in scene.get("evidence_ids", [])]
            modes = set()
            for source in sources:
                if isinstance(source,dict):
                    provenance = (str(source.get("provenance", "")) + " " + str(source.get("mode", ""))).lower()
                else:
                    provenance = ""
                provenance += " " + str(evidence.get("meta",{}).get("mode", ""))
                if "live-model" in provenance or "live model" in provenance:
                    modes.add("model")
                if "deterministic" in provenance or "scripted" in provenance or "seed" in provenance:
                    modes.add("scripted")
            if modes == {"model"}:
                label = "RECORDED MODEL-BUILT APP · EXCERPT"
            elif modes == {"scripted"}:
                label = "SCRIPTED KERNEL EXECUTION · EXCERPT"
            elif modes == {"model","scripted"}:
                label = "RECORDED EXECUTION · MIXED SOURCES"
        panel_top = max(title_end + 36*s, (405 if self.portrait else 332)*s)
        panel_bottom = (self.h - (390 if self.portrait else 225)*s)
        self.text(draw, (margin, panel_top-31*s), label, 22 if self.portrait else 17, ACCENT)
        box = (margin, panel_top, self.w-margin, panel_bottom)
        draw.rounded_rectangle(box, radius=24*s, fill=PANEL)
        visual_lines = scene["visual"].get("lines", [])
        if kind == "capture":
            lines = []
            for eid in scene.get("evidence_ids", []):
                lines += evidence_lines(evidence["sections"][eid])
            self.capture(draw, box, lines, phase, phase_count)
        elif kind in {"diagram", "steps"}:
            nodes = scene["visual"].get("nodes") or visual_lines
            self.diagram(draw, box, nodes, phase, phase_count)
        else:
            self.statements(draw, box, visual_lines, phase, phase_count, mono=kind == "code")
        # Captions are always burned in and also exported as SRT/VTT.
        caption_y = self.h - (315 if self.portrait else 173)*s
        if caption:
            self.text(draw, (margin, caption_y), caption,
                      37 if self.portrait else 33, width=content_w,
                      max_lines=4 if self.portrait else 3)
        footer = scene["visual"].get("caption", "")
        self.text(draw, (margin, self.h-60*s), footer, 17, MUTED,
                  width=content_w-85*s, max_lines=1)
        self.text(draw, (self.w-margin-70*s, self.h-60*s), f"{index+1:02}/{total:02}", 17, MUTED)
        return image

    def capture(self, draw, box, lines, phase, phase_count):
        left, top, right, bottom = box
        s = self.scale
        for n, color in enumerate(["#F87979", "#F3CE73", ACCENT]):
            draw.ellipse((left+(23+n*22)*s, top+23*s, left+(35+n*22)*s, top+35*s), fill=color)
        self.text(draw, (left+107*s, top+18*s), "SBCL / captured output", 18, MUTED)
        size = 35 if self.portrait else 28
        font = self.font(size, True)
        wrapped = []
        for line in lines:
            wrapped.extend(self.wrap(draw, line, font, right-left-64*s))
        max_rows = max(1, int((bottom-top-104*s)/(size*1.35*s)))
        # Show all available evidence over time, paging long terminal excerpts.
        pages = max(1, math.ceil(len(wrapped)/max_rows))
        page = min(pages-1, int(phase*pages/max(1, phase_count)))
        page_lines = wrapped[page*max_rows:(page+1)*max_rows]
        visible = max(1, math.ceil(len(page_lines)*(phase+1)/phase_count)) if pages == 1 else len(page_lines)
        y = top+68*s
        for line in page_lines[:visible]:
            self.text(draw, (left+28*s, y), line, size,
                      ACCENT if line.strip().startswith(("=>", "result", "PASS", "TOTAL")) else INK, mono=True)
            y += size*1.35*s
        if pages > 1:
            self.text(draw, (right-145*s, bottom-32*s), f"excerpt {page+1}/{pages}", 15, MUTED)

    def diagram(self, draw, box, nodes, phase, phase_count):
        left, top, right, bottom = box
        s = self.scale
        nodes = list(nodes)[:5]
        if not nodes:
            return
        active = min(len(nodes)-1, int(phase*len(nodes)/max(1,phase_count)))
        vertical = self.portrait or len(nodes) > 4
        if vertical:
            gap = 20*s
            height = min(120*s, (bottom-top-65*s-gap*(len(nodes)-1))/len(nodes))
            y = top+32*s
            for i, node in enumerate(nodes):
                color = ACCENT if i == active else (MUTED if i < active else "#59667A")
                draw.rounded_rectangle((left+26*s,y,right-26*s,y+height),radius=13*s,
                                       fill=BG,outline=color,width=max(1,round(2*s)))
                self.text(draw,(left+43*s,y+height/2-17*s),f"{i+1:02}",24,color)
                size = min(36 if self.portrait else 29,height/s/3.1)
                self.text(draw,(left+104*s,y+height/2-size*s),str(node),size,
                          color,width=right-left-148*s,max_lines=2)
                if i < len(nodes)-1:
                    draw.line((left+61*s,y+height,left+61*s,y+height+gap),fill=color,width=max(1,round(3*s)))
                y += height+gap
        else:
            gap = 34*s
            width = (right-left-64*s-gap*(len(nodes)-1))/len(nodes)
            x = left+32*s
            y = top+57*s
            height = bottom-top-115*s
            for i,node in enumerate(nodes):
                color = ACCENT if i == active else (MUTED if i < active else "#59667A")
                draw.rounded_rectangle((x,y,x+width,y+height),radius=18*s,fill=BG,outline=color,width=max(1,round(2*s)))
                self.text(draw,(x+22*s,y+23*s),f"{i+1:02}",25,color)
                self.text(draw,(x+22*s,y+81*s),str(node),30,color,width=width-44*s,max_lines=4)
                if i < len(nodes)-1:
                    mid = y+height/2
                    draw.line((x+width,mid,x+width+gap,mid),fill=color,width=max(1,round(3*s)))
                    draw.polygon([(x+width+gap,mid),(x+width+gap-9*s,mid-6*s),(x+width+gap-9*s,mid+6*s)],fill=color)
                x += width+gap

    def statements(self, draw, box, lines, phase, phase_count, mono=False):
        left, top, right, bottom = box
        s = self.scale
        visible = max(1, math.ceil(len(lines)*(phase+1)/phase_count))
        y = top+35*s
        usable = bottom-top-60*s
        size = min(38 if self.portrait else 40, max(23, usable/s/max(1,len(lines))/1.85))
        for i,line in enumerate(lines[:visible]):
            y = self.text(draw,(left+32*s,y),str(line),size,ACCENT if i == visible-1 else INK,
                          width=right-left-64*s,mono=mono,max_lines=3)
            y += 22*s


def scene_slices(scene):
    duration = scene["duration"]
    phases = min(5, max(2, math.floor(duration/2)))
    captions = scene_captions(scene)
    boundaries = sorted(set([0.0,duration] + [duration*i/phases for i in range(1,phases)] +
                            [a for a,_,_ in captions] + [b for _,b,_ in captions]))
    result = []
    for a,b in zip(boundaries,boundaries[1:]):
        if b-a < 0.001:
            continue
        middle = (a+b)/2
        caption = next((text for ca,cb,text in captions if ca <= middle < cb), "")
        phase = min(phases-1, int(middle*phases/duration))
        result.append((a,b,phase,phases,caption))
    return result


def run(command):
    subprocess.run([str(x) for x in command], check=True)


def locate_binary(name):
    result = shutil.which(name)
    if result:
        return result
    raise RuntimeError(f"{name} is required; run this command through devenv shell")


def duration_of(path, ffprobe):
    proc = subprocess.run([ffprobe,"-v","error","-show_entries","format=duration","-of","json",str(path)],
                          capture_output=True,text=True,check=True)
    return float(json.loads(proc.stdout)["format"]["duration"])


def narration_path(audio_dir, video, scene):
    if audio_dir:
        for extension in ("wav", "mp3", "m4a", "flac", "ogg"):
            path = audio_dir / video["id"] / f"{scene['id']}.{extension}"
            if path.exists():
                return path
    return None


def make_audio(video, audio_dir, music, target, ffmpeg, ffprobe):
    inputs, chains, labels = [], [], []
    missing = []
    for i, scene in enumerate(video["scenes"]):
        path = narration_path(audio_dir,video,scene)
        if path:
            actual = duration_of(path,ffprobe)
            if actual > scene["duration"]+0.15:
                raise ValueError(f"{path}: narration {actual:.2f}s exceeds scene {scene['duration']}s")
            scene["_caption_duration"] = min(actual,scene["duration"])
            inputs += ["-i",str(path)]
            chains.append(f"[{i}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,apad,atrim=duration={scene['duration']},asetpts=PTS-STARTPTS[a{i}]")
        else:
            missing.append(scene["id"])
            inputs += ["-f","lavfi","-t",str(scene["duration"]),"-i","anullsrc=r=48000:cl=stereo"]
            chains.append(f"[{i}:a]atrim=duration={scene['duration']},asetpts=PTS-STARTPTS[a{i}]")
        labels.append(f"[a{i}]")
    chains.append("".join(labels)+f"concat=n={len(labels)}:v=0:a=1[voice]")
    if music:
        music_index = len(labels)
        inputs += ["-stream_loop","-1","-i",str(music)]
        volume = 0.16 if len(missing) < len(video["scenes"]) else 0.55
        chains.append(f"[{music_index}:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,atrim=duration={video['duration']},volume={volume},afade=t=out:st={max(0,video['duration']-2)}:d=2[music]")
        chains.append("[voice][music]amix=inputs=2:duration=first:normalize=0,alimiter=limit=0.95[out]")
    else:
        chains.append("[voice]anull[out]")
    run([ffmpeg,"-hide_banner","-loglevel","error","-y",*inputs,"-filter_complex",";".join(chains),
         "-map","[out]","-t",str(video["duration"]),"-c:a","pcm_s16le",str(target)])
    return missing


def concat_quote(path):
    # FFmpeg's concat-file grammar has its own single-quote escaping.
    return "'" + str(path.resolve()).replace("'", "'\\''") + "'"


def render_video(video,evidence,output,audio_dir,music,ffmpeg,ffprobe,fps,resolution_scale=1.0,orientations=None,song=None):
    work = output/"sources"/video["id"]
    work.mkdir(parents=True,exist_ok=True)
    audio_target = work/"mixed.wav"
    use_song = song and (video.get("kind") in {"music","musical","trailer","music-trailer"} or video["id"] == "10-say-the-word")
    if use_song:
        run([ffmpeg,"-hide_banner","-loglevel","error","-y","-i",song,"-af",
             f"aresample=48000,apad,atrim=duration={video['duration']},afade=t=out:st={max(0,video['duration']-0.8)}:d=0.8",
             "-ac","2","-c:a","pcm_s16le",audio_target])
        missing = []
    else:
        missing = make_audio(video,audio_dir,music,audio_target,ffmpeg,ffprobe)
    write_captions(video,output/video["id"])
    records = []
    for orientation in orientations or video.get("orientations",["landscape"]):
        nominal = (1080,1920) if orientation == "portrait" else (1920,1080)
        width,height = (max(2,round(d*resolution_scale/2)*2) for d in nominal)
        composer = Composer(width,height)
        frames_dir = work/orientation
        frames_dir.mkdir(exist_ok=True)
        concat_lines = []
        frame_no = 0
        thumbnail = None
        for index,scene in enumerate(video["scenes"]):
            slices = scene_slices(scene)
            for a,b,phase,phases,caption in slices:
                frame = composer.frame(video,scene,evidence,phase,phases,caption,index,len(video["scenes"]))
                path = frames_dir/f"{frame_no:04}.png"
                frame.save(path,optimize=False)
                concat_lines += [f"file {concat_quote(path)}", f"duration {b-a:.9f}"]
                frame_no += 1
            if thumbnail is None or index == 0:
                thumbnail = composer.frame(video,scene,evidence,phases-1,phases,"",index,len(video["scenes"]))
        concat_lines.append(f"file {concat_quote(path)}")
        concat = frames_dir/"frames.ffconcat"
        concat.write_text("ffconcat version 1.0\n"+"\n".join(concat_lines)+"\n")
        basename = f"{video['id']}-{orientation}"
        destination = output/f"{basename}.mp4"
        # The progress strip moves continuously, while diagrams/terminal evidence
        # reveal in discrete steps without rendering thousands of Python frames.
        progress_height = max(2,round(5*resolution_scale))
        filters = (f"[0:v]fps={fps},format=yuv420p[base];"
                   f"color=c=0x77E4B4:s={width}x{progress_height}:r={fps}:d={video['duration']}[bar];"
                   f"[base][bar]overlay=x='-W+W*t/{video['duration']}':y={height-progress_height}:shortest=1[out]")
        run([ffmpeg,"-hide_banner","-loglevel","error","-y","-f","concat","-safe","0","-i",concat,
             "-i",audio_target,"-filter_complex_threads","1","-filter_complex",filters,"-map","[out]","-map","1:a",
             "-t",str(video["duration"]),"-r",str(fps),"-c:v","libx264","-preset","ultrafast","-crf","21",
             "-threads","2","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-movflags","+faststart",destination])
        thumb = output/f"{basename}.jpg"
        thumbnail.save(thumb,quality=92)
        actual = duration_of(destination,ffprobe)
        if abs(actual-video["duration"]) > 0.2:
            raise RuntimeError(f"{destination}: duration {actual} differs from expected {video['duration']}")
        records.append({"id":video["id"],"title":video["title"],"orientation":orientation,"width":width,"height":height,
                        "duration":actual,"file":destination.name,"thumbnail":thumb.name,
                        "audio":"song" if use_song else ("narration-and-music" if music and not missing else "caption-led" if missing else "narration"),
                        "narration":"not-applicable" if use_song else "complete" if not missing else ("absent" if len(missing)==len(video["scenes"]) else "partial"),
                        "missing_narration_scenes":missing})
        print(f"Rendered {destination.name} ({actual:.2f}s, {width}×{height})",flush=True)
    return records


def write_gallery(output,records):
    cards = []
    for record in records:
        title = html.escape(record["title"])
        vid = html.escape(record["id"])
        cards.append(f'<article><h2>{title}</h2><p>{record["orientation"]} · {record["duration"]:g}s · {record["audio"]}</p>'
                     f'<video controls preload="metadata" poster="{record["thumbnail"]}"><source src="{record["file"]}" type="video/mp4">'
                     f'<track kind="captions" src="{vid}.vtt" srclang="en" label="English"></video>'
                     f'<p><a href="{record["file"]}">MP4</a> · <a href="{vid}.txt">Transcript</a> · <a href="{vid}.srt">SRT</a></p></article>')
    content = '<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
    content += '<title>Jiti launch films</title><style>body{background:#101521;color:#f4f5f8;font:16px system-ui;max-width:1400px;margin:40px auto;padding:0 24px}a{color:#77e4b4}main{display:grid;grid-template-columns:repeat(auto-fit,minmax(350px,1fr));gap:32px}article{background:#192232;padding:24px;border-radius:16px}video{width:100%;max-height:620px}p{color:#aab8ce}h2{font-size:22px}</style>'
    content += '<h1>Jiti · Grow an application by talking to it</h1><p>Local review copies. Diagrams are labelled; recorded output is traceable to <a href="evidence.json">saved execution evidence</a>. Captions are burned in and available separately.</p><main>'
    if (output/"audio"/"song.wav").exists():
        content += '<article><h2>Say the Word · original song</h2><p>60-second sung master</p><audio controls preload="metadata" src="audio/song.wav"></audio><p><a href="audio/song.wav">Vocal master WAV</a> · <a href="audio/instrumental.wav">Companion instrumental</a> · <a href="audio/trailer.wav">30-second trailer edit</a></p></article>'
    content += "".join(cards) + '</main></html>'
    (output/"index.html").write_text(content)


def merge_report(previous,current):
    """Retain prior deliverables only when both saved source inputs match."""
    keys = ("manifest_sha256","evidence_sha256")
    if any(previous.get(key) != current.get(key) for key in keys):
        return current,False
    replacement_keys = {(record["id"],record["orientation"]) for record in current["outputs"]}
    retained = [record for record in previous.get("outputs",[])
                if (record["id"],record["orientation"]) not in replacement_keys]
    merged = dict(current)
    merged["outputs"] = sorted(retained+current["outputs"],key=lambda item:(item["id"],item["orientation"]))
    return merged,True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest",type=Path,default=ROOT/"launch"/"manifest.json")
    parser.add_argument("--evidence",type=Path,required=True,help="Saved execution evidence: {sections:{id:{lines:[...]}}}")
    parser.add_argument("--output",type=Path,default=ROOT/"artifacts"/"launch")
    parser.add_argument("--audio-dir",type=Path,help="Narration at VIDEO_ID/SCENE_ID.wav or .mp3")
    parser.add_argument("--music",type=Path,help="Instrumental audio bed; looped to each film's duration")
    parser.add_argument("--song",type=Path,help="Complete vocal song edit for the music trailer; replaces its narration and bed")
    parser.add_argument("--only",action="append",help="Render only this video id (repeatable)")
    parser.add_argument("--orientation",choices=["landscape","portrait"],help="Override manifest orientations")
    parser.add_argument("--scale",type=float,default=1.0,help="Use a smaller scale for draft review; default 1 is 1080p")
    parser.add_argument("--validate-only",action="store_true",help="Check the manifest and evidence without producing files")
    args = parser.parse_args(argv)
    manifest_text, evidence_text = args.manifest.read_text(), args.evidence.read_text()
    manifest,evidence = json.loads(manifest_text),json.loads(evidence_text)
    validate_manifest(manifest,evidence)
    if args.validate_only:
        print(f"Validated {len(manifest['videos'])} videos and {len(evidence.get('sections',{}))} evidence sections")
        return 0
    if not 0 < args.scale <= 1:
        parser.error("--scale must be greater than 0 and at most 1")
    videos = [video for video in manifest["videos"] if not args.only or video["id"] in args.only]
    if args.only and set(args.only)-{video["id"] for video in videos}:
        parser.error("--only contains unknown video ids")
    ffmpeg,ffprobe = locate_binary("ffmpeg"),locate_binary("ffprobe")
    args.output.mkdir(parents=True,exist_ok=True)
    # Keep exact inputs alongside rendered deliverables so every claim can be audited.
    (args.output/"manifest.json").write_text(manifest_text)
    (args.output/"evidence.json").write_text(evidence_text)
    records = []
    for video in videos:
        records += render_video(video,evidence,args.output,args.audio_dir,args.music,ffmpeg,ffprobe,
                                manifest.get("fps",24),args.scale,[args.orientation] if args.orientation else None,args.song)
    result = {"manifest_sha256":hashlib.sha256(manifest_text.encode()).hexdigest(),
              "evidence_sha256":hashlib.sha256(evidence_text.encode()).hexdigest(),"outputs":records}
    report_path = args.output/"render-report.json"
    if report_path.exists() and (args.only or args.orientation):
        result,merged = merge_report(read_json(report_path),result)
        if not merged:
            print("Source hashes changed; gallery includes only this render, excluding older output files.",file=sys.stderr)
    report_path.write_text(json.dumps(result,indent=2)+"\n")
    write_gallery(args.output,result["outputs"])
    print(f"Review gallery: {args.output/'index.html'}",flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError,RuntimeError,subprocess.CalledProcessError) as exc:
        print(f"render: {exc}",file=sys.stderr)
        raise SystemExit(1)
