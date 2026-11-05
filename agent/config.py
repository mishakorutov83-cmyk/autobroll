"""Paths and knobs for the video agent."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = Path(__file__).parent / "templates"
MODELS = Path(os.environ.get("REEL_MODELS", Path.home() / ".cache" / "autobroll"))

# brain
MODEL = os.environ.get("AGENT_MODEL", "claude-opus-5-5")
EFFORT = os.environ.get("AGENT_EFFORT", "high")

# analysis
WHISPER_MODEL = os.environ.get("REEL_WHISPER", "large-v3-turbo")
SHEET_STEP = 1.5  # seconds between contact-sheet frames
SHEET_COLS, SHEET_ROWS = 8, 5


def proj_dirs(proj: str) -> tuple[Path, Path]:
    """work dir (analysis, plans) and public dir (render proxies — Remotion reads public/)."""
    return ROOT / "work" / "agent" / proj, ROOT / "public" / "agent" / proj
