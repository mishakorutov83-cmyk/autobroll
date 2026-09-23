import json, numpy as np, re
FPS = 30
T = json.load(open("transcript.json"))
WORDS = []
for seg in T:
    for w in seg["words"]:
        if w["w"].startswith("-") and WORDS:
            WORDS[-1] = {**WORDS[-1], "w": WORDS[-1]["w"] + w["w"], "e": w["e"]}
        else:
            WORDS.append(dict(w))
FACES = json.load(open("faces.json"))
rms = np.load("rms.npy")
db = 20 * np.log10(np.convolve(rms, np.ones(3) / 3, mode="same") + 1e-6)

N, M, C = 1.06, 1.16, 1.28
# id, in, out, shot(scale or (a,b) slow push), corrected caption text, accents, punch=(t,scale)
E = [
 ("c01",160.60,163.30,(1.20,1.30),"Я здесь девять месяцев сидел без заказов,",["девять","месяцев"],None),
 ("c02",153.50,157.80,M,"Не ехать сюда, поверив всем, что здесь золотые горы.",["золотые","горы."],None),
 ("c03",45.36,47.16,N,"Как зовут, откуда ты?",[],None),
 ("c04",48.10,49.30,M,"Меня зовут Мовсар.",[],None),
 ("c05",50.90,54.10,N,"Сам я чеченец, но я из Питера. Всю жизнь прожил в Питере.",[],None),
 ("c06",56.42,58.90,M,"Сколько ты уже в Китае? Второй год.",[],None),
 ("c07",60.14,61.02,N,"Чем занимаешься?",[],None),
 ("c08",62.32,65.12,N,"Сейчас продаю люксовые копии часов",[],None),
 ("c09",66.00,69.28,M,"создаю свой бренд обуви. Уже почти готов.",["бренд","обуви."],None),
 ("c10",77.58,79.94,N,"Как появился в твоей жизни Китай, расскажи.",[],None),
 ("c11",80.06,84.76,M,"Вот я прилетел сюда, чтобы познакомиться с фабриками, кто делает обувь.",[],None),
 ("c12",85.42,93.38,N,"И три недели здесь побыв, и решил, что здесь буду жить. Я улетел в Питер, собрал все свои вещи и прилетел.",["буду","жить."],(89.30,C)),
 ("c13",94.32,95.66,M,"Всё, так и остался.",[],None),
 ("c14",112.04,114.10,N,"Нравится? Да, мне нравится. Супер.",[],None),
 ("c15",127.82,131.28,M,"Человек только приехал в Китай, с чего начать?",[],None),
 ("c16",150.92,160.40,N,"Ехать с какой-то определённой целью, а не ехать сюда, поверив всем, что здесь золотые горы, что вы можете зарабатывать всё подряд. Нет.",["определённой","целью,"],(153.40,M)),
 ("c17",160.60,163.30,C,"Я здесь девять месяцев сидел без заказов,",["девять","месяцев"],None),
 ("c18",165.02,166.28,M,"но я продолжал своё дело.",["продолжал"],None),
 ("c19",167.30,172.38,N,"Я всем посоветую определиться, что они хотят в жизни, только после этого действовать.",["определиться,"],(170.95,M)),
 ("c20",370.02,375.30,N,"Чего ты сейчас такого знаешь о Китае, чего не знал в свой первый месяц пребывания?",[],(372.90,M)),
 ("c21",378.88,380.60,C,"Здесь реально дёшево жить.",["дёшево"],None),
 ("c22",386.86,390.82,N,"Намного дешевле отсюда путешествовать по всей Азии.",[],None),
 ("c23",391.94,397.10,M,"Я вот лечу скоро во Вьетнам. Туда-обратно билеты у меня обошлись в 20 тысяч рублей.",["20","тысяч"],(394.50,C)),
 ("c24",397.90,398.44,N,"Супер.",[],None),
 ("c25",240.36,243.05,N,"Как ты вообще пришёл к своей нише",[],None),
 ("c26",243.65,245.38,M,"по часам?",[],None),
 ("c27",246.06,248.52,C,"По наитию, если честно.",["наитию,"],None),
 ("c28",250.04,254.68,N,"Волка ноги кормят. Не буду придумывать ничего. Вот как есть.",[],None),
 ("c29",254.96,261.24,M,"Человек у меня заказал 75 штук часов. Спасибо, кстати, этому человеку.",["75"],(259.25,N)),
 ("c30",263.30,269.42,N,"Полтора месяца каждый день я с ним эти часы разбирал, открывал, проверял, смотрел.",[],(266.60,M)),
 ("c31",269.64,274.54,C,"И всё — засосало, как говорится.",["засосало,"],None),
 ("c32",410.36,415.98,N,"Представь, что ты с твоим багажом знаний вот уже приезжаешь повторно в Китай.",[],(413.30,M)),
 ("c33",416.74,419.34,N,"Вот первые три действия, которые бы ты сделал?",["три","действия,"],None),
 ("c34",424.18,425.88,M,"Не приехал бы без визы.",[],None),
 ("c35",428.64,431.06,N,"Нашёл бы квартиру, где прописали бы сразу.",[],None),
 ("c36",432.60,434.64,M,"И занялся бы чем-то одним.",["одним."],None),
 ("c37",435.12,438.76,C,"И становился бы в этом направлении самым лучшим.",["самым","лучшим."],None),
 ("c38",440.04,440.98,M,"Всё. Вот три действия.",[],None),
 ("c39",441.84,442.36,N,"Офигенно.",[],None),
 ("c40",460.84,464.52,M,"Ты сможешь чем-то помочь на безвозмездной основе, без коммерции?",["безвозмездной"],None),
 ("c41",470.42,474.80,N,"Я так и делаю, если честно. И это сейчас без прикрас. Ко мне обращаются.",[],(472.20,M)),
 ("c42",475.16,486.10,N,"Я без всяких там «заплати мне за поставщиков». И ещё познакомлю с поставщиками. Покажу основные рынки. Расскажу, где снять дешевле квартиру, где подороже.",[],(481.05,M)),
 ("c43",486.50,488.24,C,"И ни копейки за это не возьмёшь.",["ни","копейки"],None),
 ("c44",488.96,489.48,M,"Супер.",[],None),
 ("c45",556.28,560.95,N,"И от нашей семьи тебе говорим огромное спасибо за помощь, которую ты нам оказываешь.",["огромное","спасибо"],(559.10,M)),
 ("c46",574.00,578.24,N,"Если они посетят наш ресторан, что им в первую очередь нужно попробовать?",[],(576.00,M)),
 ("c47",582.90,584.56,M,"Если честно, я ещё пробую.",[],None),
 ("c48",591.56,593.90,N,"Пока всё, что ел, всё было вкусно.",["вкусно."],None),
 ("c49",594.08,594.80,M,"",[],None),
 ("c50",594.80,597.80,N,None,[],None),
]

