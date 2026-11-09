#!/usr/bin/env python3
"""Step 3 — one Remotion render → publish master + chat preview + QA sheets.

  python3 scripts/reel/render.py <episode-id> [--stills 0,300,1500]

  out/<ep>_master.mp4    1080×1920 H.264/AAC, loudness −14 LUFS (video stream copied, not re-encoded)
  out/<ep>_preview.mp4   ≤ 28 MB, 720×1280 — quick re-encode of the master, no second render
  out/<ep>_sheet.jpg     one frame every 4 s   ┐ look at these before sending
  out/<ep>_first20.jpg   first 20 s, 1 fps     ┘
--stills renders only the given frames (seconds of work) for a look before the full render.
"""
import argparse, json, os, re, subprocess, sys, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import preset as P

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "out"


def render_concurrency() -> int:
    """Remotion opens one headless Chrome tab per worker: too many for the memory = the render gets killed.
    REEL_CONCURRENCY overrides; otherwise min(CPU cores, ~1 worker per 1.5 GB of available memory)."""
    env = os.environ.get("REEL_CONCURRENCY")
    if env and env.isdigit() and int(env) > 0:
        return int(env)
    cores = os.cpu_count() or 4
    try:
        mem = {k: int(v.split()[0]) for k, v in (l.split(":", 1) for l in open("/proc/meminfo"))}
        gb = mem.get("MemAvailable", mem.get("MemTotal", 8 * 2**20)) / 2**20
        try:  # a container memory limit is lower than the host's
            lim = open("/sys/fs/cgroup/memory.max").read().strip()
            gb = min(gb, int(lim) / 2**30) if lim.isdigit() else gb
        except OSError:
            pass
        return max(1, min(cores, int(gb / 1.5)))
    except Exception:
        return min(cores, 4)


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, cwd=ROOT, **kw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ep")
    ap.add_argument("--stills", help="comma-separated frame numbers: render stills only")
    args = ap.parse_args()
    props = ROOT / "public" / f"{args.ep}.props.json"
    OUT.mkdir(exist_ok=True)
    cpus = str(render_concurrency())

    if args.stills:
        run(["node", "scripts/reel/stills.mjs", args.ep, args.stills])
        return

    t0 = time.time()
    raw = OUT / f"{args.ep}_raw.mp4"
    run(["npx", "remotion", "render", "src/index.ts", "MultiClip", str(raw), f"--props={props}", "--codec=h264",
         "--crf=16", "--x264-preset=veryfast", "--jpeg-quality=95", "--audio-codec=aac", "--audio-bitrate=256k", f"--concurrency={cpus}", "--log=error"])
    t1 = time.time()

    # loudness: measure, then linear normalisation; video stream is copied
    meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(raw), "-vn", "-af", P.LOUDNESS + ":print_format=json", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    m = json.loads(meas[meas.rindex("{"): meas.rindex("}") + 1])
    ln = (f"{P.LOUDNESS}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
          f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    master = OUT / f"{args.ep}_master.mp4"
    # the output rate is an OUTPUT option (-ar): loudnorm emits 192 kHz, and an «aresample» right after it inside the
    # same filter makes ffmpeg 5.1 (Debian — the Docker image) fail with «Error reinitializing filters»
    run(["ffmpeg", "-y", "-v", "error", "-i", str(raw), "-af", ln, "-ar", "48000", "-c:v", "copy",
         "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(master)])
    raw.unlink()

    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(master)],
                               capture_output=True, text=True).stdout)
    vkbps = int(P.PREVIEW_MAX_MB * 8 * 1024 / dur - 96)
    preview = OUT / f"{args.ep}_preview.mp4"
    common = ["-vf", f"scale={P.PREVIEW_W}:{P.PREVIEW_H}:flags=lanczos", "-c:v", "libx264", "-preset", "faster",
              "-b:v", f"{vkbps}k", "-passlogfile", str(OUT / f".{args.ep}_2pass")]
    run(["ffmpeg", "-y", "-v", "error", "-i", str(master), *common, "-pass", "1", "-an", "-f", "mp4", "/dev/null"])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(master), *common, "-pass", "2", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", "-c:a", "aac", "-b:a", "96k", str(preview)])
    for f in OUT.glob(f".{args.ep}_2pass*"):
        f.unlink()

    run(["ffmpeg", "-y", "-v", "error", "-i", str(master), "-vf", "fps=1/4,scale=180:320,tile=11x4", "-frames:v", "1",
         str(OUT / f"{args.ep}_sheet.jpg")])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(master), "-vf", "fps=1,scale=216:384,tile=10x2", "-frames:v", "1",
         str(OUT / f"{args.ep}_first20.jpg")])
    t2 = time.time()
    mb = lambda p: p.stat().st_size / 1024 / 1024
    print(f"render {t1 - t0:.0f}s, master+preview+QA {t2 - t1:.0f}s")
    print(f"master : {master} ({mb(master):.0f} MB, {dur:.1f}s, {m['input_i']} → -14 LUFS)")
    print(f"preview: {preview} ({mb(preview):.1f} MB)")


if __name__ == "__main__":
    main()
