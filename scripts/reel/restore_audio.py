#!/usr/bin/env python3
"""Dialogue restoration for phone-recorded interviews (approved on ep2, variant B).

  python3 scripts/reel/restore_audio.py <episode-id>      # after build.py, before render.py

  1. audio of the selected fragments straight from the ORIGINAL source (not the levelled selects)
  2. gentle dereverb (WPE) → DeepFilterNet3 speech enhancement, suppression capped at 18 dB
     (uncapped it ate word endings: ASR lost ~27 % of words on ep2)
  3. HPF 85 Hz, −3 dB @220 Hz (mud), +2.5 dB @3.2 kHz (presence), light de-ess,
     3:1 compression, voice levelling, limiter
  4. new audio muxed into public/clips/<ep>_sel_r.mp4 (video stream copied), props switched to it,
     host clips (shot subject edl.HOST_SIDE, default "L", or edl.HOST_CLIPS) gain-matched to the guest.
Speed/pitch stay in Remotion; loudness (−14 LUFS) is done by render.py.
The WPE/DeepFilterNet step runs in the isolated venv made by setup.sh (torch 2.2 + deepfilternet).
"""
import importlib.util, json, subprocess, sys, wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
VENV_PY = Path.home() / ".cache" / "autobroll" / "dfn-venv" / "bin" / "python"
DFN_LIMIT_DB = 18
POST = ("highpass=f=85:p=2,equalizer=f=220:t=q:w=1.0:g=-3,equalizer=f=3200:t=q:w=1.2:g=2.5,"
        "equalizer=f=6500:t=q:w=1.5:g=1.5,deesser=i=0.3,"
        "acompressor=threshold=-26dB:ratio=3:attack=8:release=160:makeup=3,"
        "dynaudnorm=f=400:g=15:p=0.9:m=6:r=0.4,alimiter=limit=0.89:level=false")

ENHANCE = r'''
import sys, numpy as np, soundfile as sf, torch
from nara_wpe.wpe import wpe
from nara_wpe.utils import stft, istft
from df.enhance import init_df, enhance
inp, out, lim, taps = sys.argv[1], sys.argv[2], float(sys.argv[3]), int(sys.argv[4])
x, sr = sf.read(inp, dtype="float64")
Y = stft(x[None], size=1024, shift=256).transpose(2, 0, 1)
z = istft(wpe(Y, taps=taps, delay=3, iterations=3, statistics_mode="full").transpose(1, 2, 0), size=1024, shift=256)[0][: len(x)]
z = (z / max(1.0, np.abs(z).max())).astype("float32")
model, state, _ = init_df()
y = enhance(model, state, torch.from_numpy(z)[None], atten_lim_db=lim)[0].numpy()
sf.write(out, y, sr, subtype="PCM_16")
'''


def sh(*a):
    subprocess.run(a, check=True)


