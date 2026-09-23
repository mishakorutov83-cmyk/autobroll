#!/usr/bin/env python3
"""Step 1 of the interview-reel pipeline — analysis only, nothing is upscaled.

  python3 scripts/reel/prepare.py <google-drive-url | video file> <episode-id>

Writes work/<ep>/:
  source.<ext>       the original, untouched
  audio.wav          16 kHz mono for analysis
  rms.npy            10 ms loudness envelope (cut snapping)
  transcript.json    segments + word-level timestamps
  transcript.txt     readable "[start-end] text" lines — read this to build the story
  faces.json         face boxes, 4 fps (framing)
  meta.json          source size / fps / duration
Transcription and face detection run in parallel.
"""
import json, os, re, subprocess, sys, threading, time, wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import preset as P

ROOT = Path(__file__).resolve().parents[2]
MODELS = Path(os.environ.get("REEL_MODELS", Path.home() / ".cache" / "autobroll"))


def sh(*a, **kw):
    return subprocess.run(a, check=True, **kw)


def fetch(src: str, work: Path) -> Path:
    existing = sorted(work.glob("source.*"))
    if existing:
        return existing[0]
    if re.match(r"https?://", src):
        m = re.search(r"/d/([\w-]+)|id=([\w-]+)", src)
        fid = m.group(1) or m.group(2) if m else None
        out = work / "source.mp4"
        sh("gdown", fid if fid else src, "-O", str(out), "-q")
        return out
    out = work / ("source" + Path(src).suffix.lower())
    os.symlink(Path(src).resolve(), out)
    return out


def probe(path: Path) -> dict:
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                                   "stream=width,height,r_frame_rate:stream_tags=rotate:stream_side_data=rotation:format=duration",
                                   "-of", "json", str(path)], capture_output=True, text=True, check=True).stdout)
    s = j["streams"][0]
    w, h = s["width"], s["height"]
    rot = abs(int(float((s.get("tags") or {}).get("rotate", 0) or next((d.get("rotation", 0) for d in s.get("side_data_list", [])), 0))))
    if rot in (90, 270):
        w, h = h, w
    n, d = s["r_frame_rate"].split("/")
    return {"width": w, "height": h, "fps": float(n) / float(d), "duration": float(j["format"]["duration"])}


def transcribe(work: Path, model_name: str, prompt: str):
    from faster_whisper import WhisperModel

    t0 = time.time()
    model = WhisperModel(model_name, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4,
                         download_root=str(MODELS / "whisper"))
    # sequential decoding on purpose: the batched/VAD mode is faster but drops the host's
    # short reactions («Супер», «Да-да») and hallucinated on the ep1 benchmark
    segs, _ = model.transcribe(str(work / "audio.wav"), language="ru", word_timestamps=True, beam_size=5,
                               vad_filter=False, initial_prompt=prompt or None)
    out = [{"start": s.start, "end": s.end, "text": s.text.strip(),
            "words": [{"w": w.word, "s": w.start, "e": w.end, "p": w.probability} for w in s.words]} for s in segs]
    json.dump(out, open(work / "transcript.json", "w"), ensure_ascii=False)
    with open(work / "transcript.txt", "w") as f:
        for s in out:
            f.write(f"[{s['start']:7.2f}-{s['end']:7.2f}] {s['text']}\n")
    print(f"transcript: {len(out)} segments in {time.time() - t0:.0f}s ({model_name})", flush=True)


def faces(work: Path, src: Path, meta: dict):
    import cv2

    t0 = time.time()
    # decode a small 4 fps copy through ffmpeg — cheap even for 4K sources
    w = 360
    h = int(round(meta["height"] * w / meta["width"] / 2) * 2)
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(src), "-vf", f"fps=4,scale={w}:{h}", "-f", "rawvideo",
                             "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    det = cv2.FaceDetectorYN.create(str(MODELS / "yunet.onnx"), "", (w, h), 0.6, 0.3, 5000)
    out, i = [], 0
    while True:
        buf = proc.stdout.read(w * h * 3)
        if len(buf) < w * h * 3:
            break
        _, fs = det.detect(np.frombuffer(buf, np.uint8).reshape(h, w, 3))
        fl = [[float(x[0]) / w, float(x[1]) / h, float(x[2]) / w, float(x[3]) / h, float(x[14])] for x in (fs if fs is not None else [])]
        out.append({"t": i / 4, "faces": fl})
        i += 1
    json.dump(out, open(work / "faces.json", "w"))
    print(f"faces: {len(out)} samples in {time.time() - t0:.0f}s", flush=True)


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    src_arg, ep = sys.argv[1], sys.argv[2]
    prompt = sys.argv[3] if len(sys.argv) > 3 else "Интервью. Ресторан «Наше место», Китай, Гуанчжоу, Фошань."
    work = ROOT / "work" / ep
    work.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    src = fetch(src_arg, work)
    meta = probe(src)
    json.dump(meta, open(work / "meta.json", "w"))
    print(f"source: {meta['width']}x{meta['height']} {meta['fps']:.2f}fps {meta['duration']:.0f}s", flush=True)

    sh("ffmpeg", "-y", "-v", "error", "-i", str(src), "-ac", "1", "-ar", "16000", str(work / "audio.wav"))
    wv = wave.open(str(work / "audio.wav"))
    a = np.frombuffer(wv.readframes(wv.getnframes()), np.int16).astype(np.float32) / 32768
    n = len(a) // 160
    np.save(work / "rms.npy", np.sqrt((a[: n * 160].reshape(n, 160) ** 2).mean(1)))

    model = os.environ.get("REEL_WHISPER", P.WHISPER_MODEL)
    jobs = [threading.Thread(target=transcribe, args=(work, model, prompt))]
    if not (work / "faces.json").exists():
        jobs.append(threading.Thread(target=faces, args=(work, src, meta)))
    for j in jobs:
        j.start()
    for j in jobs:
        j.join()
    print(f"prepare done in {time.time() - t0:.0f}s → {work}/transcript.txt")


if __name__ == "__main__":
    main()
