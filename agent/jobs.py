"""Heavy work for both interfaces (Telegram bot, web app): analyse → plan → render.

One job at a time (CPU / RAM bound), run in a worker thread so the event loop stays responsive.
Every step updates the project's state.json, so whoever looks — bot or web — sees the same progress.
"""
from __future__ import annotations

import asyncio, json, logging, time, traceback

from . import projects
from .projects import State

log = logging.getLogger("agent.jobs")
JOB = asyncio.Semaphore(1)
RUNNING: set[str] = set()  # project ids with a job in flight (waiting or working)


def queued() -> bool:
    return JOB.locked()


def api_hint(e: Exception) -> str:
    t = str(e).lower()
    if "credit balance" in t or "billing" in t:
        return "На счёте Claude API нет денег: console.anthropic.com → Billing. Потом нажмите «Повторить» — разбор видео повторять не придётся."
    if "authentication" in t or "api key" in t or "x-api-key" in t or "auth_token" in t:
        return "Неверный или пустой ANTHROPIC_API_KEY в .env."
    if "connection" in t or "forbidden" in t or "region" in t or "timed out" in t:
        return "Нет связи с Claude API — проверьте VPN («для всей системы»)."
    if "drive" in t or "gdown" in t:
        return "Google Drive не отдал файл — проверьте, что ссылка открыта «Всем, у кого есть ссылка»."
    return ""


async def _step(st: State, stage: str, title: str, fn, *args):
    st.stage, st.error = stage, ""
    st.say(f"⏳ {title}" + (" — ждёт очереди" if queued() else ""))
    RUNNING.add(st.id)
    try:
        async with JOB:
            st.say(f"⏳ {title}…")
            t0 = time.time()
            res = await asyncio.to_thread(fn, *args)
            st.say(f"✅ {title} — {time.time() - t0:.0f} с")
            return res
    finally:
        RUNNING.discard(st.id)


def _fail(st: State, step: str, e: Exception):
    log.error(traceback.format_exc())
    hint = api_hint(e)
    st.stage, st.failed = "error", step
    st.error = f"{type(e).__name__}: {str(e)[:400]}" + (f"\n\n{hint}" if hint else "")
    st.save()


def analysed(st: State) -> bool:
    pj = st.work / "project.json"
    return pj.exists() and [x["input"] for x in json.load(open(pj))["sources"]] == st.inputs


def _plan(st: State, feedback: str | None):
    from . import brain

    pj = json.load(open(st.work / "project.json"))
    pj["template"] = st.template
    json.dump(pj, open(st.work / "project.json", "w"), ensure_ascii=False, indent=1)
    ps = brain.plan(st.id, st.template, st.variants, feedback)
    rep = brain.check(st.id, ps)
    (st.work / "check.json").write_text(rep.model_dump_json(indent=1))


async def analyse_and_plan(st: State) -> bool:
    """collect → (analysing) → planning → review. A retry skips an analysis that already finished."""
    from .ingest import ingest

    try:
        if not analysed(st):
            await _step(st, "analysing", "Разбираю видео (речь, лица, кадры)", ingest, st.id, st.inputs, "ru", None, st.say)
        await _step(st, "planning", f"Монтирую по шаблону {st.template}", _plan, st, None)
    except Exception as e:
        _fail(st, "plan", e)
        return False
    st.stage = "review"
    st.save()
    return True


async def replan(st: State, feedback: str) -> bool:
    st.feedback = feedback
    try:
        await _step(st, "planning", "Переделываю план по правкам", _plan, st, feedback)
    except Exception as e:
        _fail(st, "replan", e)
        return False
    st.stage = "review"
    st.save()
    return True


async def render(st: State) -> list[dict] | None:
    from .render import render as _render

    try:
        await _step(st, "rendering", "Рендерю ролики", _render, st.id)
    except Exception as e:
        _fail(st, "render", e)
        return None
    st.stage = "done"
    st.save()
    return projects.results(st)


async def retry(st: State):
    if st.failed == "render":
        return await render(st)
    if st.failed == "replan" and st.feedback:
        return await replan(st, st.feedback)
    return await analyse_and_plan(st)
