"""Nashe Mesto — «Девичник», суббота 26.09. Source: 195036.mp4 (464×848, 15.5 s, one handheld take).

Story: the girls' table waving and laughing (hook) → a second table of girls laughing →
a girl singing karaoke with friends (ties into the karaoke block, which lights up here).
The pan between the tables (3.6–4.7 s), the couch-only frames and the man entering at ~13.3 s are cut.
Source is short, so the first two fragments are gently slowed (interpolated).
"""

# (src_t, fx, fy, zoom): source point put at the window centre
CLIPS = [
    dict(src=(0.0, 3.6), speed=0.72, keys=[
        (0.0, 0.62, 0.47, 1.12),
        (1.4, 0.58, 0.45, 1.08),
        (2.4, 0.62, 0.44, 1.10),
        (3.6, 0.60, 0.44, 1.14),
    ]),
    dict(src=(4.7, 6.3), speed=0.72, keys=[
        (4.7, 0.62, 0.44, 1.22),
        (5.5, 0.50, 0.43, 1.18),
        (6.3, 0.42, 0.43, 1.18),
    ]),
    dict(src=(7.7, 13.25), speed=0.88, keys=[
        (7.7, 0.62, 0.43, 1.12),
        (8.8, 0.52, 0.40, 1.14),
        (9.8, 0.44, 0.41, 1.16),
        (11.8, 0.38, 0.43, 1.20),
        (13.25, 0.34, 0.43, 1.24),
    ]),
]

# the source sound is the venue's music — keep it as one continuous bed under the cuts
AUDIO = dict(mode="bed", src_start=0.0)

GRADE = "eq=contrast=1.05:brightness=0.02:saturation=1.12,colorbalance=rs=0.03:bs=0.02:rm=0.02"

FRAME = dict(
    theme=dict(bgTop="#d3136c", bgMid="#b30b58", bgDeep="#5e0430", accent="#e2187a", ink="#c80f67",
               paper="#fff4f8", glow="#ff7ab8"),
    brand=dict(name="Nashe Mesto", lines=["РЕСТОРАН • БАР", "В ФОШАНЕ"]),
    badge=dict(top="В ЭТУ СУББОТУ", big="26.09"),
    headline="ДЕВИЧНИК",
    offer=dict(prefix="СКИДКА", big="30%", sub="НА ОСНОВНОЕ МЕНЮ"),
    terms=["ТОЛЬКО ЕДА  •  АЛКОГОЛЬ НЕ ВХОДИТ", "АКЦИЯ ДЕЙСТВУЕТ НА КОМПАНИЮ ОТ 3-Х ДЕВУШЕК"],
    features=[dict(icon="mic", title="КАРАОКЕ-ВЕЧЕР", sub="20:00–01:00"),
              dict(icon="guitar", title="ЖИВАЯ МУЗЫКА", sub="")],
    featureAccentClip=2,  # the karaoke block lights up when the singer appears
)
