"""Dior Maison «Таро» — set of 4 round plates: product video for DMs (no price), ~31 s.

Sources: v1/v3/v4 phone videos from the store (464×848, messenger-compressed) and 720×1280 photos
(turned into 4.5 s clips in ph/). Live sound only: Екатерина's own lines over the box («Вот такая
коробка, смотрите! Получить такой подарок под ёлку — это же вообще…») and the size («26 диаметр»),
quiet store ambience under the photos. Zoom kept ≤ 1.15 because of the low-res video.
"""
SOURCES = {
    "box": "raw/VID_20261104_101948_573.mp4",   # round sun-lid box + plates
    "amb": "raw/VID_20261104_102738_313.mp4",   # plates in the store (ambience)
    "amb2": "raw/VID_20261104_102237_826.mp4",
    "tape": "raw/VID_20261104_103701_734.mp4",  # measuring La Lune
    "fortune": "ph/IMG_20261104_101953_975.mp4",
    "etoile": "ph/IMG_20261104_101956_657.mp4",
    "lune": "ph/IMG_20261104_101951_916.mp4",
    "temper": "ph/IMG_20261104_101959_523.mp4",
    "set": "ph/IMG_20261104_102002_450.mp4",
    "open": "ph/IMG_20261104_102419_761.mp4",
    "closed": "ph/IMG_20261104_102435_595.mp4",
}
GRADE = "eq=saturation=1.08:contrast=1.04:gamma=0.98,unsharp=5:5:0.5:5:5:0"
XFADE = 0.25
KICK = 0.03
S = lambda src, t_in, dur, **k: dict(src=src, t_in=t_in, dur=dur, **k)

SHOTS = [
    S("box", 0.0, 7.3, zoom=(1.00, 1.08), focus=(0.5, 0.45)),                       # the box + her line
    S("fortune", 0.0, 2.9, zoom=(1.00, 1.07), focus=(0.5, 0.48), kick=KICK),
    S("etoile", 0.0, 2.9, zoom=(1.07, 1.00), focus=(0.5, 0.45), kick=KICK),
    S("lune", 0.0, 2.9, zoom=(1.00, 1.07), focus=(0.45, 0.45), kick=KICK),
    S("temper", 0.0, 2.9, zoom=(1.07, 1.00), focus=(0.55, 0.45), kick=KICK),
    S("set", 0.0, 3.2, zoom=(1.00, 1.06), focus=(0.5, 0.5), kick=KICK),
    S("tape", 19.6, 4.2, zoom=(1.05, 1.12), focus=(0.5, 0.55), kick=KICK),          # «26 диаметр, девчонки»
    S("open", 0.0, 2.6, zoom=(1.00, 1.06), focus=(0.5, 0.45), kick=KICK),
    S("closed", 0.0, 3.6, zoom=(1.06, 1.00), focus=(0.5, 0.45)),
]
AUDIO = [("box", 0.0, 7.3, 3), ("amb", 8.6, 14.8, -4), ("tape", 19.6, 4.2, 3), ("amb2", 2.5, 6.2, -4)]

TOP = 9
_t = [0.0]
for s in SHOTS[:-1]:
    _t.append(_t[-1] + s["dur"])
POPS = [
    (_t[0] + 0.3, 3.4, "DIOR MAISON", "коллекция по мотивам карт Таро", TOP, 0),
    (_t[0] + 3.9, 3.2, "«ПОЛУЧИТЬ ТАКОЙ ПОДАРОК\nПОД ЁЛКУ…»", None, 70, 0),
    (_t[1] + 0.15, 2.6, "КОЛЕСО ФОРТУНЫ", "удача и новые возможности", TOP, 0),
    (_t[2] + 0.15, 2.6, "ЗВЕЗДА", "надежда и вдохновение", TOP, 0),
    (_t[3] + 0.15, 2.6, "ЛУНА\u00a0", "интуиция и женственность", TOP, 0),
    (_t[4] + 0.15, 2.6, "УМЕРЕННОСТЬ", "гармония и внутреннее равновесие", TOP, 0),
    (_t[5] + 0.15, 2.9, "НАБОР ИЗ 4 ТАРЕЛОК", "у каждой — свой смысл", TOP, 0),
    (_t[6] + 0.6, 3.4, "Ø 26 СМ", "диаметр тарелки", TOP, 0),
    (_t[7] + 0.15, 5.9, "В ФИРМЕННОЙ\nКОРОБКЕ DIOR", "доставка из Китая к Новому году", TOP, 0),
]
