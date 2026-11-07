"""Web app API (FastAPI) + the static iPhone-friendly frontend in agent/web/.

Login: one access code (WEB_PASSWORD in .env) → signed cookie for 90 days.
Uploads: resumable, in chunks (Safari on iPhone drops long requests; the app resumes from the
server's offset) — no size limit, files land in work/agent/<proj>/inbox/ like the bot's downloads.
"""
from __future__ import annotations

import asyncio, hashlib, hmac, json, os, re, secrets, time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import inbox as inbox_mod, jobs, pricing, projects, tgauth
from .config import INBOX, ROOT

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
    if (p.startswith("/api/") and p not in ("/api/login", "/api/me", "/api/tg-login")) or p.startswith("/files/"):
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
         "status": st.status[-12:], "error": st.error, "brief": st.brief, "failed": st.failed, "queued": jobs.queued(), "owner": st.owner}
    res = projects.results(st)
    v["results_count"] = len(res)
    v["cost"] = pricing.line(st.id)
    if full:
        md = st.work / "plans.md"
        chk = st.work / "check.json"
        v["plans_md"] = md.read_text() if md.exists() else ""
        v["checks"] = json.loads(chk.read_text())["checks"] if chk.exists() else []
        v["results"] = [{"id": r["id"], "angle": r["angle"], "caption": r["caption"], "mb": r["mb"],
                         "preview": f"/files/{st.id}/{r['preview'].name}", "master": f"/files/{st.id}/{r['master'].name}"} for r in res]
    return v


# ---------------------------------------------------------------- auth

@app.get("/health")
async def health():
    """connectivity check: open <address>/health in the phone's browser — «ok» means the whole route works"""
    return PlainTextResponse("ok")


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
    return _session(req)


def _session(req: Request) -> JSONResponse:
    resp = JSONResponse({"ok": True})
    exp = int(time.time()) + 90 * 86400
    resp.set_cookie(COOKIE, _token(exp), max_age=90 * 86400, httponly=True, samesite="lax",
                    secure=req.headers.get("x-forwarded-proto", req.url.scheme) == "https")
    return resp


@app.post("/api/tg-login")
async def tg_login(req: Request):
    """opened from the Telegram bot's button: signed launch data instead of the access code"""
    body = await req.json()
    token, allowed = os.environ.get("BOT_TOKEN", ""), tgauth.allowed_ids()
    if not token or not allowed:  # without a list of allowed users any Telegram user could get in
        raise HTTPException(403, "вход через Telegram выключен: задайте BOT_TOKEN и ALLOWED_USERS")
    uid = tgauth.verify(str(body.get("initData", "")), token)
    if uid is None or uid not in allowed:
        raise HTTPException(403, "Telegram не подтвердил вход")
    return _session(req)


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
    if not x.startswith("http") and st.work.resolve() in Path(x).resolve().parents:  # never delete a file from the server's inbox
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
    st.brief = str(body.get("brief", st.brief)).strip()[:4000]
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
# One mechanism, two targets: a project's own folder, or the shared server inbox (what the bot lists).

def _upload_paths(folder: Path, uid: str) -> tuple[Path, Path]:
    if not re.fullmatch(r"[0-9a-f]{16}", uid):
        raise HTTPException(404, "нет такой загрузки")
    return folder / f"{uid}.part", folder / f"{uid}.json"


async def _upload_create(folder: Path, req: Request, videos_only: bool = False) -> dict:
    body = await req.json()
    name = Path(str(body.get("name", "video.mp4"))).name[:120] or "video.mp4"
    size = int(body.get("size", 0))
    if size <= 0:
        raise HTTPException(400, "пустой файл")
    if videos_only and (Path(name).suffix.lower() or ".mp4") not in inbox_mod.VIDEO_EXT | {""}:
        raise HTTPException(400, "это не видео")
    uid = secrets.token_hex(8)
    part, meta = _upload_paths(folder, uid)
    part.parent.mkdir(parents=True, exist_ok=True)
    for old in part.parent.iterdir():  # forget abandoned uploads after a week
        if time.time() - old.stat().st_mtime > 7 * 86400:
            old.unlink(missing_ok=True)
    part.touch()
    meta.write_text(json.dumps({"name": name, "size": size}))
    return {"uid": uid, "received": 0, "size": size}


