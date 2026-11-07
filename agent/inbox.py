"""Server-side file exchange: sources go into the inbox folder, finished videos are published to out/ready/.

  inbox/                       drop videos here (copy, SFTP/WinSCP, a synced folder …) — the bot lists them
  out/ready/<date>_<name>/     finished masters (1080×1920) with friendly names + the post text next to each
"""
from __future__ import annotations

import os, re, shutil, time
from pathlib import Path

from .config import INBOX, READY
from .projects import State, results

VIDEO_EXT = {".mp4", ".mov", ".m4v", ".mkv", ".avi", ".webm", ".mts"}


def list_videos(limit: int = 12) -> list[dict]:
    """newest first; fresh = modified in the last 15 s, i.e. probably still being copied"""
    INBOX.mkdir(parents=True, exist_ok=True)
    now = time.time()
    out = []
    for p in INBOX.iterdir():
        if p.is_file() and p.suffix.lower() in VIDEO_EXT and not p.name.startswith("."):
            st = p.stat()
            out.append({"path": p, "name": p.name, "size": st.st_size, "mtime": st.st_mtime, "fresh": now - st.st_mtime < 15})
    return sorted(out, key=lambda x: x["mtime"], reverse=True)[:limit]


def human_size(n: int) -> str:
    return f"{n / 2**30:.1f} ГБ" if n >= 2**30 else f"{n / 2**20:.0f} МБ"


def _slug(text: str) -> str:
    return re.sub(r"[^\w-]+", "_", text, flags=re.UNICODE).strip("_")[:40] or "video"


def publish(st: State) -> Path | None:
    """finished masters → out/ready/<date>_<name>/<id>.mp4 (a hard link: no second copy on disk; a copy where
    links are not possible) and <id>.txt with the post text. Returns the folder."""
    res = results(st)
    if not res:
        return None
    first = st.inputs[0] if st.inputs else ""
    base = Path(first).stem if first and not first.startswith("http") else st.title
    folder = READY / f"{time.strftime('%m%d_%H%M', time.localtime(st.created))}_{_slug(base)}"
    folder.mkdir(parents=True, exist_ok=True)
    for r in res:
        dst = folder / f"{r['id']}.mp4"
        dst.unlink(missing_ok=True)
        try:
            os.link(r["master"], dst)
        except OSError:
            shutil.copy2(r["master"], dst)
        (folder / f"{r['id']}.txt").write_text(f"{r['angle']}\n\n{r['caption']}\n", encoding="utf-8")
    return folder
