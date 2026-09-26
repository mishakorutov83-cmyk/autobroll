#!/usr/bin/env python3
"""Step 2 — turn the episode's edit list into an AutoBroll/Remotion project.

  python3 scripts/reel/build.py <episode-id> [--check] [--speed 1.15]

Reads work/<ep>/edl.py (written per interview — see docs/episodes/ep1/edl.py for
the format) plus the analysis files from prepare.py, then:
  1. snaps every cut to the quiet point next to the word boundary,
  2. encodes ONLY the selected fragments (+ small handles) from the original:
     cover-scale to 1080×1920, gentle audio levelling → public/clips/<ep>_sel.mp4,
  3. writes public/<ep>.props.json: clips (speed, face-tracked keyframes,
     punch-ins), captions (corrected text on word timings), lower-third, end card,
  4. prints the joints worth a listen; --check transcribes just those.
"""
import argparse, difflib, importlib.util, json, re, subprocess, sys, time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import preset as P

ROOT = Path(__file__).resolve().parents[2]
FPS = P.FPS


def load_edl(path: Path):
    spec = importlib.util.spec_from_file_location("edl", path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def fr(x):
    return round(x * FPS) / FPS


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ep")
    ap.add_argument("--check", action="store_true", help="transcribe only the flagged joints")
    ap.add_argument("--speed", type=float, help="override SPEED (1.0 / 1.10 / 1.15 / 1.20)")
    ap.add_argument("--no-media", action="store_true", help="skip re-encoding the selects file")
    args = ap.parse_args()
    t_start = time.time()

    work = ROOT / "work" / args.ep
    edl = load_edl(work / "edl.py")
    meta = json.load(open(work / "meta.json"))
    src = sorted(work.glob("source.*"))[0]
    speed = args.speed or getattr(edl, "SPEED", P.SPEED)
    # shot code → (scale, subject). Subject None = largest face; "L"/"R" = left/right person,
    # "both" = centre of the pair. An episode can add its own codes (e.g. virtual cameras
    # on a static two-shot) via SHOTS = {"W": (1.45, "both"), "G": (1.9, "R")}.
    shots = {"N": (P.N, None), "M": (P.M, None), "C": (P.C, None), **getattr(edl, "SHOTS", {})}
    min_face = getattr(edl, "FACE_MIN_W", 0.12)

    T = json.load(open(work / "transcript.json"))
    WORDS = []
    for seg in T:
        for w in seg["words"]:
            if w["w"].startswith("-") and WORDS:  # "какой" + "-то"
                WORDS[-1] = {**WORDS[-1], "w": WORDS[-1]["w"] + w["w"], "e": w["e"]}
            else:
                WORDS.append(dict(w))
    FACES = json.load(open(work / "faces.json"))
    rms = np.load(work / "rms.npy")
    db = 20 * np.log10(np.convolve(rms, np.ones(3) / 3, mode="same") + 1e-6)

    # ---- cut snapping: quiet point right before / after the words ------------------------
    def snap(t, before):
        a, b = (t - 0.22, t + 0.04) if before else (t - 0.04, t + 0.28)
        i0, i1 = max(0, int(a * 100)), min(len(db), int(b * 100))
        seg = db[i0:i1]
        cand = np.where(seg <= seg.min() + 2.5)[0]
        return (i0 + (cand.max() if before else cand.min())) / 100

    # ---- framing: cover-scale geometry + face track --------------------------------------
    sw, sh = meta["width"], meta["height"]
    if sw / sh > P.W / P.H:
        dh, dw = P.H, int(round(sw * P.H / sh / 2) * 2)
    else:
        dw, dh = P.W, int(round(sh * P.W / sw / 2) * 2)
    face_t = np.array([f["t"] for f in FACES])

    # ---- zoom cap: never stretch the source more than the face detail allows ------------
    widths = [max(z[2] for z in f["faces"]) * sw for f in FACES if f["faces"]]
    face_px = float(np.median(widths)) if widths else 0.0
    max_mag = P.MAX_MAG_SMALL_FACE if face_px < P.FACE_DETAIL_PX else P.MAX_MAG
    # LAYOUT = "split": stacked panels (top → bottom = PANELS subjects), for landscape sources
    # whose 9:16 full-frame crop alone would already exceed the magnification cap
    split = getattr(edl, "LAYOUT", None) == "split"
    panel_who = getattr(edl, "PANELS", ["R", "L"])
    PW, PH = P.W, (P.H - 4 * (len(panel_who) - 1)) / len(panel_who)
    pk = max(PW / sw, PH / sh)
    pdw, pdh = sw * pk, sh * pk
    zoom_cap = max_mag / (pk if split else dw / sw)
    if zoom_cap < 1:
        print(f"WARNING: a full-frame 9:16 crop already stretches this {sw}x{sh} source ×{dw / sw:.2f} "
              f"(> ×{max_mag}); consider LAYOUT = 'split' in edl.py")
        zoom_cap = 1.0
    capped = {code: (sc, who) for code, (sc, who) in shots.items()
              if isinstance(sc, (int, float)) and sc > zoom_cap + 1e-6}
    if capped:
        print(f"zoom cap: faces ≈{face_px:.0f}px in a {sw}px source → max ×{max_mag} "
              f"(shot scale ≤ {zoom_cap:.2f}); capped: " + ", ".join(f"{c} {v[0]}" for c, v in capped.items()))
    clamp = lambda v: min(v, zoom_cap)

    def face_at(t, who=None):
        i = int(np.argmin(np.abs(face_t - t)))
        if abs(face_t[i] - t) > 0.13:
            return None
        good = [(x + w / 2, y + h / 2, w) for x, y, w, h, _ in FACES[i]["faces"] if w > min_face and y + h / 2 < 0.5]
        if not good:
            return None
        if who is None:
            return max(good, key=lambda z: z[2])[:2]
        left = [g for g in good if g[0] < 0.5]
        right = [g for g in good if g[0] >= 0.5]
        L = max(left, key=lambda z: z[2])[:2] if left else None
        R = max(right, key=lambda z: z[2])[:2] if right else None
        if who == "L":
            return L
        if who == "R":
            return R
        return ((L[0] + R[0]) / 2, (L[1] + R[1]) / 2) if L and R else None

    def track(a, b, who=None):
        ts = np.arange(a, b + 0.001, 0.25)
        pts = [face_at(t, who) for t in ts]
        valid = [i for i, p in enumerate(pts) if p]
        if not valid:
            return ts, np.full(len(ts), 0.5), np.full(len(ts), 0.27)
        xs = np.array([pts[min(valid, key=lambda v: abs(v - i))][0] for i in range(len(ts))])
        ys = np.array([pts[min(valid, key=lambda v: abs(v - i))][1] for i in range(len(ts))])
        k = 7
        sm = lambda v: np.convolve(np.pad(v, k // 2, mode="edge"), np.ones(k) / k, mode="valid")
        return ts, sm(xs), sm(ys)

    def xf_panel(s, cx, cy):
        ox = (cx * pdw - (pdw - PW) / 2) / PW
        oy = (cy * pdh - (pdh - PH) / 2) / PH
        lim = (s - 1) / 2
        tx = np.clip(0.5 + (ox - 0.5) * P.FACE_KEEP_X - (0.5 + (ox - 0.5) * s), -lim, lim)
        ty = np.clip(getattr(edl, "PANEL_FACE_Y", 0.40) - (0.5 + (oy - 0.5) * s), -lim, lim)
        return round(float(tx) * 100, 2), round(float(ty) * 100, 2)

    def xf(s, cx, cy):
        ox = (cx * dw - (dw - P.W) / 2) / P.W
        oy = (cy * dh - (dh - P.H) / 2) / P.H
        lim = (s - 1) / 2
        tx = np.clip(0.5 + (ox - 0.5) * P.FACE_KEEP_X - (0.5 + (ox - 0.5) * s), -lim, lim)
        ty = np.clip(P.FACE_TARGET_Y - (0.5 + (oy - 0.5) * s), -lim, lim)
        return round(float(tx) * 100, 2), round(float(ty) * 100, 2)

    # ---- 1. resolve cut points (source time) ---------------------------------------------
    OVR = getattr(edl, "OVR", {})
    cuts = []
    for row in edl.E:
        cid, a, b = row[0], row[1], row[2]
        ia, ob = max(0, snap(a, True) - 0.02), snap(b, False) + 0.04
        o = OVR.get(cid, (None, None))
        ia = o[0] if o[0] is not None else ia
        ob = o[1] if o[1] is not None else ob
        cuts.append((fr(ia), fr(ob)))
    outro = getattr(edl, "OUTRO", None)  # muted tail under the end card
    if outro:
        cuts.append((fr(outro[0]), fr(outro[1])))

    # ---- 2. selects file: only the chosen fragments --------------------------------------
    ranges = []
    for ia, ob in sorted(cuts):
        a, b = fr(max(0, ia - P.HANDLE)), fr(min(meta["duration"] - 0.05, ob + P.HANDLE))
        if ranges and a <= ranges[-1][1] + 0.5:
            ranges[-1][1] = max(ranges[-1][1], b)
        else:
            ranges.append([a, b])
    offs, acc = [], 0.0
    for a, b in ranges:
        offs.append(acc)
        acc += round((b - a) * FPS) / FPS

    def to_sel(t):
        for (a, b), o in zip(ranges, offs):
            if a - 1e-6 <= t <= b + 1e-6:
                return round((o + t - a) * FPS) / FPS
        raise ValueError(f"time {t} outside selects")

    sel_rel = f"clips/{args.ep}_sel.mp4"
    sel_path = ROOT / "public" / sel_rel
    ranges_file = work / "selects_ranges.json"
    if args.no_media and not ranges_file.exists():
        print("warning: selects built before range tracking — assuming they match the edit list")
    elif args.no_media and json.load(open(ranges_file)) != ranges:
        sys.exit("cut points moved outside the encoded selects — rebuild without --no-media")
    if not args.no_media:
        t0 = time.time()
        sel_path.parent.mkdir(parents=True, exist_ok=True)
        cmd = ["ffmpeg", "-y", "-v", "error"]
        fc = []
        upscale = dw > sw
        for i, (a, b) in enumerate(ranges):
            d = round((b - a) * FPS) / FPS
            cmd += ["-ss", f"{a:.3f}", "-t", f"{d + 0.5:.3f}", "-i", str(src)]
            fc.append(f"[{i}:v]fps={FPS},tpad=stop_mode=clone:stop=15,trim=end_frame={round(d * FPS)},setpts=N/{FPS}/TB[v{i}]")
            fc.append(f"[{i}:a]aresample=48000,apad,atrim=0:{d:.4f},asetpts=N/SR/TB[a{i}]")
        fc.append("".join(f"[v{i}][a{i}]" for i in range(len(ranges))) + f"concat=n={len(ranges)}:v=1:a=1[cv][ca]")
        # split panels only need the panel's cover size, not a full 9:16 cover (half the pixels)
        ew, eh = (int(round(pdw / 2) * 2), int(round(pdh / 2) * 2)) if split else (dw, dh)
        if sh >= 1000 and ew > sw:
            # HD source: keep native pixels — a 1080p landscape frame pre-stretched to a 9:16
            # cover (3413×1920) only bloats the file and the render cache; Chrome scales it
            ew, eh = sw - sw % 2, sh - sh % 2
        upscale = ew > sw
        vf = f"scale={ew}:{eh}:flags=lanczos" + (",unsharp=5:5:0.5:5:5:0.0" if upscale else "") + ",setsar=1,format=yuv420p"
        fc.append(f"[cv]{vf}[vo]")
        fc.append(f"[ca]{P.AUDIO_FILTER}[ao]")
        cmd += ["-filter_complex", ";".join(fc), "-map", "[vo]", "-map", "[ao]", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "15", "-g", str(FPS), "-c:a", "aac", "-b:a", "192k", str(sel_path)]
        subprocess.run(cmd, check=True)
        json.dump(ranges, open(ranges_file, "w"))
        print(f"selects: {len(ranges)} ranges, {acc:.0f}s of {meta['duration']:.0f}s source, {time.time() - t0:.0f}s", flush=True)

    # ---- 3. clips + captions -------------------------------------------------------------
    norm = lambda x: re.sub(r"[^а-яa-z0-9]", "", x.lower().replace("ё", "е"))
    clips, captions, flags = [], [], []
    rows = list(edl.E) + ([("outro", outro[0], outro[1], "N", None, [], None)] if outro else [])
    for (cid, a, b, shot, text, acc_words, punch), (ia, ob) in zip(rows, cuts):
        shot, who = shots[shot] if isinstance(shot, str) else (shot, None)
        punch = (punch[0], *(shots[punch[1]] if isinstance(punch[1], str) else (punch[1], who))) if punch else None
        tracks = {w: track(ia, ob, w) for w in {who, punch[2] if punch else who}}

        def scale_at(t):
            if isinstance(shot, tuple):
                return clamp(shot[0] + (shot[1] - shot[0]) * (t - ia) / max(0.01, ob - ia))
            return clamp(punch[1] if punch and t >= punch[0] else shot)

        def who_at(t):
            return punch[2] if punch and t >= punch[0] else who

        kts = sorted(set([round(t, 3) for t in np.arange(ia, ob + 0.001, 0.5)] + [ob] +
                         ([round(punch[0] - 1 / FPS, 3), round(punch[0], 3)] if punch else [])))
        # landscape source, single-person shot: slide the 9:16 window to the subject
        # (objectPosition), then track/zoom inside that window as usual
        focus_off = (dw - P.W) / 2
        clip_focus = None
        if not split and dw > P.W * 1.2 and who in ("L", "R"):
            if punch and punch[2] != who:
                flags.append((cid, "punch changes the subject on a landscape source — use a separate clip"))
            ts0, xs0, _ = tracks[who]
            want = float(np.median(xs0)) * dw - P.W / 2
            focus_off = float(np.clip(want, 0, dw - P.W))
            clip_focus = round(100 * focus_off / (dw - P.W), 2)

        def xf_f(s_, cx, cy):
            ox = (cx * dw - focus_off) / P.W
            oy = (cy * dh - (dh - P.H) / 2) / P.H
            lim = (s_ - 1) / 2
            tx = np.clip(0.5 + (ox - 0.5) * P.FACE_KEEP_X - (0.5 + (ox - 0.5) * s_), -lim, lim)
            ty = np.clip(P.FACE_TARGET_Y - (0.5 + (oy - 0.5) * s_), -lim, lim)
            return round(float(tx) * 100, 2), round(float(ty) * 100, 2)

        kfs = []
        for t in kts:
            tq = punch[0] - 0.5 if punch and abs(t - (punch[0] - 1 / FPS)) < 1e-3 else t
            ts, xs, ys = tracks[who_at(tq)]
            i = int(np.argmin(np.abs(ts - t)))
            s = scale_at(tq)
            x, y = xf_f(s, xs[i], ys[i])
            kfs.append({"t": to_sel(t), "scale": round(s, 4), "x": x, "y": y})
        panels = None
        if split:
            panels = []
            for pw_ in panel_who:
                ts_, xs_, ys_ = track(ia, ob, pw_)
                pk_ = []
                for t in kts:
                    tq = punch[0] - 0.5 if punch and abs(t - (punch[0] - 1 / FPS)) < 1e-3 else t
                    i = int(np.argmin(np.abs(ts_ - t)))
                    sc_ = scale_at(tq)
                    x, y = xf_panel(sc_, xs_[i], ys_[i])
                    pk_.append({"t": to_sel(t), "scale": round(sc_, 4), "x": x, "y": y})
                panels.append(pk_)
        clip = {"id": cid, "src": sel_rel, "label": (text or cid)[:28], "inSec": to_sel(ia), "outSec": to_sel(ob),
                "sourceDurationSec": round(acc, 3), "transform": kfs, "volume": 1,
                "speed": 1 if text is None else speed}
        if clip_focus is not None:
            clip["focusX"] = clip_focus
        if panels:
            clip["panels"] = panels
            clip["transform"] = []
        if text is None:
            clip["muted"] = True
        clips.append(clip)
        if not text:
            continue

        # words → caption tokens (corrected text), aligned by sequence matching
        ww = [w for w in WORDS if w["s"] >= a - 0.25 and w["s"] < b - 0.02]
        toks = text.split()
        A, B = [norm(t) for t in toks], [norm(w["w"]) for w in ww]
        tim = [None] * len(toks)
        sm = difflib.SequenceMatcher(None, A, B, autojunk=False)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == "equal" or (op == "replace" and i2 - i1 == j2 - j1):
                for k in range(i2 - i1):
                    w = ww[j1 + k]
                    tim[i1 + k] = (max(w["s"], ia), min(w["e"], ob))
        k = 0
        while k < len(toks):
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
            if any(norm(toks[j]) for j in range(k, run)):
                flags.append((cid, f"caption words not in transcript: {' '.join(toks[k:run])}"))
            k = run

        # joints worth a listen: cut inside a word, or low-confidence word at the edge
        for w in WORDS:
            if len(norm(w["w"])) < 3 or w["e"] - w["s"] > 0.9:  # short words / stretched (pause) timings
                continue
            if w["s"] + 0.12 < ia < w["e"] - 0.12 or w["s"] + 0.12 < ob < w["e"] - 0.12:
                flags.append((cid, f"cut inside word «{w['w'].strip()}» ({w['s']:.2f}-{w['e']:.2f})"))
        if ww and min(ww[0]["p"], ww[-1]["p"]) < 0.45:
            flags.append((cid, "low-confidence word at the edge"))

        # pages (≤ 2 lines)
        pages, cur = [], []
        for k, t in enumerate(toks):
            cur.append(k)
            chars = sum(len(toks[j]) + 1 for j in cur)
            nxt = toks[k + 1] if k + 1 < len(toks) else None
            if (nxt is None or (re.search(r"[.?!]$", t) and chars > 8) or chars + len(nxt or "") + 1 > P.CAPTION_MAX_CHARS
                    or (re.search(r"[,»]$", t) and chars > 20)):
                pages.append(cur)
                cur = []
        merged = []
        for p in pages:
            if merged and len(p) == 1 and sum(len(toks[j]) + 1 for j in merged[-1] + p) <= 36 \
                    and not re.search(r"[.?!]$", toks[merged[-1][-1]]):
                merged[-1] += p
            else:
                merged.append(p)
        for pi, p in enumerate(merged):
            words = [{"text": toks[j], "startMs": round(to_sel(tim[j][0]) * 1000), "endMs": round(to_sel(tim[j][1]) * 1000),
                      "accent": toks[j] in acc_words} for j in p]
            captions.append({"id": f"{cid}_{pi}", "clipId": cid, "words": words,
                             "startMs": max(round(to_sel(ia) * 1000), words[0]["startMs"] - 60),
                             "endMs": words[-1]["endMs"], "topPct": getattr(edl, "CAPTION_TOP_PCT", P.CAPTION_TOP_PCT)})

    # a cut between two fragments that end/start in the same framing reads as a jump
    prev = None
    for row in edl.E:
        cid, sh_, pu = row[0], row[3], row[6]
        st = shots[sh_] if isinstance(sh_, str) else (sh_, None)
        en = (shots[pu[1]] if isinstance(pu[1], str) else (pu[1], st[1])) if pu else st
        st = (clamp(st[0]) if not isinstance(st[0], tuple) else st[0], st[1])
        en = (clamp(en[0]) if not isinstance(en[0], tuple) else en[0], en[1])
        if prev and prev[1] == st:
            flags.append((cid, f"same framing as {prev[0]} across the cut — alternate the shot"))
        prev = (cid, en)

    titles = [{"id": "lt", "kind": "lower", "clipId": edl.LOWER_THIRD_CLIP, "offsetSec": P.LOWER_THIRD_OFFSET,
               "durationSec": P.LOWER_THIRD_DUR, "title": edl.GUEST,
               "subtitle": getattr(edl, "GUEST_SUB", P.LOWER_THIRD_SUB)}]
    if hasattr(edl, "LOWER_THIRD_TOP"):
        titles[0]["topPct"] = edl.LOWER_THIRD_TOP
    if outro:
        titles.append({"id": "end", "kind": "end", "clipId": "outro", "offsetSec": 0, "durationSec": P.END_DUR,
                       "title": P.END_TITLE, "subtitle": P.END_SUB})
    props = {"clips": clips, "music": None, "captions": captions, "brolls": [], "accentColor": P.ACCENT,
             "captionPreset": P.CAPTION_PRESET, "titles": titles}
    json.dump(props, open(ROOT / "public" / f"{args.ep}.props.json", "w"), ensure_ascii=False, indent=1)
    total = sum(round((c["outSec"] - c["inSec"]) / c["speed"] * FPS) for c in clips) / FPS
    print(f"project: {len(clips)} clips, {len(captions)} caption pages, {total // 60:.0f}:{total % 60:04.1f} at {speed}x "
          f"→ public/{args.ep}.props.json ({time.time() - t_start:.0f}s)")
    if flags:
        print("joints to check:")
        for cid, msg in flags:
            print(f"  {cid}: {msg}")

    if args.check and flags:
        check(work, sorted({c for c, m in flags if m.startswith("cut")}), dict(zip([r[0] for r in rows], cuts)), {r[0]: r[4] for r in rows})


def check(work, ids, cuts, texts):
    """Transcribe only the flagged clips (a few seconds of audio), not the whole reel."""
    from faster_whisper import WhisperModel

    m = WhisperModel(P.WHISPER_MODEL, device="cpu", compute_type="int8",
                     download_root=str(Path.home() / ".cache" / "autobroll" / "whisper"))
    for cid in ids:
        a, b = cuts[cid]
        tmp = work / f"_chk_{cid}.wav"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", str(a), "-to", str(b), "-i", str(work / "audio.wav"), str(tmp)], check=True)
        segs, _ = m.transcribe(str(tmp), language="ru", beam_size=5, condition_on_previous_text=False)
        heard = " ".join(s.text.strip() for s in segs)
        tmp.unlink()
        print(f"  {cid}\n    caption: {texts[cid]}\n    heard:   {heard}")


if __name__ == "__main__":
    main()
