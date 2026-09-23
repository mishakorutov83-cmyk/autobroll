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

for w in 500 600 700 800; do
  f="public/fonts/Inter-$w.ttf"
  [ -s "$f" ] && continue
  url=$(curl -fsS "https://fonts.googleapis.com/css2?family=Inter:wght@$w" | grep -o 'https://[^)]*\.ttf' | head -1)
  curl -fsSL -o "$f" "$url"
done

[ -s "$CACHE/yunet.onnx" ] || curl -fsSL -o "$CACHE/yunet.onnx" \
  "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"

# pre-download the Whisper model so the first transcription starts immediately
python3 - <<PY
import sys; sys.path.insert(0, "scripts/reel")
import preset
from faster_whisper.utils import download_model
download_model(preset.WHISPER_MODEL, cache_dir="$CACHE/whisper")
PY
echo "reel pipeline ready"
