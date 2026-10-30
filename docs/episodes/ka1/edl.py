"""v3 (user: «нужна полная версия», 1:27) — NOTHING is cut: rows are contiguous (each out = next in) from 0 to
the last frame; rows only switch framing and mark the quiet speaker for the gain. Notes on cut phrases below
are v1 history; captions keep the best reading of doubtful words; the off-script talk at the end has no captions.

Анонс мастер-класса Екатерины Гиль — Екатерина (red top, left) + Екатерина Гиль (white dress,
right), outdoors, one vertical take 1080×1920.

Гиль's voice was recorded 6–11 dB quieter and closer to the street noise → her clips are marked as
HOST_CLIPS so restore_audio levels them to the left speaker; mild DFN only (stronger suppression
"eats" her words). Doubtful words checked by forced choice on boosted audio: «рада познакомиться»,
«про вкус китайцев», «самые короткие пути», «закуплюсь на 200 тысяч», «приезжая в Гуанчжоу»,
. Cut: «приходите в воскресенье/на прослушивание» (tie), «про все … камни»
adjective tied (→ «подводные» by meaning), «про всё, что любят китайцы. И про всё. И байеры»
(unclear), the repeated «или реальные кейсы», the crude «просто потрахать мозги» sentence, the
outtakes at the end. Also cut: «если вы не знаете, вы (не) можете узнать… выстроить всю дорогу» — «можете / не можете»
is a tie that flips the meaning. Speaker changes with no pause are split at one point (equal OVR).
"""
GUEST = "ЕКАТЕРИНА ГИЛЬ"
GUEST_SUB = "спикер мастер-класса • фэшн-индустрия"
LOWER_THIRD_CLIP = "g1"
END_TITLE = "МАСТЕР-КЛАСС\nЕКАТЕРИНЫ ГИЛЬ"
END_SUB = "1 ноября, воскресенье • «Наше место»"
OUTRO = None   # full version: no end card over the footage; the date is a plate at the start
LOWER_EXTRA = [("w1a", 0.3, 5.0, "1 НОЯБРЯ", "воскресенье • мастер-класс • «Наше место»")]
SPEED = 1.0

FACE_MIN_W = 0.05
HOST_SIDE = "R"
SHOTS = {
    "W": (1.00, "both"),   # both
    "K": (1.45, "L"),      # Екатерина (red)
    "G": (1.45, "R"),      # Екатерина Гиль (white)
}
HOST_CLIPS = ["g1", "g3", "g5"]   # the quiet speaker — levelled up to the other voice

E = [
 ("w1a",0.00,9.50,"W","В это воскресенье в «Нашем месте» будет эксперт, которого обязательно нужно послушать всем, кто занимается, кто связан с фэшн-индустрией.",["фэшн-индустрией."],None),
 ("w1b",9.50,21.36,"K","Всем привет-привет! Не знаю, какое время суток вас застало, а нас застал прекрасный вечер в городе Гуанчжоу. Город потрясающих возможностей, которыми обязательно надо пользоваться. Я Екатерина и представляю вам Екатерину.",["Гуанчжоу."],(18.45,"W")),
 ("g1",21.36,32.13,"G","Рада познакомиться с вами. Приходите в воскресенье — буду рассказывать про ритейл, про вкус китайцев, про все подводные камни и про всё, что любят китайцы. И про всё. И байеры, потому что",["ритейл,"],(27.00,"W")),
 ("g3",32.13,43.74,"G","сейчас интернет переполнен информацией о том, как легко работать с Китаем, никто не рассказывает реальные кейсы, или реальные кейсы. Я в Китае с 2018 года, я прошла всю эту школу, и у меня есть чем с вами поделиться.",["реальные","кейсы,"],(38.70,"W")),
 ("w2a",43.74,48.95,"K","Самые крутые фабрики, самые сложные кейсы, самые короткие пути —",["крутые","фабрики,"],None),
 ("w2b",48.95,52.08,"W","эта женщина знает, как их пройти.",[],None),
 ("w2c",52.08,61.07,"K","Самое интересное, что многие думают: я приеду в Китай, закуплюсь на 200 тысяч и стану миллионером.",["миллионером."],None),
 ("w2d",61.07,65.56,"W","Приезжая в Гуанчжоу, твои намерения должны быть конкретными. Ты",["конкретными."],None),
 ("w2e",65.56,68.21,"K","должен понимать конкретный запрос.",[],None),
 ("w3",68.21,72.02,"W","Если таких запросов нет и просто потрахать мозги — то это не сюда. Не сюда.",["не","сюда."],None),
 ("g5",72.02,79.78,"G","Китай — для тех, кто знает, что нужно. Если вы не знаете — вы можете узнать, потому что нужно правильно и грамотно выстроить всю дорогу.",["знает,","что","нужно."],(75.00,"W")),
 ("tail",79.78,87.20,"W","",[],None),
]

OVR = {r[0]: (r[1], r[2]) for r in E}

AUDIO = {   # mild: her low-SNR voice must not be "eaten"
    "dfn_db": 4,
    "wpe_taps": 3,
    "pre_gain": {c: 8 for c in HOST_CLIPS},   # Гиль was recorded ~8 dB quieter
    "post": "highpass=f=80:p=2,equalizer=f=220:t=q:w=1.0:g=-1.5,equalizer=f=2800:t=q:w=1.2:g=2.5,deesser=i=0.15,"
            "acompressor=threshold=-26dB:ratio=2.5:attack=8:release=200:makeup=3,alimiter=limit=0.89:level=false",
}
