#!/usr/bin/env python3
"""Promo ad, step 2 — one Remotion render → master + chat preview + QA sheet.

  python3 scripts/promo/render.py <promo-id> [--stills 0,120,300]   (frames)

  out/<id>_master.mp4   1080×1920 H.264/AAC, −14 LUFS (video stream copied)
  out/<id>_preview.mp4  ≤ 28 MB 720×1280 re-encode of the master (only if the master is bigger)
  out/<id>_sheet.jpg    one frame per second
"""
import argparse, json, os, shutil, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import preset as P

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"


def run(cmd):
    subprocess.run(cmd, check=True, cwd=ROOT)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("id")
    ap.add_argument("--stills")
    args = ap.parse_args()
    props = ROOT / "public" / f"{args.id}.promo.json"
    OUT.mkdir(exist_ok=True)
    if args.stills:
        run(["node", "scripts/promo/stills.mjs", args.id, args.stills])
        return

    raw = OUT / f"{args.id}_raw.mp4"
    run(["npx", "remotion", "render", "src/index.ts", P.COMPOSITION, str(raw), f"--props={props}", "--codec=h264",
         "--crf=15", "--x264-preset=medium", "--jpeg-quality=95", "--audio-codec=aac", "--audio-bitrate=256k",
         f"--concurrency={os.cpu_count() or 4}", "--log=error"])
    master = OUT / f"{args.id}_master.mp4"
    has_audio = json.loads(props.read_text()).get("audio")
    if has_audio:
        meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(raw), "-vn", "-af", P.LOUDNESS + ":print_format=json", "-f", "null", "-"],
                              capture_output=True, text=True).stderr
        m = json.loads(meas[meas.rindex("{"): meas.rindex("}") + 1])
        ln = (f"{P.LOUDNESS}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
              f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
        run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af", ln + ",aresample=48000", "-c:v", "copy",
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(master)])
    else:
        run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-c", "copy", "-movflags", "+faststart", str(master)])
    raw.unlink()

    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(master)],
                               capture_output=True, text=True).stdout)
    preview = OUT / f"{args.id}_preview.mp4"
    if master.stat().st_size <= P.PREVIEW_MAX_MB * 1024 * 1024:
        shutil.copy(master, preview)
    else:
        vk = int(P.PREVIEW_MAX_MB * 8 * 1024 / dur - 128)
        run(["ffmpeg", "-y", "-v", "error", "-i", str(master), "-vf", f"scale={P.PREVIEW_W}:{P.PREVIEW_H}:flags=lanczos",
             "-c:v", "libx264", "-preset", "slow", "-b:v", f"{vk}k", "-maxrate", f"{vk * 2}k", "-bufsize", f"{vk * 2}k",
             "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(preview)])
    n = int(dur) + 1
    run(["ffmpeg", "-y", "-v", "error", "-i", str(master), "-vf", f"fps=1,scale=216:384,tile={(n + 1) // 2}x2", "-frames:v", "1",
         str(OUT / f"{args.id}_sheet.jpg")])
    mb = lambda p: p.stat().st_size / 1024 / 1024
    print(f"master : {master} ({mb(master):.1f} MB, {dur:.2f}s)")
    print(f"preview: {preview} ({mb(preview):.1f} MB)")


if __name__ == "__main__":
    main()