def speech_level(x, sr, a, b):
    seg = x[int(a * sr):int(b * sr)]
    hop = sr // 50
    n = len(seg) // hop
    if n < 5:
        return None
    r = 20 * np.log10(np.sqrt((seg[: n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)
    return float(np.mean(r[r > np.percentile(r, 50)]))


def main():
    ep = sys.argv[1]
    work = ROOT / "work" / ep
    src = sorted(work.glob("source.*"))[0]
    ranges = json.load(open(work / "selects_ranges.json"))
    spec = importlib.util.spec_from_file_location("edl", work / "edl.py")
    edl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(edl)

    # 1. original audio of the selects ranges (same trims as build.py)
    cmd, fc = ["ffmpeg", "-y", "-v", "error"], []
    for i, (a, b) in enumerate(ranges):
        d = round((b - a) * 30) / 30
        cmd += ["-ss", f"{a:.3f}", "-t", f"{d + 0.5:.3f}", "-i", str(src)]
        fc.append(f"[{i}:a]aresample=48000,apad,atrim=0:{d:.4f},asetpts=N/SR/TB[a{i}]")
    fc.append("".join(f"[a{i}]" for i in range(len(ranges))) + f"concat=n={len(ranges)}:v=0:a=1,pan=mono|c0=0.5*c0+0.5*c1[ca]")
    raw, enh, fin = work / "sel_raw_mono.wav", work / "sel_enh.wav", work / "sel_restored.wav"
    sh(*cmd, "-filter_complex", ";".join(fc), "-map", "[ca]", "-c:a", "pcm_s16le", str(raw))

    # 2. WPE + DeepFilterNet3 (isolated venv)
    script = work / "_enhance.py"
    script.write_text(ENHANCE)
    # per-episode tuning (edl.AUDIO): dfn_db (suppression cap), wpe_taps (dereverb strength), post (ffmpeg chain)
    cfg = getattr(edl, "AUDIO", {})
    sh(str(VENV_PY), str(script), str(raw), str(enh), str(cfg.get("dfn_db", DFN_LIMIT_DB)), str(cfg.get("wpe_taps", 10)))
    script.unlink()

    # 3. post chain
    post_tmp = work / "sel_post.wav"
    sh("ffmpeg", "-y", "-v", "error", "-i", str(enh), "-af", cfg.get("post", POST), str(post_tmp))
    # static gain to a sane working level (−20 LUFS): a very quiet track would otherwise go through
    # AAC at −40 LUFS and get +26 dB at mastering, lifting codec noise with it
    meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(post_tmp), "-af", "ebur128", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    li = float(meas[meas.rindex("I:"):].split()[1])
    sh("ffmpeg", "-y", "-v", "error", "-i", str(post_tmp), "-af", f"volume={-20 - li:.2f}dB,alimiter=limit=0.95:level=false", str(fin))
    post_tmp.unlink()

    # 4. mux + props
    sel = ROOT / "public" / "clips" / f"{ep}_sel.mp4"
    sel_r = ROOT / "public" / "clips" / f"{ep}_sel_r.mp4"
    sh("ffmpeg", "-y", "-v", "error", "-i", str(sel), "-i", str(fin), "-map", "0:v", "-map", "1:a", "-c:v", "copy",
       "-c:a", "aac", "-b:a", "256k", "-ac", "2", "-ar", "48000", str(sel_r))
    props_path = ROOT / "public" / f"{ep}.props.json"
    props = json.load(open(props_path))
    shots = getattr(edl, "SHOTS", {})
    hs = getattr(edl, "HOST_SIDE", "L")   # side of the source frame the host sits on
    gs = {"L": "R", "R": "L"}[hs]
    host = set(getattr(edl, "HOST_CLIPS", [])) | {r[0] for r in edl.E if isinstance(r[3], str) and shots.get(r[3], (0, None))[1] == hs}
    guest = {r[0] for r in edl.E if isinstance(r[3], str) and shots.get(r[3], (0, None))[1] == gs} - host
    w = wave.open(str(fin))
    x = np.frombuffer(w.readframes(w.getnframes()), np.int16).astype(float) / 32768
    sr = w.getframerate()
    lv = lambda ids: [v for c in props["clips"] if c["id"] in ids
                      for v in [speech_level(x, sr, c["inSec"], c["outSec"])] if v is not None]
    gain = 1.0
    if host and guest and lv(host) and lv(guest):
        diff = float(np.median(lv(guest)) - np.median(lv(host)))
        gain = 10 ** (max(-4.0, min(4.0, diff)) / 20)
    for c in props["clips"]:
        c["src"] = f"clips/{ep}_sel_r.mp4"
        if c["id"] in host:
            c["volume"] = round(gain, 3)
    json.dump(props, open(props_path, "w"), ensure_ascii=False, indent=1)
    print(f"restored audio → {sel_r.name}; host clips {len(host)} × {20 * np.log10(gain):+.1f} dB")


if __name__ == "__main__":
    main()
