"""Projects on disk — shared by the Telegram bot and the web app.

work/agent/<proj>/state.json holds what the interfaces need between restarts:
  stage     collect → analysing → planning → review → rendering → done   (or error)
  inputs    source files (inbox/…) and Google Drive links, in order
  template, variants, owner ("web" or a Telegram chat id), title
  status    the last progress lines, error — the last failure, failed — which step to retry
"""
from __future__ import annotations

import json, re, secrets, threading, time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

from .config import ROOT, TEMPLATES, proj_dirs

BUSY = ("analysing", "planning", "rendering")
_lock = threading.Lock()
LIVE: dict[str, "State"] = {}  # one object per project in this process — a job and a web request never race


@dataclass
class State:
    id: str
    owner: str = "web"
    title: str = ""
    created: float = field(default_factory=time.time)
    inputs: list[str] = field(default_factory=list)
    template: str = "live_showroom"
    variants: int = 3
    stage: str = "collect"
    status: list[str] = field(default_factory=list)
    error: str = ""
    failed: str = ""  # step to retry after an error: plan | replan | render
    feedback: str = ""  # the last revision request (retried with «replan»)

    @property
    def work(self) -> Path:
        return proj_dirs(self.id)[0]

    def save(self):
        with _lock:
            self.work.mkdir(parents=True, exist_ok=True)
            tmp = self.work / "state.json.tmp"
            tmp.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=1))
            tmp.replace(self.work / "state.json")

    def say(self, line: str):
        """progress line, safe to call from worker threads"""
        self.status = (self.status + [line.strip()])[-40:]
        self.save()


def new_id(prefix: str) -> str:
    return f"{prefix}_{time.strftime('%m%d_%H%M%S')}_{secrets.token_hex(2)}"


def create(owner: str = "web", prefix: str = "web", **kw) -> State:
    st = State(id=new_id(prefix), owner=owner, **kw)
    st.save()
    LIVE[st.id] = st
    return st


def valid_id(pid: str) -> bool:
    return bool(re.fullmatch(r"[\w-]{3,80}", pid))


def load(pid: str) -> State | None:
    if not valid_id(pid):
        return None
    if pid in LIVE:
        return LIVE[pid]
    p = proj_dirs(pid)[0] / "state.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text())
    st = State(**{k: v for k, v in d.items() if k in State.__dataclass_fields__})
    LIVE[pid] = st
    return st


def list_projects(owner: str | None = None) -> list[State]:
    root = ROOT / "work" / "agent"
    out = []
    for p in root.glob("*/state.json"):
        st = load(p.parent.name)
        if st and (owner is None or st.owner == owner):
            out.append(st)
    return sorted(out, key=lambda s: s.created, reverse=True)


def recover_after_restart():
    """a job that was running when the process stopped will never finish — let the user retry it"""
    for st in list_projects():
        if st.stage in BUSY:
            st.failed = "render" if st.stage == "rendering" else "plan"
            st.stage, st.error = "error", "Работа прервалась (сервер перезапускался). Нажмите «Повторить»."
            st.save()


def templates() -> dict[str, str]:
    return {p.stem: yaml.safe_load(p.read_text()).get("description", "") for p in sorted(TEMPLATES.glob("*.yaml"))}


def results(st: State) -> list[dict]:
    """rendered videos of this project, in plan order"""
    plans_p = st.work / "plans.json"
    if not plans_p.exists():
        return []
    out = []
    for p in json.loads(plans_p.read_text())["plans"]:
        name = f"agent_{st.id}_{p['id']}"
        prev, master = ROOT / "out" / f"{name}_preview.mp4", ROOT / "out" / f"{name}_master.mp4"
        if prev.exists() and master.exists():
            out.append({"id": p["id"], "angle": p["angle"], "caption": (p["caption_text"] + "\n\n" + " ".join(p["hashtags"])).strip(),
                        "preview": prev, "master": master, "mb": round(master.stat().st_size / 2**20)})
    return out
