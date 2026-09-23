#!/bin/bash
# Idempotent setup for restaurant promo ads (separate from the interview-reel preset).
# Reuses the reel setup for ffmpeg / node / Chrome / Inter, then adds the display fonts.
#   bash scripts/promo/setup.sh
set -euo pipefail
cd "$(dirname "$0")/../.."
command -v ffmpeg >/dev/null && [ -d node_modules/remotion ] && [ -s public/fonts/Inter-800.ttf ] || bash scripts/reel/setup.sh
mkdir -p public/fonts
# file name → Google Fonts family spec (all with Cyrillic)
for pair in "GreatVibes-400:Great+Vibes" "Caveat-700:Caveat:wght@700" "Pacifico-400:Pacifico" "MarckScript-400:Marck+Script"; do
  f="public/fonts/${pair%%:*}.ttf"
  [ -s "$f" ] && continue
  url=$(curl -fsS -A "Mozilla/4.0" "https://fonts.googleapis.com/css2?family=${pair#*:}" | grep -o 'https://[^)]*\.ttf' | head -1)
  curl -fsSL -o "$f" "$url"
done
echo "promo pipeline ready"
