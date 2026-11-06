"""Web app API (FastAPI) + the static iPhone-friendly frontend in agent/web/.

Login: one access code (WEB_PASSWORD in .env) → signed cookie for 90 days.
Uploads: resumable, in chunks (Safari on iPhone drops long requests; the app resumes from the
server's offset) — no size limit, files land in work/agent/<proj>/inbox/ like the bot's downloads.
"""
from __future__ import annotations

import asyncio, hashlib, hmac, json, os, re, secrets, time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import jobs, projects
from .config import ROOT

STATIC = Path(__file__).parent / "web"
COOKIE = "agent_auth"
MAX_VARIANTS = int(os.environ.get("MAX_VARIANTS", 30))
_secret_file = ROOT / "work" / "agent" / ".web_secret"


def _secret() -> bytes:
    if not _secret_file.exists():
        _secret_file.parent.mkdir(parents=True, exist_ok=True)
        _secret_file.write_text(secrets.token_hex(32))
    return (_secret_file.read_text().strip() + os.environ.get("WEB_PASSWORD", "")).encode()


def _token(exp: int) -> str:
    return f"{exp}.{hmac.new(_secret(), str(exp).encode(), hashlib.sha256).hexdigest()}"


def _authed(req: Request) -> bool:
    t = req.cookies.get(COOKIE, "")
    exp, _, sig = t.partition(".")
    return exp.isdigit() and int(exp) > time.time() and hmac.compare_digest(t, _token(int(exp)))


app = FastAPI(title="Video agent", docs_url=None, redoc_url=None)
TASKS: set[asyncio.Task] = set()


@app.middleware("http")
async def guard(req: Request, call_next):
    p = req.url.path
    if (p.startswith("/api/") and p not in ("/api/login", "/api/me")) or p.startswith("/files/"):
        if not _authed(req):
            return JSONResponse({"error": "login"}, status_code=401)
    return await call_next(req)


def _bg(coro):
    t = asyncio.create_task(coro)
    TASKS.add(t)
    t.add_done_callback(TASKS.discard)


def _proj(pid: str) -> projects.State:
    st = projects.load(pid)
    if not st:
        raise HTTPException(404, "нет такого проекта")
    return st


def _view(st: projects.State, full: bool = False) -> dict:
    v = {"id": st.id, "title": st.title or st.id, "created": st.created, "stage": st.stage, "template": st.template,
         "variants": st.variants, "inputs": [Path(x).name if not x.startswith("http") else "Google Drive" for x in st.inputs],
         "status": st.status[-12:], "error": st.error, "failed": st.failed, "queued": jobs.queued(), "owner": st.owner}
    res = projects.results(st)
    v["results_count"] = len(res)
    if full:
        md = st.work / "plans.md"
        chk = st.work / "check.json"
        v["plans_md"] = md.read_text() if md.exists() else ""
        v["checks"] = json.loads(chk.read_text())["checks"] if chk.exists() else []
        v["results"] = [{"id": r["id"], "angle": r["angle"], "caption": r["caption"], "mb": r["mb"],
                         "preview": f"/files/{st.id}/{r['preview'].name}", "master": f"/files/{st.id}/{r['master'].name}"} for r in res]
    return v


# ---------------------------------------------------------------- auth

@app.get("/api/me")
async def me(req: Request):
    return {"authed": _authed(req), "configured": bool(os.environ.get("WEB_PASSWORD"))}


@app.post("/api/login")
async def login(req: Request):
    body = await req.json()
    pw = os.environ.get("WEB_PASSWORD", "")
    await asyncio.sleep(0.5)  # slows down guessing
    if not pw or not hmac.compare_digest(str(body.get("code", "")).strip(), pw):
        raise HTTPException(403, "неверный код" if pw else "WEB_PASSWORD не задан в .env на сервере")
    resp = JSONResponse({"ok": True})
    exp = int(time.time()) + 90 * 86400
    resp.set_cookie(COOKIE, _token(exp), max_age=90 * 86400, httponly=True, samesite="lax",
                    secure=req.headers.get("x-forwarded-proto", req.url.scheme) == "https")
    return resp


