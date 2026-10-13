"""Мастер-класс с Ксенией — анонс, v2 (re-edit after review).

v1 problems: the hook repeated Ксения's line later; doubled words at joins («в следующее
воскресенье» ×2, «бесплатно» ×2); cuts inside sentences with a framing change; zoom kicks and
constant framing changes; stickers at face level.
v2: an opening thought that is not repeated later → the story in order; cuts only between
sentences; calm framing (wide / medium two-shot, one medium single for Ксения's bio), no kicks,
no stickers — only name plates in the lower third and the CTA end card.
"""
GUEST = "КСЕНИЯ"
GUEST_SUB = "регистрация компаний • визы • бухгалтерия в Китае"
LOWER_THIRD_CLIP = "e6"
LOWER_THIRD_TOP = 54                 # below the faces, above the captions
LOWER_EXTRA = [("e9", 0.1, 5.0, "18 ОКТЯБРЯ • 19:00", "мастер-класс • «Наше место» • бесплатно")]
END_TITLE = "МАСТЕР-КЛАСС\n18 ОКТЯБРЯ\n19:00"
END_SUB = "«Наше место» • бесплатно • запись в директ"
OUTRO = (88.85, 91.25)
SPEED = 1.10

FACE_MIN_W = 0.05
SHOTS = {
    "W": (1.06, "both"),  # wide two-shot
    "t": (1.30, "both"),  # medium two-shot
    "K": (1.40, "L"),     # Ксения, medium
}
HOST_CLIPS = ["e7", "e1a", "e1b", "e2", "e3", "e8", "e9", "e10", "e13"]

E = [
 # --- opening thought (not repeated later)
 ("e7",43.55,51.45,"t","Я думаю, всем, кто планирует запустить свой бизнес в Китае, информация, которую расскажет Ксюша, будет очень полезна.",["свой","бизнес"],None),
 # --- the story, in order
 ("e1a",0.70,2.08,"W","Дорогие друзья,",[],None),
 ("e1b",3.27,4.70,"t","стартует Кантонская выставка.",["Кантонская"],None),
 ("e2",4.85,18.45,"W","И в преддверии этого события у нас с Ксюшей появилась замечательная идея — провести мастер-класс по открытию компании, по открытию расчётных счетов, по рабочим визам и всем подобным вопросам.",["мастер-класс"],None),
 ("e3",18.65,30.95,"t","Почему я решил предложить Ксюше провести данный мастер-класс? Да потому что сам пользуюсь её услугами, и она нам в этих вопросах во всех помогает. Ксюш, коротко расскажи о себе, вообще за твой бэкграунд.",[],(23.22,"W")),
 ("e6",31.25,41.60,"K","Я живу и работаю в Китае уже более 20 лет. Занимаюсь регистрацией компаний, открытием рабочих виз, ну и всё, что с этим связано.",["20","лет."],None),
 # --- when and where
 ("e8",52.12,54.18,"W","Встречаемся здесь, в «Нашем месте».",[],None),
 ("e9",63.40,65.80,"t","Ждём вас в 19 часов.",["19","часов."],None),
 ("e10",67.95,77.30,"W","Поэтому не упустите эту возможность бесплатно получить информацию и пополнить свою базу знаний от крутого эксперта. Да, и можете позадавать вопросы.",["бесплатно"],(75.93,"t")),
 # --- call to action
 ("e13",80.55,86.92,"W","Всё, всех ждём. Давайте, записывайтесь, пишите нам в Instagram, в комментарии.",["записывайтесь,"],None),
]

OVR = {"e1a": (0.70, 2.08), "e1b": (3.27, 4.70), "e8": (52.12, 54.18), "e13": (None, 86.92)}
# cut out (recorded a week earlier): «буквально на следующей неделе», «в следующее воскресенье»,
# «и на следующей неделе встретимся» — the date is on the plate and the end card instead

AUDIO = {
    "dfn_db": 8,
    "wpe_taps": 3,
    "post": "highpass=f=75:p=2,equalizer=f=220:t=q:w=1.0:g=-1.5,deesser=i=0.15,"
            "acompressor=threshold=-24dB:ratio=2:attack=10:release=200:makeup=2,alimiter=limit=0.89:level=false",
}