def _upload_status(folder: Path, uid: str) -> dict:
    part, meta = _upload_paths(folder, uid)
    if not meta.exists():
        raise HTTPException(404, "нет такой загрузки")
    m = json.loads(meta.read_text())
    return {"uid": uid, "received": part.stat().st_size if part.exists() else m["size"], "size": m["size"], "done": not part.exists()}


async def _upload_chunk(folder: Path, uid: str, offset: int, req: Request, finish):
    part, meta = _upload_paths(folder, uid)
    if not meta.exists():
        raise HTTPException(404, "нет такой загрузки")
    m = json.loads(meta.read_text())
    if not part.exists():  # finished earlier and only the reply was lost: answer «done» again, do not start over
        return {"received": m["size"], "size": m["size"], "done": True}
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
        finish(part, uid, m)
    return {"received": have, "size": m["size"], "done": done}


def _project_uploads(st: projects.State) -> Path:
    return st.work / "uploads"


def _finish_project(st: projects.State):
    def finish(part: Path, uid: str, m: dict):
        box = st.work / "inbox"
        box.mkdir(exist_ok=True)
        ext = Path(m["name"]).suffix.lower() or ".mp4"
        dst = box / f"src{len(st.inputs)}_{uid[:4]}{ext}"
        part.replace(dst)
        st.inputs.append(str(dst))
        if st.title.startswith("Ролик ") and len(st.inputs) == 1:
            st.title = Path(m["name"]).stem[:60] or st.title
        st.save()
    return finish


@app.post("/api/projects/{pid}/uploads")
async def upload_create(pid: str, req: Request):
    st = _proj(pid)
    if st.stage != "collect":
        raise HTTPException(409, "проект уже запущен")
    return await _upload_create(_project_uploads(st), req)


@app.get("/api/projects/{pid}/uploads/{uid}")
async def upload_status(pid: str, uid: str):
    return _upload_status(_project_uploads(_proj(pid)), uid)


@app.put("/api/projects/{pid}/uploads/{uid}")
async def upload_chunk(pid: str, uid: str, offset: int, req: Request):
    st = _proj(pid)
    return await _upload_chunk(_project_uploads(st), uid, offset, req, _finish_project(st))


# ---- the shared server inbox: iPhone → server, listed by the Telegram bot («📁 Папка сервера»)

INBOX_TMP = INBOX / ".uploads"


def _finish_inbox(part: Path, uid: str, m: dict):
    name = Path(m["name"]).name
    stem, ext = Path(name).stem or "video", (Path(name).suffix.lower() or ".mp4")
    dst, n = INBOX / f"{stem}{ext}", 1
    while dst.exists():  # IMG_0042.MOV from two phones, or the same file sent twice — never overwrite
        dst, n = INBOX / f"{stem}_{n}{ext}", n + 1
    part.replace(dst)
    # the file arrived whole (renamed into place): don't show it as «still being copied» (that flag is for other tools)
    t = time.time() - 30
    os.utime(dst, (t, t))


@app.get("/api/inbox")
async def inbox_list():
    return {"files": [{"name": v["name"], "size": v["size"], "mtime": v["mtime"], "fresh": v["fresh"]} for v in inbox_mod.list_videos(60)],
            "folder": str(INBOX)}


@app.post("/api/inbox/uploads")
async def inbox_upload_create(req: Request):
    return await _upload_create(INBOX_TMP, req, videos_only=True)


@app.get("/api/inbox/uploads/{uid}")
async def inbox_upload_status(uid: str):
    return _upload_status(INBOX_TMP, uid)


@app.put("/api/inbox/uploads/{uid}")
async def inbox_upload_chunk(uid: str, offset: int, req: Request):
    return await _upload_chunk(INBOX_TMP, uid, offset, req, _finish_inbox)


@app.post("/api/projects/{pid}/inbox")
async def add_from_inbox(pid: str, req: Request):
    st = _proj(pid)
    if st.stage != "collect":
        raise HTTPException(409, "проект уже запущен")
    name = Path(str((await req.json()).get("name", ""))).name
    path = INBOX / name
    if not name or not path.is_file() or path.suffix.lower() not in inbox_mod.VIDEO_EXT:
        raise HTTPException(404, "нет такого файла в папке сервера")
    if str(path) not in st.inputs:
        st.inputs.append(str(path))
        st.save()
    return _view(st)


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
