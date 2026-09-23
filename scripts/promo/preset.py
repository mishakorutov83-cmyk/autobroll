"""Restaurant promo-ad preset (Nashe Mesto акции) — separate from the interview series.

Format: Instagram Reels + Stories, 9:16, 1080×1920, H.264/AAC, 30 fps, ~13–15 s.
Look: a STATIC branded frame (layout in src/promo/) with live video in a large window.
Per-promo content (fragments, framing keyframes, texts, colours) lives in promos/<id>/spec.py.
"""

FPS = 30
W, H = 1080, 1920
COMPOSITION = "Promo"

# live-video window inside the frame (px, output coords) — big: the video is the hero
WINDOW = dict(x=28, y=212, w=1024, h=1016, radius=44)

# mezzanine clips: upscaled once with lanczos + light sharpening, so Remotion only positions them
MEZZ_W = 1080
MEZZ_CRF = 14
SHARPEN = "unsharp=5:5:0.55:5:5:0.0"
# slow-motion (speed < 1) is interpolated instead of duplicating frames when this is on
SMOOTH_SLOWMO = True

XFADE = 0.20  # soft cross-dissolve between fragments (s)
FADE_OUT = 0.45  # short fade at the very end (s); the offer stays on screen until then

LOUDNESS = "loudnorm=I=-14:TP=-1.5:LRA=9"
PREVIEW_MAX_MB = 28
PREVIEW_W, PREVIEW_H = 720, 1280
