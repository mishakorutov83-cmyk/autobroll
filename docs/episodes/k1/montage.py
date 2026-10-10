"""Квартирник 09.10 — mood montage, ~57 s.

Sources (phone, vertical 720×1280): g guitarist solo «Я с тобой спорить не хочу…» + room pan;
t trio on stage (120 fps); s singer + guitarist «Седая ночь» (strongest number); q group of three
«Если бы мы не забыли оставить следы…» (120 fps); d duo + room pan with guests (120 fps).
Structure: four quick live snippets (own sound, flash between) → «Седая ночь» chorus as the
backbone, cut with room/guest shots and 120 fps slow motion over it → room + end card.
"""
SOURCES = {
    "g": "raw/20261009_192615.mp4",
    "t": "raw/20261009_194727.mp4",
    "s": "raw/20261009_200307.mp4",
    "q": "raw/20261009_201742.mp4",
    "d": "raw/20261009_204139.mp4",
}
GRADE = "eq=saturation=1.22:contrast=1.07:gamma=0.97,unsharp=5:5:0.4:5:5:0"

S = lambda src, t_in, dur, **k: dict(src=src, t_in=t_in, dur=dur, **k)
KICK = 0.07

# --- 1. live snippets (picture = sound)
SHOTS = [
    S("g", 0.0, 3.4, zoom=(1.00, 1.08), focus=(0.52, 0.45)),
    S("g", 3.4, 3.6, zoom=(1.45, 1.55), focus=(0.55, 0.42), kick=KICK),
    S("q", 0.0, 3.0, zoom=(1.00, 1.06), focus=(0.5, 0.42), flash=True),
    S("q", 3.0, 3.0, zoom=(1.40, 1.48), focus=(0.5, 0.40), kick=KICK),
    S("t", 1.0, 3.6, zoom=(1.05, 1.28), focus=(0.5, 0.40), flash=True),
    S("d", 0.5, 4.0, zoom=(1.30, 1.40), focus=(0.48, 0.42), kick=KICK),
]
AUDIO = [("g", 0.0, 7.0), ("q", 0.0, 6.0), ("t", 1.0, 3.6), ("d", 0.5, 4.0)]

# --- 2. «Седая ночь»: chorus from 34.6 s of s, intercut with the room and slow motion
T5, A5 = sum(x["dur"] for x in SHOTS), 34.6
sync = lambda o, dur, **k: S("s", A5 + o, dur, **k)          # in sync with the chorus audio
SHOTS += [
    sync(0.0, 4.6, zoom=(1.00, 1.10), focus=(0.45, 0.42), flash=True),
    S("g", 12.0, 3.0, zoom=(1.00, 1.06), focus=(0.5, 0.5), kick=KICK),           # room, guests
    sync(7.6, 3.0, zoom=(1.55, 1.62), focus=(0.30, 0.38), kick=KICK),           # singer close
    sync(10.6, 3.4, zoom=(1.22, 1.30), focus=(0.42, 0.42), kick=KICK),
    S("d", 8.0, 3.0, speed=0.5, zoom=(1.20, 1.34), focus=(0.48, 0.42)),          # slow motion
    sync(17.0, 3.6, zoom=(1.50, 1.58), focus=(0.30, 0.38), kick=KICK),
    S("d", 23.0, 3.0, speed=0.5, zoom=(1.00, 1.10), focus=(0.5, 0.5)),           # guests, slow
    sync(23.6, 3.4, zoom=(1.00, 1.08), focus=(0.45, 0.45), kick=KICK),
    S("t", 6.0, 2.6, speed=0.5, zoom=(1.10, 1.25), focus=(0.5, 0.40)),           # trio, slow
    sync(29.6, 3.7, zoom=(1.40, 1.62), focus=(0.32, 0.38), kick=KICK),
]
AUDIO += [("s", A5, 33.3)]

# --- 3. the room + end card (chorus tail fades out)
SHOTS += [S("d", 26.0, 3.0, speed=0.5, zoom=(1.00, 1.08), focus=(0.5, 0.5), flash=True)]
AUDIO += [("s", A5 + 33.3, 3.0)]

POPS = [
    (0.25, 2.4, "КВАРТИРНИК", "в «Нашем месте»", 42, -3),
    (T5 + 0.5, 2.6, "«СЕДАЯ НОЧЬ»", "живой звук", 42, 2),
]
END = ("ПРОДОЛЖЕНИЕ\n10 ОКТЯБРЯ", "Начало в 20:00 • квартирник в «Нашем месте»", 3.0)
