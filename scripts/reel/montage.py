#!/usr/bin/env python3
"""Music / event montage (no interview): shots cut to a pre-mixed live-sound track.

  python3 scripts/reel/montage.py <ep>        # reads work/<ep>/montage.py, writes public/<ep>.props.json
  python3 scripts/reel/render.py <ep>         # then render as usual (master −14 LUFS + preview)

work/<ep>/montage.py defines
  SOURCES = {"a": "raw/file.mp4", ...}           # paths relative to work/<ep>
  GRADE   = "eq=saturation=1.2:contrast=1.05"     # ffmpeg colour grade for every proxy (optional)
  SHOTS   = [dict(src, t_in, dur, speed=1, zoom=(s0, s1), focus=(fx, fy), kick=0, flash=False), ...]
            sequential on the timeline; dur = timeline seconds; speed 0.5 = slow motion
            (120 fps sources are proxied at 60 fps so 0.5× stays smooth)
  AUDIO   = [(src, t_in, dur), ...]               # sequential live-sound segments, 60 ms crossfades
  POPS    = [(t_timeline, dur, title, subtitle, top%, tilt), ...]
  END     = (title, subtitle, dur)                # end card over the last shot
All clips are muted in the composition; the mix plays as the props' music track.
"""
import importlib.util, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FPS = 30


def probe_fps(p):
    r = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=r_frame_rate",
                        "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout.strip()
    a, b = r.split("\n")[0].strip(",").split("/")
    return float(a) / float(b)


def main():
    ep = sys.argv[1]
    work = ROOT / "work" / ep
    spec = importlib.util.spec_from_file_location("m", work / "montage.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    clips_dir = ROOT / "public" / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    grade = getattr(m, "GRADE", "")

    # 1. graded proxies (only the sources used), native size, 30 or 60 fps
    rel = {}
    for k, path in m.SOURCES.items():
        src = work / path
        out = clips_dir / f"{ep}_{k}.mp4"
        rel[k] = f"clips/{ep}_{k}.mp4"
        if out.exists() and "--reencode" not in sys.argv:
            continue
        fps = 60 if probe_fps(src) > 45 else 30
        vf = f"fps={fps}" + (f",{grade}" if grade else "") + ",format=yuv420p"
        subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-i", str(src), "-vf", vf, "-an", "-c:v", "libx264",
                        "-preset", "veryfast", "-crf", "16", "-g", str(fps), str(out)], check=True)
        print(f"proxy {k}: {fps} fps")

    # 2. live-sound mix: sequential segments with short crossfades (ends padded so durations add up)
    X = 0.06
    cmd, fc = ["ffmpeg", "-nostdin", "-y", "-v", "error"], []
    for i, (k, t, d) in enumerate(m.AUDIO):
        cmd += ["-ss", f"{max(0, t - X / 2):.3f}", "-t", f"{d + X + 0.5:.3f}", "-i", str(work / m.SOURCES[k])]
        fc.append(f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{d + X:.4f},asetpts=N/SR/TB[a{i}]")
    chain = "[a0]"
    for i in range(1, len(m.AUDIO)):
        fc.append(f"{chain}[a{i}]acrossfade=d={X}:c1=tri:c2=tri[x{i}]")
        chain = f"[x{i}]"
    total = sum(s["dur"] for s in m.SHOTS)
    end_dur = getattr(m, "END", (None, None, 0))[2]
    fc.append(f"{chain}highpass=f=40,afade=t=in:d=0.08,afade=t=out:st={total - max(1.5, end_dur):.3f}:d={max(1.5, end_dur):.3f},"
              f"apad,atrim=0:{total:.4f}[mix]")
    mix = clips_dir / f"{ep}_mix.wav"
    subprocess.run(cmd + ["-filter_complex", ";".join(fc), "-map", "[mix]", "-c:a", "pcm_s16le", str(mix)], check=True)
    audio_len = sum(d for _, _, d in m.AUDIO)
    if abs(audio_len - total) > 0.05:
        print(f"WARNING: audio {audio_len:.2f}s vs picture {total:.2f}s")

    # 3. clips with zoom/focus keyframes
    clips, starts, t = [], [], 0.0
    for i, s in enumerate(m.SHOTS):
        sp = s.get("speed", 1)
        a, b = s["t_in"], s["t_in"] + s["dur"] * sp
        s0, s1 = s.get("zoom", (1.0, 1.0))
        fx, fy = s.get("focus", (0.5, 0.5))

        def kf(tt, sc):
            lim = (sc - 1) / 2 * 100
            x = max(-lim, min(lim, -(fx - 0.5) * sc * 100))
            y = max(-lim, min(lim, -(fy - 0.5) * sc * 100))
            return {"t": round(tt, 3), "scale": round(sc, 4), "x": round(x, 2), "y": round(y, 2)}

        c = {"id": f"s{i}", "src": rel[s["src"]], "label": f"{s['src']} {a:.1f}", "inSec": round(a, 3), "outSec": round(b, 3),
             "sourceDurationSec": 9999, "transform": [kf(a, s0), kf(b, s1)], "volume": 0, "muted": True, "speed": sp}
        if s.get("kick"):
            c["kick"] = s["kick"]
        clips.append(c)
        starts.append(t)
        t += s["dur"]

    def at(tt):  # timeline time → (clip id, offset)
        for i, st in enumerate(starts):
            if tt < st + m.SHOTS[i]["dur"] or i == len(starts) - 1:
                return f"s{i}", round(tt - st, 3)

    titles = []
    for i, s in enumerate(m.SHOTS):
        if s.get("flash"):
            titles.append({"id": f"fl{i}", "kind": "flash", "clipId": f"s{i}", "offsetSec": 0, "durationSec": 0.2, "title": ""})
    for i, (tt, d, ti, sub, top, tilt) in enumerate(getattr(m, "POPS", [])):
        cid, off = at(tt)
        titles.append({"id": f"pop{i}", "kind": "pop", "clipId": cid, "offsetSec": off, "durationSec": d, "title": ti,
                       "subtitle": sub, "topPct": top, "tilt": tilt})
    if hasattr(m, "END"):
        ti, sub, d = m.END
        cid, off = at(total - d)
        titles.append({"id": "end", "kind": "end", "clipId": cid, "offsetSec": off, "durationSec": d, "title": ti, "subtitle": sub})
    props = {"clips": clips, "music": {"src": f"clips/{ep}_mix.wav", "volume": 1, "startSec": 0, "fadeOutSec": 0},
             "captions": [], "brolls": [], "accentColor": "#F2C14E", "captionPreset": "clean", "titles": titles}
    json.dump(props, open(ROOT / "public" / f"{ep}.props.json", "w"), ensure_ascii=False, indent=1)
    print(f"montage: {len(clips)} shots, {total:.1f}s → public/{ep}.props.json")


if __name__ == "__main__":
    main()
