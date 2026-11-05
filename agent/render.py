"""Stage 4 — render approved plans (shared by the CLI and the Telegram bot)."""
from __future__ import annotations

import json, subprocess, sys
from pathlib import Path

from . import brain
from .build import build
from .config import ROOT, proj_dirs


def render(proj: str, only: set[str] | None = None, stills: str | None = None) -> list[dict]:
    """→ [{id, master, preview, caption}] for every rendered plan"""
    work, _ = proj_dirs(proj)
    template = json.load(open(work / "project.json")).get("template", "stylist_story")
    out = []
    for p in brain.load(proj).plans:
        if only and p.id not in only:
            continue
        build(proj, p, template)
        name = f"agent_{proj}_{p.id}"
        cmd = [sys.executable, str(ROOT / "scripts" / "reel" / "render.py"), name]
        if stills:
            cmd += ["--stills", stills]
        subprocess.run(cmd, check=True, cwd=ROOT)
        if not stills:
            out.append({"id": p.id, "angle": p.angle, "master": ROOT / "out" / f"{name}_master.mp4",
                        "preview": ROOT / "out" / f"{name}_preview.mp4",
                        "caption": (p.caption_text + "\n\n" + " ".join(p.hashtags)).strip()})
    return out


def latest(proj: str) -> list[Path]:
    return sorted((ROOT / "out").glob(f"agent_{proj}_*_preview.mp4"))
