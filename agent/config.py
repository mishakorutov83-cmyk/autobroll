"""Paths and knobs for the video agent."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATES = Path(__file__).parent / "templates"
MODELS = Path(os.environ.get("REEL_MODELS", Path.home() / ".cache" / "autobroll"))

# brain: which Claude model and how much thinking each step gets. Output tokens (the model's reasoning and the
# plans it writes) are most of the bill, so model and effort are the levers that matter.
#   AGENT_PROFILE = quality | balanced (default) | economy
#   or per step:  AGENT_MODEL / AGENT_EFFORT (main plan), AGENT_VARIANT_MODEL / AGENT_VARIANT_EFFORT, AGENT_CHECK_MODEL / AGENT_CHECK_EFFORT
OPUS, SONNET, HAIKU = "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"
PROFILES = {  # step → (model, effort)
    "quality": {"main": (OPUS, "high"), "variants": (OPUS, "high"), "check": (OPUS, "medium")},
    "balanced": {"main": (OPUS, "medium"), "variants": (SONNET, "medium"), "check": (SONNET, "low")},
    "economy": {"main": (SONNET, "medium"), "variants": (HAIKU, "medium"), "check": (HAIKU, "low")},
}


def llm(step: str) -> tuple[str, str]:
    """(model, effort) for a step: main | variants | check | revise (revise follows main)"""
    profile = os.environ.get("AGENT_PROFILE", "balanced")
    model, effort = PROFILES.get(profile, PROFILES["balanced"])["main" if step == "revise" else step]
    if step in ("main", "revise"):
        return os.environ.get("AGENT_MODEL") or model, os.environ.get("AGENT_EFFORT") or effort
    key = {"variants": "VARIANT", "check": "CHECK"}[step]
    return os.environ.get(f"AGENT_{key}_MODEL") or model, os.environ.get(f"AGENT_{key}_EFFORT") or effort

# server-side files: sources are dropped into INBOX, finished videos are published to READY (out/ready)
INBOX = Path(os.environ.get("AGENT_INBOX") or ROOT / "inbox")
READY = ROOT / "out" / "ready"

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
