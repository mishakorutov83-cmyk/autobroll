"""Dior Maison «Таро» — 8 rectangular dishes: review / upsell video for DMs (no price), ~1 min.

Sources: Екатерина's store videos (1080×1920, one per card, her own explanation of the card),
sped up 1.1× with pitch kept (sp/*.mp4; times below are ORIGINAL seconds, divided by SP);
Le Soleil has no video → its photo; the measuring take (IMG_0409) for the size — verified by
forced choice: «20 с половиной на 18». Every voice segment is cut at word boundaries.
"""
SP = 1.1
SOURCES = {k: f"sp/{k}.mp4" for k in ["0406", "0407", "0409", "0410", "0411", "0412", "0413", "0414"]}
SOURCES.update({"soleil": "sp/p0418.mp4", "papesse_ph": "sp/p0424.mp4"})
GRADE = "eq=saturation=1.08:contrast=1.04:gamma=0.98,unsharp=5:5:0.4:5:5:0"
XFADE = 0.18
KICK = 0.03
SHOTS, AUDIO = [], []


def v(src, a, b, gain=0, **k):
    """voice + picture in sync, a/b in original seconds"""
    SHOTS.append(dict(src=src, t_in=a / SP, dur=round((b - a) / SP, 3), **k))
    AUDIO.append((src, a / SP, round((b - a) / SP, 3), gain))


def card(name, fr, meaning, t):
    POPS.append((t, 3.2, name, f"{fr} • {meaning}", TOP, 0))


TOP = 9
POPS = []
v("0414", 0.45, 12.35, zoom=(1.00, 1.06), focus=(0.5, 0.5))                       # Звезда
v("0412", 0.00, 7.32, zoom=(1.00, 1.06), focus=(0.5, 0.5), kick=KICK)            # Колесо Фортуны
SHOTS.append(dict(src="soleil", t_in=0.0, dur=3.2, zoom=(1.00, 1.07), focus=(0.5, 0.45), kick=KICK))
AUDIO.append(("0409", 0.3, 3.2, -6))                                              # Солнце (photo, room tone)
v("0413", 1.54, 7.16, zoom=(1.00, 1.06), focus=(0.5, 0.5), kick=KICK)            # Луна
v("0411", 5.10, 11.84, zoom=(1.00, 1.06), focus=(0.5, 0.5), kick=KICK)           # Умеренность
v("0410", 0.86, 9.40, zoom=(1.00, 1.06), focus=(0.5, 0.5), kick=KICK)            # Сила
v("0410", 24.02, 26.45, zoom=(1.06, 1.10), focus=(0.5, 0.5))                      # «…подарить мужчине»
v("0406", 6.26, 15.45, zoom=(1.00, 1.06), focus=(0.5, 0.5), kick=KICK)           # Жрица
v("0407", 3.88, 11.66, zoom=(1.00, 1.06), focus=(0.5, 0.5), kick=KICK)           # Правосудие
v("0409", 6.10, 10.66, gain=2, zoom=(1.00, 1.05), focus=(0.5, 0.5), kick=KICK)   # размер
SHOTS.append(dict(src="papesse_ph", t_in=0.0, dur=3.2, zoom=(1.00, 1.05), focus=(0.5, 0.5), flash=True))
AUDIO.append(("0409", 0.3, 3.2, -8))                                        # under the end card

_t = [0.0]
for s in SHOTS[:-1]:
    _t.append(_t[-1] + s["dur"])
POPS.append((0.15, 2.5, "8 БЛЮД DIOR MAISON", "по мотивам карт Таро", TOP, 0))
card("ЗВЕЗДА", "L'Étoile", "надежда и вдохновение", 2.8)
card("КОЛЕСО ФОРТУНЫ", "La Roue de la Fortune", "перемены и удача", _t[1] + 0.15)
card("СОЛНЦЕ", "Le Soleil", "радость, успех и тепло", _t[2] + 0.1)
card("ЛУНА ", "La Lune", "интуиция и женственность", _t[3] + 0.15)
card("УМЕРЕННОСТЬ", "La Tempérance", "баланс и спокойствие", _t[4] + 0.15)
card("СИЛА\u00a0", "La Force", "внутренняя сила и смелость", _t[5] + 0.15)
POPS.append((_t[6] + 0.1, 2.1, "ПОДАРОК МУЖЧИНЕ", None, TOP, 0))
card("ЖРИЦА", "La Papesse", "мудрость и тайные знания", _t[7] + 0.15)
card("ПРАВОСУДИЕ", "La Justice", "честность и верные решения", _t[8] + 0.15)
POPS.append((_t[9] + 0.4, 3.6, "≈ 20,5 × 18 СМ", "размер блюда", TOP, 0))
END = ("ДОПОЛНИТЕ НАБОР\nИЛИ ПОДАРИТЕ ОТДЕЛЬНО", "8 блюд Dior Maison «Таро» • доставка из Китая", 3.2)
