"""Stage 4 — render approved plans (shared by the CLI and the Telegram bot)."""
from __future__ import annotations

import collections, json, re, subprocess, sys
from pathlib import Path

from . import brain
from .build import build
from .config import ROOT, proj_dirs


def run_logged(cmd: list[str], what: str):
    """run a step, keep its output in the container log AND in the error: «returned exit status 1» alone says nothing"""
    tail = collections.deque(maxlen=200)
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace")
    for line in proc.stdout:
        print(line, end="", flush=True)
        if line.strip():
            tail.append(line.rstrip()[:300])
    code = proc.wait()
    if code:
        hint = ""
        text = "\n".join(tail).lower()
        if code in (137, -9) or re.search(r"\bkilled\b|out of memory|\boom\b|oom-kill|target closed|browser crashed|page crashed", text):
            hint = ("\n\nПохоже, не хватило памяти: Docker Desktop (WSL2) отдаёт контейнеру мало RAM. "
                    "Закройте тяжёлые программы или увеличьте память WSL (файл .wslconfig, параметр memory=) и повторите.")
        lines = list(tail)
        # the child script ends with its own Python traceback, which would push out what actually failed (Remotion's or
        # ffmpeg's message): show the lines BEFORE the first traceback, then the final error line
        cut = next((i for i, l in enumerate(lines) if l.startswith("Traceback (most recent call last)")), len(lines))
        core = [l for l in lines[:cut] if not l.startswith("agent-1")][-14:]
        last = lines[-1] if lines else ""
        shown = core + ([last] if last and last not in core else [])
        raise RuntimeError(f"{what} завершился с ошибкой (код {code}). Что сообщил инструмент:\n" + "\n".join(shown or ["(вывода нет)"]) + hint)


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
        run_logged(cmd, f"Рендер {p.id}")
        if not stills:
            out.append({"id": p.id, "angle": p.angle, "master": ROOT / "out" / f"{name}_master.mp4",
                        "preview": ROOT / "out" / f"{name}_preview.mp4",
                        "caption": (p.caption_text + "\n\n" + " ".join(p.hashtags)).strip()})
    return out


def latest(proj: str) -> list[Path]:
    return sorted((ROOT / "out").glob(f"agent_{proj}_*_preview.mp4"))
