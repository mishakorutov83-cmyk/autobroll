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


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, cwd=ROOT, **kw)


def ebur(path):
    err = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-vn", "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    tail = err[err.rindex("Summary:"):]
    return float(tail.split("I:")[1].split()[0]), float(tail.split("Peak:")[1].split()[0])


def master_audio(src_video, master, audio=None):
    """Copy the video stream; programme loudness −14 LUFS: gentle peak compression, static gain,
    limiter (≈ −1.5 dBTP). Gain is calibrated in two passes on a wav, so the limiter only
    touches rare peaks and the room tone never pumps."""
    tmp_in, tmp_out = OUT / ".m_in.wav", OUT / ".m_out.wav"
    run(["ffmpeg", "-y", "-v", "error", "-i", str(audio or src_video), "-vn", "-ac", "2", "-ar", "48000", str(tmp_in)])
    i_in, _ = ebur(tmp_in)
    chain = lambda g: (f"acompressor=threshold=-22dB:ratio=2.5:attack=4:release=120:makeup=1,"
                       f"volume={g:.2f}dB,alimiter=limit=0.80:attack=3:release=60:level=false")
    gain = -14.0 - i_in
    for _ in range(2):
        run(["ffmpeg", "-y", "-v", "error", "-i", str(tmp_in), "-af", chain(gain), str(tmp_out)])
        i_out, _ = ebur(tmp_out)
        if abs(i_out + 14.0) < 0.3:
            break
        gain += -14.0 - i_out
    ins = ["-i", str(src_video), "-i", str(tmp_out)]
    run(["ffmpeg", "-y", "-v", "error", *ins, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac",
         "-b:a", "192k", "-movflags", "+faststart", str(master)])
    tmp_in.unlink(); tmp_out.unlink()
    i_out, tp = ebur(master)
    return {"input_i": f"{i_in:.2f}", "output_i": f"{i_out:.2f}", "tp": f"{tp:.2f}"}


def finish(ep, master, m, t0, t1):
    """≤ 28 MB chat preview (re-encode of the master) + QA contact sheets."""
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(master)],
                               capture_output=True, text=True).stdout)
    vkbps = int(P.PREVIEW_MAX_MB * 8 * 1024 / dur - 96)
    preview = OUT / f"{ep}_preview.mp4"
    common = ["-vf", f"scale={P.PREVIEW_W}:{P.PREVIEW_H}:flags=lanczos", "-c:v", "libx264", "-preset", "faster",
              "-b:v", f"{vkbps}k", "-passlogfile", str(OUT / f".{ep}_2pass")]
    run(["ffmpeg", "-y", "-v", "error", "-i", str(master), *common, "-pass", "1", "-an", "-f", "mp4", "/dev/null"])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(master), *common, "-pass", "2", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", "-c:a", "aac", "-b:a", "96k", str(preview)])
    for f in OUT.glob(f".{ep}_2pass*"):
        f.unlink()

    run(["ffmpeg", "-y", "-v", "error", "-i", str(master), "-vf", "fps=1/4,scale=180:320,tile=11x4", "-frames:v", "1",
         str(OUT / f"{ep}_sheet.jpg")])
    run(["ffmpeg", "-y", "-v", "error", "-i", str(master), "-vf", "fps=1,scale=216:384,tile=10x2", "-frames:v", "1",
         str(OUT / f"{ep}_first20.jpg")])
    t2 = time.time()
    mb = lambda p: p.stat().st_size / 1024 / 1024
    print(f"render {t1 - t0:.0f}s, master+preview+QA {t2 - t1:.0f}s")
    print(f"master : {master} ({mb(master):.0f} MB, {dur:.1f}s, {m['input_i']} → {m['output_i']} LUFS, peak {m['tp']} dBTP)")
    print(f"preview: {preview} ({mb(preview):.1f} MB)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ep")
    ap.add_argument("--stills", help="comma-separated frame numbers: render stills only")
    ap.add_argument("--audio-only", action="store_true",
                    help="re-render just the soundtrack and swap it into the existing master (video untouched)")
    args = ap.parse_args()
    props = ROOT / "public" / f"{args.ep}.props.json"
    OUT.mkdir(exist_ok=True)
    cpus = str(os.cpu_count() or 4)

    if args.stills:
        run(["node", "scripts/reel/stills.mjs", args.ep, args.stills])
        return

    t0 = time.time()
    if args.audio_only:
        master = OUT / f"{args.ep}_master.mp4"
        wav, old = OUT / f"{args.ep}_audio.wav", OUT / f"{args.ep}_master_prev.mp4"
        run(["npx", "remotion", "render", "src/index.ts", "MultiClip", str(wav), f"--props={props}", "--codec=wav", "--log=error"])
        for d in Path("/tmp").glob("remotion-webpack-bundle-*"):
            subprocess.run(["rm", "-rf", str(d)])
        master.rename(old)
        m = master_audio(old, master, audio=wav)
        old.unlink(); wav.unlink()
        finish(args.ep, master, m, t0, time.time())
        return
    raw = OUT / f"{args.ep}_raw.mp4"
    run(["npx", "remotion", "render", "src/index.ts", "MultiClip", str(raw), f"--props={props}", "--codec=h264",
         "--crf=16", "--x264-preset=veryfast", "--jpeg-quality=95", "--audio-codec=aac", "--audio-bitrate=256k", f"--concurrency={cpus}", "--log=error"])
    t1 = time.time()
    # every render bundles a copy of public/ (clips!) into /tmp — drop it, or the disk fills up
    for d in Path("/tmp").glob("remotion-webpack-bundle-*"):
        subprocess.run(["rm", "-rf", str(d)])

    # loudness: static gain to −14 LUFS + a peak limiter (≈ −1.5 dBTP). loudnorm's "linear" mode
    # silently falls back to dynamic (pumping room tone) when the peaks don't allow the gain.
    master = OUT / f"{args.ep}_master.mp4"
    m = master_audio(raw, master)
    raw.unlink()

    finish(args.ep, master, m, t0, t1)


if __name__ == "__main__":
    main()
