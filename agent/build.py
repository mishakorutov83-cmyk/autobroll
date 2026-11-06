"""Stage 3 — an edit plan → Remotion props (public/<name>.props.json).

Snaps every cut to the quiet point next to the word boundary, frames talking heads by the
face track, maps the plan's captions onto real word timings, adds hook / label / end titles.
"""
from __future__ import annotations

import difflib, json, re
from pathlib import Path

import numpy as np
import yaml

from .config import ROOT, proj_dirs
from .brain import load_template
from .plan import EditPlan

import sys

sys.path.insert(0, str(ROOT / "scripts" / "reel"))
import preset as P  # noqa: E402

FPS = P.FPS
NEXT = {"N": "M", "M": "C", "C": "M", "push": "C"}
norm = lambda x: re.sub(r"[^а-яa-z0-9]", "", x.lower().replace("ё", "е"))
fr = lambda x: round(x * FPS) / FPS


class Source:
    def __init__(self, work: Path, idx: int):
        sw = work / f"s{idx}"
        self.meta = json.load(open(sw / "meta.json"))
        self.words = []
        for seg in json.load(open(sw / "words.json")):
            for w in seg["words"]:
                if w["w"].startswith("-") and self.words:  # «какой» + «-то»
                    self.words[-1] = {**self.words[-1], "w": self.words[-1]["w"] + w["w"], "e": w["e"]}
                else:
                    self.words.append(dict(w))
        rms = np.load(sw / "rms.npy")
        self.db = 20 * np.log10(np.convolve(rms, np.ones(3) / 3, mode="same") + 1e-6)
        faces = json.load(open(sw / "faces.json"))
        self.face_t = np.array([f["t"] for f in faces]) if faces else np.array([-99.0])
        self.faces = faces
        sw_, sh_ = self.meta["width"], self.meta["height"]
        k = max(P.W / sw_, P.H / sh_)  # proxy = cover-scale + centre crop
        self.dw, self.dh = sw_ * k, sh_ * k

    def snap(self, t: float, before: bool) -> float:
        a, b = (t - 0.22, t + 0.04) if before else (t - 0.04, t + 0.28)
        i0, i1 = max(0, int(a * 100)), min(len(self.db), int(b * 100))
        if i1 <= i0:
            return t
        seg = self.db[i0:i1]
        cand = np.where(seg <= seg.min() + 2.5)[0]
        return (i0 + (cand.max() if before else cand.min())) / 100

    def face(self, a: float, b: float):
        """median face centre in proxy coordinates (0..1), or None for product / b-roll shots"""
        pts = []
        for f in self.faces:
            if a <= f["t"] <= b:
                good = [z for z in f["faces"] if z[2] > 0.08]
                if good:
                    x, y, w, h, _ = max(good, key=lambda z: z[2])
                    pts.append((((x + w / 2) * self.dw - (self.dw - P.W) / 2) / P.W,
                                ((y + h / 2) * self.dh - (self.dh - P.H) / 2) / P.H))
        n = sum(1 for f in self.faces if a <= f["t"] <= b) or 1
        if len(pts) < n * 0.5:
            return None
        return float(np.median([p[0] for p in pts])), float(np.median([p[1] for p in pts]))


def transform(scale: float, face) -> tuple[float, float]:
    if face is None:
        return 0.0, 0.0
    ox, oy = face
    lim = (scale - 1) / 2
    tx = np.clip(0.5 + (ox - 0.5) * P.FACE_KEEP_X - (0.5 + (ox - 0.5) * scale), -lim, lim)
    ty = np.clip(P.FACE_TARGET_Y - (0.5 + (oy - 0.5) * scale), -lim, lim)
    return round(float(tx) * 100, 2), round(float(ty) * 100, 2)


def caption_pages(cid, text, accents, words, ia, ob, max_chars, top, plain=False):
    """corrected caption text → timed pages (≤ 2 lines), aligned to the transcript's words.
    plain: creator style — no trailing dots/commas on screen, numbers and prices always accented"""
    toks = text.split()
    ww = [w for w in words if ia - 0.25 <= w["s"] < ob - 0.02]
    A, B = [norm(t) for t in toks], [norm(w["w"]) for w in ww]
    tim = [None] * len(toks)
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, A, B, autojunk=False).get_opcodes():
        if op == "equal" or (op == "replace" and i2 - i1 == j2 - j1):
            for k in range(i2 - i1):
                w = ww[j1 + k]
                tim[i1 + k] = (max(w["s"], ia), min(w["e"], ob))
    k = 0
    while k < len(toks):  # unmatched words: spread evenly between their matched neighbours
        if tim[k] is not None:
            k += 1
            continue
        run = k
        while run < len(toks) and tim[run] is None:
            run += 1
        p = next((tim[j][1] for j in range(k - 1, -1, -1) if tim[j]), ia)
        nx = tim[run][0] if run < len(toks) else ob
        step = (nx - p) / (run - k)
        for n, j in enumerate(range(k, run)):
            tim[j] = (p + n * step, p + (n + 1) * step)
        k = run
    pages, cur = [], []
    for k, t in enumerate(toks):
        cur.append(k)
        chars = sum(len(toks[j]) + 1 for j in cur)
        nxt = toks[k + 1] if k + 1 < len(toks) else None
        if nxt is None or (re.search(r"[.?!]$", t) and chars > 8) or chars + len(nxt) + 1 > max_chars \
                or (re.search(r"[,»:—]$", t) and chars > 18):
            pages.append(cur)
            cur = []
    out = []
    shown = [re.sub(r"[.,;:]+$", "", t) if plain else t for t in toks]
    for pi, p in enumerate(pages):
        words_ = [{"text": shown[j], "startMs": round(tim[j][0] * 1000), "endMs": round(tim[j][1] * 1000),
                   "accent": toks[j] in accents or (plain and bool(re.search(r"\d", toks[j])))} for j in p]
        out.append({"id": f"{cid}_{pi}", "clipId": cid, "words": words_, "startMs": max(round(ia * 1000), words_[0]["startMs"] - 60),
                    "endMs": words_[-1]["endMs"], "topPct": top})
    return out


