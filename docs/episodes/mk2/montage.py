"""Мастер-класс Ксении (18.10) + караоке после — recap, ~31 s.

Clips: a/b hall during the masterclass (120 fps, 1280×720 rotated): a — Ксения with the mic in a
white shirt + the room, b — the full room listening; d duet on stage «Пейте, сударыня, вино»;
w woman singing at a table (seen from behind). Ксения's own words in these takes start mid-topic
(one is about buying invoices) → not used; the duet is the sound backbone from the first frame,
masterclass shots in slow motion under the topic plates, then the duet in sync, the room, the
message of the place and the weekly-masterclass end card.
"""
SOURCES = {
    "a": "raw/20261018_201406.mp4",
    "b": "raw/20261018_201934.mp4",
    "d": "raw/IMG_1769.MOV",
    "w": "raw/IMG_1771.MOV",
}
GRADE = "eq=saturation=1.15:contrast=1.06:gamma=0.98,unsharp=5:5:0.35:5:5:0"
XFADE = 0.3
KICK = 0.04
S = lambda src, t_in, dur, **k: dict(src=src, t_in=t_in, dur=dur, **k)

SHOTS = [
    # --- masterclass (slow motion, the song plays from the start)
    S("a", 1.5, 3.0, speed=0.5, zoom=(1.00, 1.08), focus=(0.5, 0.5)),                 # the room
    S("a", 7.0, 3.2, zoom=(1.12, 1.20), focus=(0.62, 0.5), kick=KICK),                # Ксения with the mic
    S("b", 1.8, 3.0, speed=0.5, zoom=(1.00, 1.08), focus=(0.5, 0.5), kick=KICK),      # listening
    S("b", 6.0, 3.2, speed=0.5, zoom=(1.05, 1.12), focus=(0.5, 0.5), kick=KICK),      # the room, sofa side
    # --- after: live music + karaoke (picture in sync with the song)
    S("d", 12.4, 6.0, zoom=(1.20, 1.30), focus=(0.5, 0.48), kick=KICK, flash=True),   # «…то ли умер, то ли ожил»
    S("w", 3.0, 3.2, zoom=(1.00, 1.08), focus=(0.4, 0.5), kick=KICK),                 # singing at the table
    S("d", 21.6, 3.5, zoom=(1.05, 1.12), focus=(0.5, 0.5), kick=KICK),                # «Нам с вами некого винить»
    # --- the place
    S("a", 15.4, 3.3, speed=0.5, zoom=(1.00, 1.08), focus=(0.5, 0.5), kick=KICK),     # the room
    S("b", 12.2, 3.0, speed=0.5, zoom=(1.00, 1.05), focus=(0.5, 0.5), flash=True),    # under the end card
]
# the duet from its first second runs under everything; its end → the singer at the table
AUDIO = [("d", 0.0, 28.4), ("w", 8.0, 3.0, -2)]

TOP = 10
_t = [0.0]
for s in SHOTS[:-1]:
    _t.append(_t[-1] + s["dur"])
POPS = [
    (_t[0] + 0.15, 2.8, "МАСТЕР-КЛАСС\nОТ КСЕНИИ", "18 октября • «Наше место»", TOP, 0),
    (_t[1] + 0.1, 3.0, "19 ЛЕТ ОПЫТА", "сопровождение бизнеса в Китае", TOP, 0),
    (_t[2] + 0.1, 2.8, "КОМПАНИЯ • СЧЕТА", "открытие компании • корпоративные счета", TOP, 0),
    (_t[3] + 0.1, 3.0, "НАЛОГИ • ВИЗЫ", "разобрали актуальные вопросы", TOP, 0),
    (_t[4] + 0.2, 3.6, "А ПОСЛЕ —\nЖИВАЯ МУЗЫКА", "и караоке", TOP, 0),
    (_t[7] + 0.1, 3.1, "ВКУСНО И ПОЛЕЗНО", "еда в кругу своих + полезные знания", TOP, 0),
]
END = ("МАСТЕР-КЛАССЫ\nКАЖДУЮ НЕДЕЛЮ", "о бизнесе и жизни в Китае • «Наше место»", 3.0)
