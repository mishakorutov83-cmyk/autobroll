#!/usr/bin/env python3
"""Listen-through: ASR of every clip of the edit (restored selects audio, 1.0×) vs its caption.

  python3 scripts/reel/qa_listen.py <episode-id>

Prints per clip: caption words heard, where speech starts/ends inside the clip (a late first word
or an early last word = dead air; speech running to the clip end = possibly clipped word), the
caption and what was heard. Clips under ~1.5 s often hallucinate in isolation — recheck those in
context before acting on them.
"""
import difflib, json, re, subprocess, sys
from pathlib import Path

from faster_whisper import WhisperModel

ROOT = Path(__file__).resolve().parents[2]
ep = sys.argv[1]
P = json.load(open(ROOT / "public" / f"{ep}.props.json"))
wav = ROOT / "work" / ep / "sel_restored.wav"
if not wav.exists():
    wav = ROOT / "public" / "clips" / f"{ep}_sel.mp4"
caps = {}
for c in P["captions"]:
    caps.setdefault(c["clipId"], []).append(" ".join(w["text"] for w in c["words"]))
m = WhisperModel("large-v3", device="cpu", compute_type="int8", cpu_threads=4)
norm = lambda x: re.sub(r"[^а-яa-z0-9 ]", "", x.lower().replace("ё", "е")).split()
tot = hit = 0
tmp = ROOT / "work" / ep / "_qa.wav"
for c in P["clips"]:
    if c.get("muted"):
        continue
    subprocess.run(["ffmpeg", "-nostdin", "-y", "-v", "error", "-ss", str(c["inSec"]), "-to", str(c["outSec"]), "-i", str(wav),
                    "-vn", "-ar", "16000", "-ac", "1", str(tmp)], check=True)
    segs, _ = m.transcribe(str(tmp), language="ru", beam_size=5, condition_on_previous_text=False, word_timestamps=True)
    ws = [w for s in segs for w in s.words]
    heard = " ".join(w.word.strip() for w in ws)
    a, b = norm(" ".join(caps.get(c["id"], []))), norm(heard)
    h = sum(x.size for x in difflib.SequenceMatcher(None, a, b).get_matching_blocks())
    tot += len(a)
    hit += h
    edge = f"speech {ws[0].start:.2f}–{ws[-1].end:.2f} of {c['outSec'] - c['inSec']:.2f}s" if ws else "no speech"
    print(f"{c['id']:5} {h}/{len(a)}  {edge}\n   CAP: {' '.join(caps.get(c['id'], []))}\n   ASR: {heard}", flush=True)
tmp.unlink(missing_ok=True)
print(f"caption words heard {hit}/{tot} = {100 * hit / max(1, tot):.0f}%")