@app.post("/api/logout")
async def logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(COOKIE)
    return resp


# ---------------------------------------------------------------- projects

@app.get("/api/templates")
async def templates():
    return {"templates": [{"name": k, "description": v} for k, v in projects.templates().items()], "max_variants": MAX_VARIANTS}


@app.get("/api/projects")
async def list_projects():
    return {"projects": [_view(s) for s in projects.list_projects()[:50]]}


@app.post("/api/projects")
async def create_project(req: Request):
    body = await req.json() if req.headers.get("content-length", "0") != "0" else {}
    title = str(body.get("title", "")).strip()[:80] or time.strftime("Ролик %d.%m %H:%M")
    return _view(projects.create(owner="web", prefix="web", title=title))


@app.get("/api/projects/{pid}")
async def get_project(pid: str):
    return _view(_proj(pid), full=True)


@app.delete("/api/projects/{pid}")
async def delete_project(pid: str):
    import shutil

    st = _proj(pid)
    if st.id in jobs.RUNNING:
        raise HTTPException(409, "проект сейчас в работе")
    shutil.rmtree(st.work, ignore_errors=True)
    shutil.rmtree(ROOT / "public" / "agent" / pid, ignore_errors=True)
    for f in (ROOT / "out").glob(f"agent_{pid}_*"):
        f.unlink(missing_ok=True)
    for f in (ROOT / "public").glob(f"agent_{pid}_*.props.json"):
        f.unlink(missing_ok=True)
    projects.LIVE.pop(pid, None)
    return {"ok": True}


@app.post("/api/projects/{pid}/links")
async def add_link(pid: str, req: Request):
    st = _proj(pid)
    url = str((await req.json()).get("url", "")).strip()
    if not re.match(r"https?://drive\.google\.com/\S+$", url):
        raise HTTPException(400, "нужна ссылка на файл в Google Drive")
    if st.stage != "collect":
        raise HTTPException(409, "проект уже запущен")
    st.inputs.append(url)
    st.save()
    return _view(st)


@app.post("/api/projects/{pid}/inputs/{idx}/delete")
async def remove_input(pid: str, idx: int):
    st = _proj(pid)
    if st.stage != "collect" or not 0 <= idx < len(st.inputs):
        raise HTTPException(409, "нельзя")
    x = st.inputs.pop(idx)
    if not x.startswith("http"):
        Path(x).unlink(missing_ok=True)
    st.save()
    return _view(st)


@app.post("/api/projects/{pid}/start")
async def start(pid: str, req: Request):
    st = _proj(pid)
    body = await req.json()
    if st.stage not in ("collect",):
        raise HTTPException(409, "проект уже запущен")
    if not st.inputs:
        raise HTTPException(400, "сначала загрузите видео")
    tpl = str(body.get("template", st.template))
    if tpl not in projects.templates():
        raise HTTPException(400, "нет такого шаблона")
    st.template, st.variants = tpl, max(1, min(MAX_VARIANTS, int(body.get("variants", st.variants))))
    st.stage, st.status = "analysing", []
    st.save()
    _bg(jobs.analyse_and_plan(st))
    return _view(st)


@app.post("/api/projects/{pid}/feedback")
async def feedback(pid: str, req: Request):
    st = _proj(pid)
    text = str((await req.json()).get("text", "")).strip()
    if st.stage not in ("review", "done") or not text:
        raise HTTPException(409, "сейчас правки не принимаются")
    st.stage = "planning"
    st.save()
    _bg(jobs.replan(st, text))
    return _view(st)


@app.post("/api/projects/{pid}/render")
async def render(pid: str):
    st = _proj(pid)
    if st.stage not in ("review", "done"):
        raise HTTPException(409, "сначала нужен план")
    st.stage = "rendering"
    st.save()
    _bg(jobs.render(st))
    return _view(st)


