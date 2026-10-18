"""Canton Fair 140 (phase 1, 17.10) — Михаил's visit, a story (~18 s).

Clips (phone, 720×1280): s screen wall at the entrance lighting up; r WOOB red robot dogs;
d white robot dog walking to camera; f red tracked fire-fighting robot; h holographic fans and
spheres; v VR rides. Hook = his line «не побывать… я не имел права» → the facts (140th jubilee,
phase 1: electronics, robotics, power tools; 340 000 guests, 8 000 sellers — figures as given by
Михаил) → end card. Live hall sound; the hologram stand's stray speech is replaced by hall noise.
Plates at 16 % (below the Stories header), short, one per shot.
"""
SOURCES = {
    "s": "raw/20261017_090601.mp4",
    "r": "raw/20261017_092059.mp4",
    "d": "raw/20261017_092220.mp4",
    "f": "raw/20261017_092922.mp4",
    "h": "raw/20261017_102432.mp4",
    "v": "raw/20261017_112433.mp4",
}
GRADE = "eq=saturation=1.15:contrast=1.06:gamma=0.98,unsharp=5:5:0.4:5:5:0"
XFADE = 0.2
KICK = 0.05
S = lambda src, t_in, dur, **k: dict(src=src, t_in=t_in, dur=dur, **k)

SHOTS = [
    S("s", 3.0, 3.0, zoom=(1.00, 1.10), focus=(0.5, 0.45)),                         # screen wall lights up
    S("r", 1.0, 2.6, zoom=(1.10, 1.18), focus=(0.45, 0.6), kick=KICK, flash=True),   # red robot dogs
    S("d", 6.5, 2.8, zoom=(1.05, 1.12), focus=(0.5, 0.6), kick=KICK),               # robot dog walks in
    S("f", 0.3, 2.4, zoom=(1.05, 1.12), focus=(0.4, 0.55), kick=KICK),              # fire-fighting robot
    S("h", 3.0, 2.4, zoom=(1.05, 1.12), focus=(0.5, 0.55), kick=KICK),              # holograms
    S("v", 2.0, 2.6, zoom=(1.05, 1.12), focus=(0.5, 0.45), kick=KICK),              # VR rides
    S("s", 9.0, 2.8, zoom=(1.00, 1.06), focus=(0.5, 0.45), flash=True),             # under the end card
]
AUDIO = [("s", 3.0, 3.0), ("r", 1.0, 2.6), ("d", 6.5, 2.8), ("f", 0.3, 2.4),
         ("f", 2.7, 2.4), ("v", 2.0, 2.6, -2), ("s", 9.0, 2.8)]

TOP = 16
_t = [0.0]
for s in SHOTS[:-1]:
    _t.append(_t[-1] + s["dur"])
POPS = [
    (_t[0] + 0.15, 2.8, "Я НЕ ИМЕЛ ПРАВА\nПРОПУСТИТЬ", "живя в Гуанчжоу", TOP, 0),
    (_t[1] + 0.1, 2.45, "140-Я ЮБИЛЕЙНАЯ\nCANTON FAIR", None, TOP, 0),
    (_t[2] + 0.1, 2.65, "1-Й ЭТАП", "электроника • робототехника\nэлектроинструмент", TOP, 0),
    (_t[3] + 0.1, 2.25, "РОБОТЫ-СПАСАТЕЛИ", "пожарный робот", TOP, 0),
    (_t[4] + 0.1, 2.25, "340 000 ГОСТЕЙ", "со всего мира", TOP, 0),
    (_t[5] + 0.1, 2.45, "8 000 ПРОДАВЦОВ", None, TOP, 0),
]
END = ("CANTON FAIR\n140-Я ВЫСТАВКА", "Гуанчжоу • 1-й этап • 15–19 октября", 2.8)
