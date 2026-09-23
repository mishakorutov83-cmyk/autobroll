#!/bin/bash
set -euo pipefail
# Only in Claude Code on the web: prepare the interview-reel toolchain.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi
bash "$CLAUDE_PROJECT_DIR/scripts/reel/setup.sh"
