"""Караоке-игра 11.10 — итоги дня, ~68 s. Chronology of the evening → the award ceremony.

Clips (phone, 720×1280): w team writing answers; t singing at the table; a audience (hands up at
the end); b man in black on stage; s man in white («…посадим сирень»), guests dancing; f woman in
white singing; c the ceremony (host announces, teams walk up, certificates and prizes, line-up).
Part 1 — short sync snippets with flashes; part 2 — the ceremony cut to the host's key lines.
"""
SOURCES = {
    "w": "raw/mmexport1791738011256.mp4",
    "t": "raw/mmexport1791738033963.mp4",
    "a": "raw/mmexport1791737998203.mp4",
    "b": "raw/mmexport1791738045119.mp4",
    "s": "raw/mmexport1791738055339.mp4",
    "f": "raw/mmexport1791737901475.mp4",
    "c": "raw/mmexport1791737960940.mp4",
}
GRADE = "eq=saturation=1.25:contrast=1.07:gamma=0.97,unsharp=5:5:0.4:5:5:0"

KICK = 0.07
SHOTS, AUDIO = [], []


def sync(src, t_in, dur, pic=None, **k):
    """shot whose own sound plays; pic = other source time for the picture (camera looked away)"""
    SHOTS.append(dict(src=src, t_in=t_in if pic is None else pic, dur=dur, **k))
    AUDIO.append((src, t_in, dur))


# --- 1. the evening
sync("w", 0.0, 3.4, zoom=(1.00, 1.08), focus=(0.4, 0.5))
sync("t", 0.0, 3.0, zoom=(1.10, 1.18), focus=(0.5, 0.45), kick=KICK, flash=True)
sync("a", 9.6, 3.0, zoom=(1.15, 1.22), focus=(0.6, 0.5), kick=KICK)
sync("b", 1.0, 3.0, zoom=(1.20, 1.28), focus=(0.5, 0.4), kick=KICK, flash=True)
sync("s", 9.0, 3.5, zoom=(1.15, 1.25), focus=(0.45, 0.4), kick=KICK)
sync("s", 40.5, 3.0, zoom=(1.00, 1.08), focus=(0.5, 0.5), kick=KICK)
sync("f", 6.0, 3.0, zoom=(1.20, 1.28), focus=(0.45, 0.4), kick=KICK)
T2 = sum(s["dur"] for s in SHOTS)

# --- 2. the ceremony (host's key lines)
sync("c", 5.00, 2.35, pic=9.0, zoom=(1.10, 1.16), focus=(0.5, 0.45), flash=True)    # «Первая команда, вы готовы узнать результат?»
sync("c", 11.85, 4.75, zoom=(1.25, 1.32), focus=(0.5, 0.42), kick=KICK)    # «…победила другую всего на два балла»
sync("c", 29.62, 1.10, zoom=(1.10, 1.14), focus=(0.5, 0.45), kick=KICK)    # «Первое место…»
sync("c", 34.20, 3.70, pic=26.0, zoom=(1.30, 1.36), focus=(0.5, 0.42), kick=KICK)    # «…занимает команда… Итак, аплодисменты!»
sync("c", 40.70, 6.10, zoom=(1.00, 1.08), focus=(0.5, 0.5), kick=KICK)     # «Первое место занимает команда …! Поздравляю вас! Подходите ко мне!»
sync("c", 50.40, 2.70, zoom=(1.00, 1.06), focus=(0.5, 0.5), kick=KICK)     # the team walks up
sync("c", 60.10, 7.00, zoom=(1.10, 1.20), focus=(0.5, 0.45), kick=KICK)    # «…почётная грамота… бесплатный кальян от нашего места»
sync("c", 69.40, 5.00, zoom=(1.00, 1.08), focus=(0.5, 0.5), kick=KICK, flash=True)  # «вторая команда… «Наши люди»»
sync("c", 79.50, 2.50, zoom=(1.00, 1.06), focus=(0.5, 0.5), kick=KICK)     # walking up
sync("c", 85.40, 3.80, zoom=(1.15, 1.22), focus=(0.5, 0.45), kick=KICK)    # «…поздравляем, это ваша почётная грамота»
sync("c", 92.40, 4.10, zoom=(1.00, 1.08), focus=(0.5, 0.5), kick=KICK)     # «каждый выигрывает по бутылке… пива»
sync("c", 98.30, 3.20, zoom=(1.05, 1.12), focus=(0.5, 0.5), kick=KICK)     # «Поздравляю! Давайте теперь сделаем…»

# --- end card over the line-up, the room's cheer underneath
SHOTS.append(dict(src="c", t_in=99.0, dur=3.0, speed=0.5, zoom=(1.00, 1.08), focus=(0.5, 0.5), flash=True))
AUDIO.append(("a", 25.5, 3.0))

TOP = 13
POPS = [
    (0.2, 3.0, "КАРАОКЕ-ИГРА", "как это было", TOP, -3),
    (3.5, 2.8, "УГАДЫВАЛИ ХИТЫ", None, TOP, 2),
    (9.5, 2.8, "ЗАЖИГАЛИ НА СЦЕНЕ", None, TOP, -2),
    (16.0, 2.8, "ПЕЛ ВЕСЬ ЗАЛ", None, TOP, 2),
    (T2 + 0.1, 2.2, "ИТОГИ ИГРЫ", None, TOP, -2),
    (T2 + 3.0, 3.6, "РАЗНИЦА — 2 БАЛЛА", None, TOP, 2),
    (T2 + 12.5, 4.0, "1 МЕСТО", "21 балл", TOP, -3),
    (T2 + 21.0, 5.5, "ГРАМОТА + КАЛЬЯН", "от «Нашего места»", TOP, 2),
    (T2 + 27.5, 4.5, "2 МЕСТО", "«Наши люди» • 19 баллов", TOP, -2),
    (T2 + 37.5, 3.8, "ПИВО КАЖДОМУ", "на выбор от «Нашего места»", TOP, 2),
]
END = ("КАРАОКЕ-ИГРА\n«НАШЕ МЕСТО»", "Спасибо всем командам! До новых игр", 3.0)
