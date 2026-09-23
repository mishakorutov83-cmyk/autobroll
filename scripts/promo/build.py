#!/usr/bin/env python3
"""Promo ad, step 1 — cut + prepare the chosen fragments and write the Remotion props.

  python3 scripts/promo/build.py <promo-id> <source-video> [--no-media]

--no-media: only rewrite the props (framing keys / texts changed, fragments and speeds unchanged).

Reads promos/<promo-id>/spec.py:
  CLIPS  — [dict(src=(start, end), speed=1.0, keys=[(src_t, fx, fy, zoom), …])]
           keys are in SOURCE seconds; (fx, fy) = point of the source frame (0..1) put at the
           window centre, zoom 1 = source width fills the window. Clamped so no empty edges.
  AUDIO  — dict(mode="bed", src_start=0.0) continuous source sound under the cuts, or mode="none"
  GRADE  — optional ffmpeg filter for colour
  FRAME  — texts / colours for the static frame (see src/promo/PromoAd.tsx)
Writes public/promo/<id>/clipN.mp4, audio.m4a and public/<id>.promo.json.
"""
import importlib.util, json, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import preset as P

ROOT = Path(__file__).resolve().parents[2]


def run(cmd):
    subprocess.run(cmd, check=True, cwd=ROOT)


def probe(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                          "-show_entries", "format=duration", "-of", "json", str(path)], capture_output=True, text=True, check=True)
    j = json.loads(out.stdout)
    return j["streams"][0]["width"], j["streams"][0]["height"], float(j["format"]["duration"])


def load_spec(pid):
    path = ROOT / "promos" / pid / "spec.py"
    spec = importlib.util.spec_from_file_location("spec", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    pid, src = sys.argv[1], Path(sys.argv[2]).resolve()
    media = "--no-media" not in sys.argv
    S = load_spec(pid)
    sw, sh, sdur = probe(src)
    mh = round(P.MEZZ_W * sh / sw / 2) * 2
    out = ROOT / "public" / "promo" / pid
    out.mkdir(parents=True, exist_ok=True)
    grade = getattr(S, "GRADE", "")
    xfade = getattr(S, "XFADE", P.XFADE)

    clips, t = [], 0.0
    for i, c in enumerate(S.CLIPS):
        a, b = c["src"]
        sp = c.get("speed", 1.0)
        dur = (b - a) / sp
        f = out / f"clip{i}.mp4"
        vf = [f"setpts=(PTS-STARTPTS)/{sp}"]
        if sp < 1 and P.SMOOTH_SLOWMO:
            vf.append(f"minterpolate=fps={P.FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1")
        else:
            vf.append(f"fps={P.FPS}")
        vf += [f"scale={P.MEZZ_W}:{mh}:flags=lanczos", P.SHARPEN] + ([grade] if grade else []) + ["format=yuv420p"]
        if media:
            run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(src), "-an",
                 "-vf", ",".join(vf), "-c:v", "libx264", "-preset", "slow", "-crf", str(P.MEZZ_CRF), "-g", "15", str(f)])
        keys = [dict(t=(k[0] - a) / sp, fx=k[1], fy=k[2], zoom=k[3]) for k in c.get("keys", [(a, .5, .5, 1.0)])]
        start = t - (xfade if i else 0)
        clips.append(dict(src=f"promo/{pid}/{f.name}", start=round(start, 3), dur=round(dur, 3),
                          xfade=xfade if i else 0, aspect=mh / P.MEZZ_W, keys=keys))
        t = start + dur
    total = t
    print(f"video: {len(clips)} fragments, {total:.2f}s")

    audio = None
    A = getattr(S, "AUDIO", dict(mode="bed", src_start=0.0))
    if A.get("mode") == "bed":
        a0 = A.get("src_start", 0.0)
        length = min(total, sdur - a0)
        fo = A.get("fade_out", P.FADE_OUT + 0.2)
        af = f"afade=t=in:d=0.12,afade=t=out:st={length - fo:.3f}:d={fo:.3f},aresample=48000"
        audio = out / "audio.m4a"
        if media:
            run(["ffmpeg", "-y", "-v", "error", "-ss", f"{a0:.3f}", "-t", f"{length:.3f}", "-i", str(src), "-vn",
                 "-af", af, "-c:a", "aac", "-b:a", "256k", str(audio)])

    props = dict(fps=P.FPS, durationSec=round(total, 3), window=getattr(S, "WINDOW", P.WINDOW), clips=clips,
                 audio=f"promo/{pid}/audio.m4a" if audio else None, fadeOut=getattr(S, "FADE_OUT", P.FADE_OUT),
                 frame=S.FRAME)
    pj = ROOT / "public" / f"{pid}.promo.json"
    pj.write_text(json.dumps(props, ensure_ascii=False, indent=1))
    print(f"props: {pj}")


if __name__ == "__main__":
    main()
