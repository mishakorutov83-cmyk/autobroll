#!/bin/bash
# Idempotent setup for the interview-reel pipeline (ffmpeg, Python deps, node deps,
# Remotion's headless Chrome, Inter fonts, face model, Whisper model).
# Runs from the SessionStart hook; safe to run by hand: bash scripts/reel/setup.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
CACHE="${REEL_MODELS:-$HOME/.cache/autobroll}"
mkdir -p "$CACHE/whisper" public/fonts

if ! command -v ffmpeg >/dev/null; then
  (apt-get update -qq || true) && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq ffmpeg >/dev/null
fi

python3 -c "import faster_whisper, cv2, gdown" 2>/dev/null || \
  pip install -q --root-user-action=ignore -r scripts/reel/requirements.txt

[ -d node_modules/remotion ] || npm install --no-audit --no-fund --loglevel=error
npx remotion browser ensure >/dev/null 2>&1 || true

# flaky networks (VPN): every download retries instead of failing the whole setup
CURL="curl -fsSL --retry 6 --retry-delay 5 --retry-all-errors --connect-timeout 30"

for w in 500 600 700 800; do  # normally already in the repo (public/fonts, SIL OFL)
  f="public/fonts/Inter-$w.ttf"
  [ -s "$f" ] && continue
  url=$($CURL "https://fonts.googleapis.com/css2?family=Inter:wght@$w" | grep -o 'https://[^)]*\.ttf' | head -1)
  $CURL -o "$f" "$url"
done

[ -s "$CACHE/yunet.onnx" ] || $CURL -o "$CACHE/yunet.onnx" \
  "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"

# pre-download the Whisper model so the first transcription starts immediately
python3 - <<PY
import sys, time; sys.path.insert(0, "scripts/reel")
import preset
from faster_whisper.utils import download_model
for attempt in range(6):  # resumes partial files; survives a dropped VPN connection
    try:
        download_model(preset.WHISPER_MODEL, cache_dir="$CACHE/whisper")
        break
    except Exception as e:
        if attempt == 5:
            raise
        print(f"Whisper model download failed ({e}); retrying in 15 s", flush=True)
        time.sleep(15)
PY
echo "reel pipeline ready"