OVR = {"c02": (153.52, None), "c08": (62.0, 65.35), "c29": (None, 261.30), "c32": (None, 416.05), "c19": (None, 172.85)}

def snap_in(t, lo):
    a, b = max(lo, t - 0.22), t + 0.04
    i0, i1 = int(a * 100), int(b * 100)
    seg = db[i0:i1]
    m = seg.min()
    cand = [i for i in range(len(seg)) if seg[i] <= m + 2.5]
    i = max(cand)  # latest quiet point before speech
    return (i0 + i) / 100

def snap_out(t, hi):
    a, b = t - 0.04, min(hi, t + 0.28)
    i0, i1 = int(a * 100), int(b * 100)
    seg = db[i0:i1]
    m = seg.min()
    cand = [i for i in range(len(seg)) if seg[i] <= m + 2.5]
    i = min(cand)  # earliest quiet point after speech
    return (i0 + i) / 100

def fr(x):
    return round(x * FPS) / FPS

# ---- face track -------------------------------------------------------------
def face_at(t):
    best = None
    for f in FACES:
        if abs(f["t"] - t) > 0.13: continue
        good = [z for z in f["faces"] if z[2] > 0.12 and z[1] + z[3] / 2 < 0.5]
        if good:
            x, y, w, h, c = max(good, key=lambda z: z[2])
            best = (x + w / 2, y + h / 2)
    return best