@app.post("/api/projects/{pid}/retry")
async def retry(pid: str):
    st = _proj(pid)
    if st.stage != "error":
        raise HTTPException(409, "нечего повторять")
    st.stage = "rendering" if st.failed == "render" else "planning"
    st.save()
    _bg(jobs.retry(st))
    return _view(st)


# ---------------------------------------------------------------- resumable uploads

def _upload_paths(st: projects.State, uid: str) -> tuple[Path, Path]:
    if not re.fullmatch(r"[0-9a-f]{16}", uid):
        raise HTTPException(404, "нет такой загрузки")
    d = st.work / "uploads"
    return d / f"{uid}.part", d / f"{uid}.json"


@app.post("/api/projects/{pid}/uploads")
async def upload_create(pid: str, req: Request):
    st = _proj(pid)
    if st.stage != "collect":
        raise HTTPException(409, "проект уже запущен")
    body = await req.json()
    name = Path(str(body.get("name", "video.mp4"))).name[:120]
    size = int(body.get("size", 0))
    if size <= 0:
        raise HTTPException(400, "пустой файл")
    uid = secrets.token_hex(8)
    part, meta = _upload_paths(st, uid)
    part.parent.mkdir(parents=True, exist_ok=True)
    part.touch()
    meta.write_text(json.dumps({"name": name, "size": size}))
    return {"uid": uid, "received": 0, "size": size}


@app.get("/api/projects/{pid}/uploads/{uid}")
async def upload_status(pid: str, uid: str):
    st = _proj(pid)
    part, meta = _upload_paths(st, uid)
    if not meta.exists():
        raise HTTPException(404, "нет такой загрузки")
    m = json.loads(meta.read_text())
    return {"uid": uid, "received": part.stat().st_size if part.exists() else m["size"], "size": m["size"], "done": not part.exists()}


@app.put("/api/projects/{pid}/uploads/{uid}")
async def upload_chunk(pid: str, uid: str, offset: int, req: Request):
    st = _proj(pid)
    part, meta = _upload_paths(st, uid)
    if not meta.exists() or not part.exists():
        raise HTTPException(404, "нет такой загрузки")
    m = json.loads(meta.read_text())
    have = part.stat().st_size
    if offset != have:  # client is out of sync (a chunk was lost / sent twice) — tell it where to continue
        return JSONResponse({"received": have, "size": m["size"]}, status_code=409)
    with open(part, "ab") as f:
        async for chunk in req.stream():
            if f.tell() + len(chunk) > m["size"]:
                f.truncate(have)
                raise HTTPException(400, "больше заявленного размера")
            f.write(chunk)
    have = part.stat().st_size
    done = have == m["size"]
    if done:
        inbox = st.work / "inbox"
        inbox.mkdir(exist_ok=True)
        ext = Path(m["name"]).suffix.lower() or ".mp4"
        dst = inbox / f"src{len(st.inputs)}_{uid[:4]}{ext}"
        part.replace(dst)
        st.inputs.append(str(dst))
        if st.title.startswith("Ролик ") and len(st.inputs) == 1:
            st.title = Path(m["name"]).stem[:60] or st.title
        st.save()
    return {"received": have, "size": m["size"], "done": done}


# ---------------------------------------------------------------- results

@app.get("/files/{pid}/{name}")
async def files(pid: str, name: str, download: int = 0):
    st = _proj(pid)
    if not re.fullmatch(rf"agent_{re.escape(st.id)}_\w+_(preview|master)\.mp4", name):
        raise HTTPException(404)
    path = ROOT / "out" / name
    if not path.exists():
        raise HTTPException(404)
    nice = name.replace(f"agent_{st.id}_", f"{(st.title or 'video')[:40]}_")
    return FileResponse(path, media_type="video/mp4", filename=nice if download else None,
                        content_disposition_type="attachment" if download else "inline")


app.mount("/", StaticFiles(directory=STATIC, html=True), name="static")
