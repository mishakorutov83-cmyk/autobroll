"""Караоке сегодня 20:00–02:00 — promo for the Telegram group, 15 s (v2; v1 was 39 s).

Message: the place where НАШИ gather — sing and hear favourite songs, live talk, familiar food,
new friends, rest with friends. Six phone clips (1080×1920): t table, guests singing «Нет, я
молодой, просто седой» (night window); o woman in white on stage «Останусь пеплом на губах…»;
g guitarist + friend (квартирник); w woman in a beige shirt on stage; m man on stage «Сердечный
пульс…»; f two men at the table with mics. Every shot plays its own live sound; the table chorus
opens and closes the film; soft crossfades between songs, a gentle kick on each cut, warm plates
up top (over the ceiling greenery), never on faces.
"""
SOURCES = {
    "t": "raw/IMG_1727.MOV",
    "o": "raw/20260918_211608.mp4",
    "g": "raw/IMG_1716.MOV",
    "w": "raw/IMG_1721.MOV",
    "m": "raw/20260918_213418.mp4",
    "f": "raw/IMG_1726.MOV",
}
GRADE = "eq=saturation=1.18:contrast=1.06:gamma=0.98,unsharp=5:5:0.35:5:5:0"
XFADE = 0.12
KICK = 0.05
SHOTS, AUDIO = [], []


def sync(src, t_in, dur, gain=0, **k):
    SHOTS.append(dict(src=src, t_in=t_in, dur=dur, **k))
    AUDIO.append((src, t_in, dur, gain))


sync("t", 36.0, 2.3, zoom=(1.00, 1.06), focus=(0.4, 0.62))                          # «Нет, я молодой…»
sync("o", 10.8, 1.9, zoom=(1.30, 1.38), focus=(0.5, 0.42), kick=KICK, flash=True)   # «Останусь пеплом…»
sync("g", 19.5, 1.6, gain=7, zoom=(1.15, 1.22), focus=(0.42, 0.52), kick=KICK)     # guitar
sync("w", 4.6, 1.6, gain=3, zoom=(1.25, 1.31), focus=(0.45, 0.45), kick=KICK)      # woman, beige shirt
sync("m", 0.0, 1.6, zoom=(1.35, 1.42), focus=(0.5, 0.45), kick=KICK)               # «Сердечный пульс…»
sync("f", 0.3, 1.6, gain=3.5, zoom=(1.00, 1.06), focus=(0.45, 0.62), kick=KICK)    # friends at the table
sync("t", 45.3, 1.9, zoom=(1.05, 1.12), focus=(0.45, 0.62), kick=KICK, flash=True) # «Нет, я не другой…»
# end card over the table, the chorus keeps going underneath
sync("t", 47.2, 2.6, zoom=(1.00, 1.05), focus=(0.5, 0.55))

TOP = 9
_t = [0.0]
for s in SHOTS[:-1]:
    _t.append(_t[-1] + s["dur"])
POPS = [
    (_t[0] + 0.1, 2.15, "МЕСТО, ГДЕ\nСОБИРАЮТСЯ НАШИ", "«Наше место»", TOP, 0),
    (_t[1] + 0.1, 1.75, "ПОЁМ ОТ ДУШИ", None, TOP, 0),
    (_t[2] + 0.05, 1.5, "ЖИВОЕ ОБЩЕНИЕ", None, TOP, 0),
    (_t[3] + 0.05, 1.5, "ЛЮБИМЫЕ ПЕСНИ", None, TOP, 0),
    (_t[4] + 0.05, 1.5, "НОВЫЕ ЗНАКОМСТВА", None, TOP, 0),
    (_t[5] + 0.05, 1.5, "ВКУСНАЯ\nПРИВЫЧНАЯ ЕДА", None, TOP, 0),
    (_t[6] + 0.1, 1.75, "ОТДЫХ\nС ДРУЗЬЯМИ", None, TOP, 0),
]
END = ("КАРАОКЕ СЕГОДНЯ\n17 ОКТЯБРЯ", "20:00 – 02:00 • «Наше место»", 2.6)
