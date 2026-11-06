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
# speech model: REEL_WHISPER (name or folder), else files dropped into models/whisper-large-v3-turbo/
# (config.json, model.bin, preprocessor_config.json, tokenizer.json, vocabulary.json — downloaded by hand),
# else the name — faster-whisper downloads it once into MODELS/whisper
LOCAL_WHISPER = ROOT / "models" / "whisper-large-v3-turbo"


def whisper_model() -> str:
    """checked on every video, so model files dropped into models/ work without a restart"""
    return os.environ.get("REEL_WHISPER") or (str(LOCAL_WHISPER) if (LOCAL_WHISPER / "model.bin").exists() else "large-v3-turbo")
SHEET_STEP = 1.5  # seconds between contact-sheet frames
SHEET_COLS, SHEET_ROWS = 8, 5


def proj_dirs(proj: str) -> tuple[Path, Path]:
    """work dir (analysis, plans) and public dir (render proxies — Remotion reads public/)."""
    return ROOT / "work" / "agent" / proj, ROOT / "public" / "agent" / proj