def track(a, b):
    ts = np.arange(a, b + 0.001, 0.25)
    pts = [face_at(t) for t in ts]
    # fill gaps with nearest valid
    valid = [i for i, p in enumerate(pts) if p]
    if not valid:
        return ts, np.full(len(ts), 0.5), np.full(len(ts), 0.27)
    xs, ys = [], []
    for i in range(len(ts)):
        j = min(valid, key=lambda v: abs(v - i))
        xs.append(pts[j][0]); ys.append(pts[j][1])
    xs, ys = np.array(xs), np.array(ys)
    k = 7  # ~1.75s smoothing window
    pad = lambda v: np.pad(v, k // 2, mode="edge")
    xs = np.convolve(pad(xs), np.ones(k) / k, mode="valid")
    ys = np.convolve(pad(ys), np.ones(k) / k, mode="valid")
    return ts, xs, ys

def xf(s, cx, cy):
    oy = (cy * 1974 - 27) / 1920
    tx_target = 0.5 + (cx - 0.5) * 0.3
    ty_target = 0.30
    lim = (s - 1) / 2
    tx = np.clip(tx_target - (0.5 + (cx - 0.5) * s), -lim, lim)
    ty = np.clip(ty_target - (0.5 + (oy - 0.5) * s), -lim, lim)
    return round(float(tx) * 100, 2), round(float(ty) * 100, 2)

clips, captions = [], []
prev_out = 0
for idx, (cid, a, b, shot, text, acc, punch) in enumerate(E):
    if not text:
        ia, ob = a, b
    else:
        ia = snap_in(a, 0)
        ob = snap_out(b, 10000)
        ia = max(0, ia - 0.02); ob = ob + 0.04
    o = OVR.get(cid, (None, None))
    if o[0] is not None: ia = o[0]
    if o[1] is not None: ob = o[1]
    ia, ob = fr(ia), fr(ob)
    # keyframes
    ts, xs, ys = track(ia, ob)
    def scale_at(t):
        if isinstance(shot, tuple):
            f = (t - ia) / max(0.01, ob - ia)
            return shot[0] + (shot[1] - shot[0]) * f
        if punch and t >= punch[0]:
            return punch[1]
        return shot
    kts = sorted(set([round(t, 3) for t in np.arange(ia, ob + 0.001, 0.5)] + [ob] +
                     ([round(punch[0] - 1 / FPS, 3), round(punch[0], 3)] if punch else [])))
    kfs = []
    for t in kts:
        i = int(np.argmin(np.abs(ts - t)))
        s = scale_at(t if not (punch and abs(t - (punch[0] - 1 / FPS)) < 1e-3) else punch[0] - 0.5)
        x, y = xf(s, xs[i], ys[i])
        kfs.append({"t": round(t, 3), "scale": round(s, 4), "x": x, "y": y})
    clip = {"id": cid, "src": "clips/ep1.mp4", "label": (text or "outro")[:28], "inSec": ia, "outSec": ob,
            "sourceDurationSec": 627.3, "transform": kfs, "volume": 1}
    if text is None:
        clip["muted"] = True
    clips.append(clip)
    if not text:
        continue
    # ---- captions: align corrected tokens to whisper words --------------------
    ww = [w for w in WORDS if w["s"] >= a - 0.25 and w["s"] < b - 0.02]
    toks = text.split()
    import difflib
    norm = lambda x: re.sub(r"[^а-яa-z0-9]", "", x.lower().replace("ё", "е"))
    A = [norm(t) for t in toks]; B = [norm(w["w"]) for w in ww]
    tim = [None] * len(toks)
    for blk in difflib.SequenceMatcher(None, A, B, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            w = ww[blk.b + k]; tim[blk.a + k] = (max(w["s"], ia), min(w["e"], ob))
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, A, B, autojunk=False).get_opcodes():
        if op == "replace" and i2 - i1 == j2 - j1:
            for k in range(i2 - i1):
                w = ww[j1 + k]; tim[i1 + k] = (max(w["s"], ia), min(w["e"], ob))
    # interpolate the rest between known neighbours
    for k in range(len(toks)):
        if tim[k] is None:
            p = next((tim[j][1] for j in range(k - 1, -1, -1) if tim[j]), ia)
            nx = next((tim[j][0] for j in range(k + 1, len(toks)) if tim[j]), ob)
            run = [j for j in range(k, len(toks)) if tim[j] is None]
            run = run[:next((i for i in range(1, len(run)) if run[i] != run[i-1] + 1), len(run))]
            step = (nx - p) / len(run)
            for n, j in enumerate(run):
                tim[j] = (p + n * step, p + (n + 1) * step)
            print(f"  {cid}: interpolated", [toks[j] for j in run])
    # pages: <= ~30 chars, break after sentence punctuation
    pages, cur = [], []
    for k, t in enumerate(toks):
        cur.append(k)
        chars = sum(len(toks[j]) + 1 for j in cur)
        nxt = toks[k + 1] if k + 1 < len(toks) else None
        end_sent = re.search(r"[.?!]$", t) is not None
        soft = re.search(r"[,»]$", t) is not None
        nxt_len = len(nxt) + 1 if nxt else 0
        if nxt is None or end_sent and chars > 8 or chars + nxt_len > 32 or (soft and chars > 20):
            pages.append(cur); cur = []
    # glue lonely 1-word tail pages to the previous page when it fits
    merged = []
    for p in pages:
        if merged and len(p) == 1 and sum(len(toks[j]) + 1 for j in merged[-1] + p) <= 36 and not re.search(r"[.?!]$", toks[merged[-1][-1]]):
            merged[-1] = merged[-1] + p
        else:
            merged.append(p)
    for pi, p in enumerate(merged):
        words = [{"text": toks[j], "startMs": round(tim[j][0] * 1000), "endMs": round(tim[j][1] * 1000),
                  "accent": toks[j] in acc} for j in p]
        captions.append({"id": f"{cid}_{pi}", "clipId": cid, "words": words,
                         "startMs": max(round(ia * 1000), words[0]["startMs"] - 60), "endMs": words[-1]["endMs"],
                         "topPct": 63.5})

titles = [
    {"id": "lt", "kind": "lower", "clipId": "c04", "offsetSec": 0.15, "durationSec": 4.6, "title": "МОВСАР", "subtitle": "Китай • бизнес • личный опыт"},
    {"id": "end", "kind": "end", "clipId": "c50", "offsetSec": 0, "durationSec": 3.0, "title": "ЛЮДИ\nНАШЕГО МЕСТА", "subtitle": "Новые истории людей из Китая"},
]
props = {"clips": clips, "music": None, "captions": captions, "brolls": [], "accentColor": "#F2C14E",
         "captionPreset": "clean", "titles": titles}
json.dump(props, open("/home/user/autobroll/public/ep1.props.json", "w"), ensure_ascii=False, indent=1)
tot = sum(round((c["outSec"] - c["inSec"]) * FPS) for c in clips) / FPS
print("clips", len(clips), "captions", len(captions), "total", round(tot, 2))
for c in captions[:12]:
    print(" ".join(w["text"] for w in c["words"]))
