"""Караоке-вечера ПТ–ВС — promo, ~26 s. Base: the karaoke-game clip (guests singing at the
tables, its own karaoke sound); short stage inserts from the квартирник with the «Седая ночь»
chorus as the second half's sound; trigger-phrase stickers over the windows/ceiling.
"""
SOURCES = {
    "k": "raw_kg/src.mp4",                    # guests with microphones at the tables
    "s": "raw_k1/20261009_200307.mp4",        # singer + guitar, «Седая ночь»
    "d": "raw_k1/20261009_204139.mp4",        # duo (120 fps → slow motion)
}
GRADE = "eq=saturation=1.25:contrast=1.07:gamma=0.97,unsharp=5:5:0.4:5:5:0"

S = lambda src, t_in, dur, **k: dict(src=src, t_in=t_in, dur=dur, **k)
KICK = 0.08
A = 34.6                                      # «Седая ночь» chorus start in s
SHOTS = [
    # --- karaoke at the tables, own sound
    S("k", 0.0, 2.4, zoom=(1.00, 1.08), focus=(0.5, 0.55)),
    S("k", 2.4, 2.4, zoom=(1.25, 1.30), focus=(0.45, 0.55), kick=KICK, flash=True),
    S("k", 4.8, 3.2, zoom=(1.00, 1.08), focus=(0.5, 0.55), kick=KICK),
    # --- «Седая ночь»: stage in sync, karaoke shots over it
    S("s", A + 0.0, 3.0, zoom=(1.00, 1.10), focus=(0.45, 0.42), flash=True),
    S("k", 9.0, 2.8, zoom=(1.15, 1.30), focus=(0.42, 0.55), kick=KICK),          # girl with the mic
    S("k", 11.8, 2.4, zoom=(1.00, 1.10), focus=(0.5, 0.55), kick=KICK),
    S("d", 8.0, 2.4, speed=0.5, zoom=(1.20, 1.32), focus=(0.48, 0.42), kick=KICK),
    S("k", 1.0, 2.4, zoom=(1.22, 1.30), focus=(0.55, 0.62), kick=KICK),           # table, food
    S("s", A + 13.0, 2.0, zoom=(1.50, 1.60), focus=(0.30, 0.38), kick=KICK),
    # --- end card
    S("k", 13.0, 3.0, speed=0.5, zoom=(1.00, 1.08), focus=(0.5, 0.55), flash=True),
]
AUDIO = [("k", 0.0, 8.0), ("s", A, 15.0), ("s", A + 15.0, 3.0)]

TOP = 13
POPS = [
    (0.2, 2.1, "КАРАОКЕ-ВЕЧЕРА", "с пятницы по воскресенье", TOP, -3),
    (2.5, 2.2, "ПОЁМ ВМЕСТЕ", None, TOP, 2),
    (4.9, 3.0, "ЛЮБИМЫЕ ПЕСНИ", "которые знает каждый", TOP, -2),
    (8.1, 2.8, "ЖИВАЯ АТМОСФЕРА", None, TOP, 2),
    (11.1, 2.6, "МИКРОФОН\nЖДЁТ ТЕБЯ", None, TOP, -3),
    (13.9, 2.2, "ДУШЕВНАЯ КОМПАНИЯ", None, TOP, 2),
    (16.3, 2.2, "ОТЛИЧНЫЙ ЗВУК", None, TOP, -2),
    (18.6, 2.2, "ВКУСНАЯ ЕДА", None, TOP, 2),
    (21.0, 1.9, "ПТ • СБ • ВС", "приходи петь с нами", TOP, -2),
]
END = ("КАРАОКЕ-ВЕЧЕРА\nПТ – ВС", "«Наше место» • Фошань", 3.0)