def build(proj: str, plan: EditPlan, template: str) -> Path:
    work, _ = proj_dirs(proj)
    tpl = yaml.safe_load(load_template(template))
    sizes = {**{"N": P.N, "M": P.M, "C": P.C}, **(tpl.get("cutting", {}).get("shot_sizes") or {})}
    cap = dict(tpl.get("captions", {}))
    if plan.style.caption_style != "template":  # the human's brief asked for another caption look
        cap["preset"] = {"plain": "plain", "clean": "clean", "pop": "default"}[plan.style.caption_style]
    srcs: dict[int, Source] = {}
    clips, captions, titles = [], [], []
    for c in plan.clips:
        s = srcs.setdefault(c.source, Source(work, c.source))
        ia = fr(max(0.0, s.snap(c.start, True) - 0.02))
        ob = fr(min(s.meta["duration"] - 0.05, s.snap(c.end, False) + 0.04))
        if ob - ia < 0.3:
            raise ValueError(f"{plan.id}/{c.id}: clip too short after snapping ({c.start}-{c.end})")
        face = s.face(ia, ob)
        base = sizes["N"] if c.shot == "push" else sizes[c.shot]
        z = plan.style.zoom_bias
        kfs = []
        if c.shot == "push":
            for t, sc in ((ia, sizes["N"]), (ob, sizes["M"])):
                kfs.append({"t": t, "scale": round(sc * z, 4), **dict(zip("xy", transform(sc * z, face)))})
        else:
            kfs.append({"t": ia, "scale": round(base * z, 4), **dict(zip("xy", transform(base * z, face)))})
            if c.punch_at and ia + 0.5 < c.punch_at < ob - 0.5:
                sc = sizes[NEXT[c.shot]] * z
                kfs.append({"t": fr(c.punch_at) - 1 / FPS, **{k: v for k, v in kfs[0].items() if k != "t"}})
                kfs.append({"t": fr(c.punch_at), "scale": round(sc, 4), **dict(zip("xy", transform(sc, face)))})
        clips.append({"id": c.id, "src": f"agent/{proj}/s{c.source}.mp4", "label": (c.caption or c.id)[:28],
                      "inSec": ia, "outSec": ob, "sourceDurationSec": round(s.meta["duration"], 3), "transform": kfs,
                      "volume": 0 if c.muted else 1, "muted": c.muted, "speed": plan.speed})
        if c.caption and not c.muted:
            captions += caption_pages(c.id, c.caption, c.accents, s.words, ia, ob,
                                      cap.get("max_chars", P.CAPTION_MAX_CHARS), plan.style.caption_top,
                                      plain=cap.get("preset") == "plain")

    ids = {c["id"] for c in clips}
    byid = {c["id"]: c for c in clips}
    brolls = []
    for i, x in enumerate(plan.inserts):
        c = byid.get(x.clip_id)
        if not c:
            continue
        a, b = max(x.at, c["inSec"]), min(x.at + x.duration, c["outSec"])
        if b - a < 0.3:
            continue
        brolls.append({"id": f"i{i}", "clipId": x.clip_id, "startMs": round(a * 1000), "endMs": round(b * 1000),
                       "kind": "video", "mode": "pip" if x.mode == "pip" else "fullscreen", "src": f"agent/{proj}/s{x.source}.mp4",
                       "fromSec": round(x.from_time, 3), "fade": False})
    for i, o in enumerate(plan.overlays):
        if o.clip_id in ids:
            titles.append({"id": f"o{i}", "kind": o.kind, "clipId": o.clip_id, "offsetSec": max(0, o.offset),
                           "durationSec": o.duration, "title": o.text})
    end = tpl.get("end_card")
    if end and clips:
        last = clips[-1]
        dur = (last["outSec"] - last["inSec"]) / last["speed"]
        sec = min(end.get("seconds", 3), dur)
        titles.append({"id": "end", "kind": "end", "clipId": last["id"], "offsetSec": round(dur - sec, 3),
                       "durationSec": sec, "title": end["title"], "subtitle": end.get("subtitle", "")})

    props = {"clips": clips, "music": None, "captions": captions, "brolls": brolls, "accentColor": plan.style.accent,
             "captionPreset": cap.get("preset", "clean"), "titles": titles}
    name = f"agent_{proj}_{plan.id}"
    out = ROOT / "public" / f"{name}.props.json"
    json.dump(props, open(out, "w"), ensure_ascii=False, indent=1)
    total = sum((c["outSec"] - c["inSec"]) / c["speed"] for c in clips)
    print(f"  {plan.id}: {len(clips)} clips, {len(captions)} caption pages, {len(titles)} titles, {len(brolls)} inserts, {total:.1f}s → {out.name}")
    return out
