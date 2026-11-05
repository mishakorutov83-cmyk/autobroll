"""Stage 1 — analyse raw footage. No decisions here, only facts for the brain.

For every source file (local path or Google Drive link) writes work/agent/<proj>/s<i>/:
  source.*        the original (symlink or download)
  meta.json       size / fps / duration
  audio.wav       16 kHz mono, rms.npy — 10 ms loudness (cut snapping)
  words.json      transcript segments with word timings
  faces.json      face boxes 4 fps (framing, talking-head vs product shots)
  sheet_*.jpg     contact sheets, one frame every SHEET_STEP s, labelled "s<i> <sec>" — the brain's eyes
and the render proxy public/agent/<proj>/s<i>.mp4 (1080×1920, 30 fps, H.264, levelled audio).
"""
from __future__ import annotations

import json, os, subprocess, sys, threading, time, wave
from pathlib import Path

import numpy as np

from .config import MODELS, ROOT, SHEET_COLS, SHEET_ROWS, SHEET_STEP, WHISPER_MODEL, proj_dirs

sys.path.insert(0, str(ROOT / "scripts" / "reel"))
import prepare as R  # noqa: E402  (fetch / probe / faces are shared with the interview pipeline)
import preset as P  # noqa: E402


def transcribe(work: Path, language: str, prompt: str | None):
    from faster_whisper import WhisperModel

    t0 = time.time()
    wv = wave.open(str(work / "audio.wav"))
    audio = np.frombuffer(wv.readframes(wv.getnframes()), np.int16).astype(np.float32) / 32768
    model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4,
                         download_root=str(MODELS / "whisper"))
    # the decoded array is passed directly: newer PyAV builds break faster-whisper's own file decoding
    segs, _ = model.transcribe(audio, language=language, word_timestamps=True, beam_size=5,
                               vad_filter=False, initial_prompt=prompt or None)
    out = [{"start": round(s.start, 2), "end": round(s.end, 2), "text": s.text.strip(),
            "words": [{"w": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2), "p": round(w.probability, 2)}
                      for w in s.words]} for s in segs]
    json.dump(out, open(work / "words.json", "w"), ensure_ascii=False)
    print(f"  {work.name}: transcript {len(out)} segments, {time.time() - t0:.0f}s", flush=True)


def proxy(src: Path, dst: Path):
    t0 = time.time()
    dst.parent.mkdir(parents=True, exist_ok=True)
    vf = f"fps={P.FPS},scale={P.W}:{P.H}:force_original_aspect_ratio=increase:flags=lanczos,crop={P.W}:{P.H},setsar=1,format=yuv420p"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", vf, "-af", P.AUDIO_FILTER + ",aresample=48000",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-g", str(P.FPS), "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", str(dst)], check=True)
    print(f"  {dst.name}: proxy {time.time() - t0:.0f}s", flush=True)


