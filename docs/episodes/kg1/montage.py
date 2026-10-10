"""Караоке-игра — promo, 18.5 s, from one 15.5 s phone clip of guests singing at the tables.

Picture stays in time order (the sound is the room's own karaoke), every cut is a zoom change +
kick, flashes on the round changes; stickers sit high (over the windows) so faces stay clear.
Low-res source (464×848): zoom kept ≤ 1.35.
"""
SOURCES = {"k": "raw/src.mp4"}
GRADE = "eq=saturation=1.28:contrast=1.08:gamma=0.96,colorbalance=rm=0.04:bm=-0.03,unsharp=5:5:0.5:5:5:0"

S = lambda t_in, dur, **k: dict(src="k", t_in=t_in, dur=dur, **k)
KICK = 0.08
SHOTS = [
    S(0.0, 2.4, zoom=(1.00, 1.08), focus=(0.5, 0.55)),
    S(2.4, 2.4, zoom=(1.25, 1.30), focus=(0.45, 0.55), kick=KICK, flash=True),
    S(4.8, 2.2, zoom=(1.00, 1.06), focus=(0.5, 0.55), kick=KICK, flash=True),
    S(7.0, 2.0, zoom=(1.28, 1.34), focus=(0.5, 0.55), kick=KICK, flash=True),
    S(9.0, 2.8, zoom=(1.15, 1.30), focus=(0.42, 0.55), kick=KICK, flash=True),   # the singer
    S(11.8, 2.4, zoom=(1.00, 1.10), focus=(0.5, 0.55), kick=KICK),
    S(14.2, 1.3, zoom=(1.25, 1.30), focus=(0.5, 0.55), kick=KICK),
    S(13.0, 3.0, speed=0.5, zoom=(1.00, 1.08), focus=(0.5, 0.55), flash=True),  # under the end card
]
AUDIO = [("k", 0.0, 15.5), ("k", 12.5, 3.0)]

TOP = 13
POPS = [
    (0.2, 2.1, "КАРАОКЕ-ИГРА", "завтра в «Нашем месте»", TOP, -3),
    (2.5, 2.2, "УГАДАЙ ХИТ", "по зашифрованному тексту", TOP, 2),
    (4.9, 2.0, "ЗАДОМ НАПЕРЁД", "песни наоборот", TOP, -2),
    (7.1, 1.8, "БЛИЦ!", "быстрые вопросы", TOP, 3),
    (9.1, 2.6, "УГАДАЛ —\nНА СЦЕНУ!", "и зажигаешь в караоке", TOP, -2),
    (11.9, 2.2, "БАЛЛЫ", "за ответ + за исполнение", TOP, 2),
    (14.2, 1.3, "СОБИРАЙ КОМАНДУ", None, TOP, -2),
]
END = ("КАРАОКЕ-ИГРА\nЗАВТРА", "Собирайте команду • «Наше место»", 3.0)
