"""Series preset «Люди нашего места» — the look & feel fixed from episode 1 (Movsar).

Only style lives here (framing, captions, titles, sound, output). The story —
which fragments, in what order — is decided anew for every interview in the
episode's edl.py.
"""

FPS = 30
W, H = 1080, 1920

# speech speed (pitch-preserving). Change per episode in edl.py: SPEED = 1.0 / 1.10 / 1.15 / 1.20
SPEED = 1.10

# digital shot sizes: normal / medium / close-up (source is often a phone video —
# keep zooms moderate so faces stay sharp and heads are not cut)
N, M, C = 1.06, 1.16, 1.28
FACE_TARGET_Y = 0.30  # face centre height in the output frame
FACE_KEEP_X = 0.30  # how much of the face's off-centre position is kept (0 = centre it)

# captions
CAPTION_PRESET = "clean"
CAPTION_TOP_PCT = 63.5  # below faces, above the Reels UI
CAPTION_MAX_CHARS = 32  # per page (≤ 2 lines)
ACCENT = "#F2C14E"

# titles
LOWER_THIRD_SUB = "Китай • бизнес • личный опыт"
LOWER_THIRD_OFFSET, LOWER_THIRD_DUR = 0.15, 4.6
END_TITLE = "ЛЮДИ\nНАШЕГО МЕСТА"
END_SUB = "Новые истории людей из Китая"
END_DUR = 3.0

# sound: gentle levelling on the selected fragments, loudness on the master
AUDIO_FILTER = "highpass=f=70,afftdn=nf=-28,dynaudnorm=f=250:g=21:p=0.9:m=6:r=0.5,alimiter=limit=0.95"
LOUDNESS = "loudnorm=I=-14:TP=-1.5:LRA=9"

# cut handles kept around every fragment in the selects file (s)
HANDLE = 0.6

# preview for the chat (hard upload limit 30 MB)
PREVIEW_MAX_MB = 28
PREVIEW_W, PREVIEW_H = 720, 1280

# transcription. ep1 benchmark (10.5 min Russian, 4 CPU): large-v3 ≈ 13 min, large-v3-turbo ≈ 5 min;
# turbo differs mostly in fillers/phrase edges, a few content words need the usual caption proofreading.
# Override for a hard recording: REEL_WHISPER=large-v3
WHISPER_MODEL = "large-v3-turbo"