def sheets(work: Path, src: Path, idx: int, meta: dict):
    """Contact sheets for the brain: a labelled frame every SHEET_STEP seconds."""
    import cv2

    w, h = 180, 320
    per = SHEET_COLS * SHEET_ROWS
    p = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(src), "-vf",
                          f"fps=1/{SHEET_STEP},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}",
                          "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    frames = []
    while True:
        buf = p.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        f = np.frombuffer(buf, np.uint8).reshape(h, w, 3).copy()
        label = f"s{idx} {len(frames) * SHEET_STEP:.1f}"
        cv2.rectangle(f, (0, 0), (w, 26), (0, 0, 0), -1)
        cv2.putText(f, label, (5, 19), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA)
        frames.append(f)
    for old in work.glob("sheet_*.jpg"):
        old.unlink()
    for n in range(0, len(frames), per):
        chunk = frames[n:n + per] + [np.zeros((h, w, 3), np.uint8)] * (per - len(frames[n:n + per]))
        rows = [np.hstack(chunk[r * SHEET_COLS:(r + 1) * SHEET_COLS]) for r in range(SHEET_ROWS)]
        cv2.imwrite(str(work / f"sheet_{n // per:02d}.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 80])
    print(f"  {work.name}: {len(frames)} frames → {-(-len(frames) // per)} sheets", flush=True)


def blacks(work: Path, src: Path):
    """black / empty frames — the brain must not show them"""
    err = subprocess.run(["ffmpeg", "-v", "info", "-i", str(src), "-vf", "scale=270:-2,blackdetect=d=0.05:pix_th=0.1", "-an",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    import re

    spans = [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", err)]
    json.dump(spans, open(work / "black.json", "w"))


def ingest(proj: str, inputs: list[str], language: str = "ru", prompt: str | None = None):
    work, pub = proj_dirs(proj)
    work.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    sources = []
    for i, arg in enumerate(inputs):
        sw = work / f"s{i}"
        sw.mkdir(exist_ok=True)
        src = R.fetch(arg, sw)
        meta = R.probe(src)
        json.dump(meta, open(sw / "meta.json", "w"))
        print(f"s{i}: {meta['width']}x{meta['height']} {meta['fps']:.0f}fps {meta['duration']:.1f}s  ← {arg}", flush=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-ac", "1", "-ar", "16000", str(sw / "audio.wav")], check=True)
        wv = wave.open(str(sw / "audio.wav"))
        a = np.frombuffer(wv.readframes(wv.getnframes()), np.int16).astype(np.float32) / 32768
        n = len(a) // 160
        np.save(sw / "rms.npy", np.sqrt((a[: n * 160].reshape(n, 160) ** 2).mean(1)))

        jobs = [threading.Thread(target=transcribe, args=(sw, language, prompt)),
                threading.Thread(target=proxy, args=(src, pub / f"s{i}.mp4")),
                threading.Thread(target=sheets, args=(sw, src, i, meta)),
                threading.Thread(target=blacks, args=(sw, src))]
        if not (sw / "faces.json").exists():
            jobs.append(threading.Thread(target=R.faces, args=(sw, src, meta)))
        for j in jobs:
            j.start()
        for j in jobs:
            j.join()
        sources.append({"index": i, "input": arg, **meta})
    json.dump({"project": proj, "sources": sources}, open(work / "project.json", "w"), ensure_ascii=False, indent=1)
    print(f"ingest done in {time.time() - t0:.0f}s → {work}")


def describe(proj: str) -> tuple[str, list[Path]]:
    """Text summary of the footage for the brain + the contact-sheet images."""
    work, _ = proj_dirs(proj)
    pj = json.load(open(work / "project.json"))
    lines, images = [], []
    for s in pj["sources"]:
        sw = work / f"s{s['index']}"
        segs = json.load(open(sw / "words.json"))
        faces = json.load(open(sw / "faces.json"))
        lines.append(f"## Source s{s['index']}: {s['width']}x{s['height']}, {s['duration']:.1f} s")
        # where a face is on screen (talking head) vs not (product / b-roll), 1 s resolution
        sec = {}
        for f in faces:
            big = any(z[2] > 0.08 for z in f["faces"])
            sec.setdefault(int(f["t"]), []).append(big)
        face_s = [k for k, v in sorted(sec.items()) if sum(v) >= len(v) / 2]
        runs, start, prev = [], None, None
        for k in face_s:
            if start is None:
                start = prev = k
            elif k == prev + 1:
                prev = k
            else:
                runs.append((start, prev + 1))
                start = prev = k
        if start is not None:
            runs.append((start, prev + 1))
        black = json.load(open(sw / "black.json")) if (sw / "black.json").exists() else []
        if black:
            lines.append("Black / empty frames (never show): " + ", ".join(f"{a:.2f}-{b:.2f}s" for a, b in black))
        lines.append("Face on screen (talking head): " + (", ".join(f"{a}-{b}s" for a, b in runs) or "never"))
        lines.append("Transcript (segment [start-end], then every word as word@start):")
        for g in segs:
            lines.append(f"[{g['start']:.2f}-{g['end']:.2f}] {g['text']}")
            lines.append("   " + " ".join(f"{w['w']}@{w['s']:.2f}" for w in g["words"]))
        images += sorted(sw.glob("sheet_*.jpg"))
    return "\n".join(lines), images
