"""Telegram bot — the interface to the video agent.

  python3 -m agent.bot          (env: BOT_TOKEN, ANTHROPIC_API_KEY, ALLOWED_USERS, BOT_API_URL)

Flow in the chat:
  1. send video files (as video or as file) and/or Google Drive links — all of them go into one project
  2. pick a template and the number of variants → «Монтировать»
  3. the bot sends the plan (hook, clips, captions, post text) + the meaning check
  4. «Рендер» — or «Правки» and write what to change in plain words → a new plan
  5. the bot sends every variant as a video with the post caption

Files > 20 MB: the official cloud Bot API refuses to download them, so in production the bot talks
to a self-hosted telegram-bot-api server (BOT_API_URL, docker-compose.yml) — up to 2 GB both ways.
Heavy work runs one job at a time in a worker thread; the chat stays responsive.
"""
from __future__ import annotations

import asyncio, json, logging, os, re, shutil, time, traceback
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from .config import TEMPLATES, proj_dirs

# .env saved by Windows Notepad can leave a stray \r or spaces around values
for _k in ("BOT_TOKEN", "ANTHROPIC_API_KEY", "ALLOWED_USERS", "BOT_API_URL", "AGENT_MODEL", "AGENT_EFFORT"):
    if _k in os.environ:
        os.environ[_k] = os.environ[_k].strip().strip('"').strip("'")
        if not os.environ[_k]:
            del os.environ[_k]

log = logging.getLogger("agent.bot")
router = Router()
JOB = asyncio.Semaphore(1)  # one heavy job at a time (CPU / RAM bound)
ALLOWED = {int(x) for x in re.findall(r"\d+", os.environ.get("ALLOWED_USERS", ""))}
LOCAL_API = bool(os.environ.get("BOT_API_URL"))
SEND_LIMIT = (2000 if LOCAL_API else 49) * 1024 * 1024
DRIVE = re.compile(r"https?://drive\.google\.com/\S+")


@dataclass
class Draft:
    proj: str
    inputs: list[str] = field(default_factory=list)
    template: str = "live_showroom"
    variants: int = 3
    stage: str = "collect"  # collect → planning → review → feedback → rendering → done
    menu_id: int | None = None


DRAFTS: dict[int, Draft] = {}


def templates() -> dict[str, str]:
    return {p.stem: yaml.safe_load(p.read_text()).get("description", "") for p in sorted(TEMPLATES.glob("*.yaml"))}


def new_draft(chat: int) -> Draft:
    d = Draft(proj=f"tg{chat}_{time.strftime('%m%d_%H%M%S')}")
    DRAFTS[chat] = d
    return d


def draft(chat: int) -> Draft:
    return DRAFTS.get(chat) or new_draft(chat)


def menu(d: Draft):
    kb = InlineKeyboardBuilder()
    for name in templates():
        kb.button(text=("✅ " if name == d.template else "") + name, callback_data=f"tpl:{name}")
    for n in (1, 3, 5, 10):
        kb.button(text=("✅ " if n == d.variants else "") + f"{n} вар.", callback_data=f"n:{n}")
    kb.button(text="▶️ Монтировать", callback_data="go")
    kb.button(text="🗑 Сбросить", callback_data="reset")
    kb.adjust(*([1] * len(templates())), 4, 2)
    return kb.as_markup()


def menu_text(d: Draft) -> str:
    src = "\n".join(f"  {i + 1}. {Path(x).name if not x.startswith('http') else 'Google Drive'}" for i, x in enumerate(d.inputs)) or "  —"
    return (f"<b>Проект</b> {d.proj}\nИсходники:\n{src}\n\n<b>Шаблон:</b> {d.template}\n<i>{templates().get(d.template, '')}</i>\n"
            f"<b>Вариантов:</b> {d.variants} (+ основной монтаж)\n\nМожно прислать ещё файлы или нажать «Монтировать».")


async def show_menu(m: Message, d: Draft):
    if d.menu_id:
        try:
            await m.bot.delete_message(m.chat.id, d.menu_id)
        except Exception:
            pass
    d.menu_id = (await m.answer(menu_text(d), reply_markup=menu(d))).message_id


def allowed(uid: int) -> bool:
    return not ALLOWED or uid in ALLOWED


# ---------------------------------------------------------------- commands

@router.message(CommandStart())
@router.message(Command("help"))
async def start(m: Message):
    if not allowed(m.from_user.id):
        return await m.answer(f"Нет доступа. Ваш id: {m.from_user.id} — передайте его владельцу бота.")
    await m.answer("Я монтирую ролики по шаблону и делаю варианты с тем же смыслом.\n\n"
                   "1. Пришлите исходники: видео (лучше <b>файлом</b>, без сжатия) или ссылку на Google Drive.\n"
                   "2. Выберите шаблон и число вариантов → «Монтировать».\n"
                   "3. Я пришлю план — подтвердите или напишите правки словами.\n"
                   "4. Получите готовые ролики с текстом поста.\n\n"
                   "/new — новый проект · /templates — шаблоны")


@router.message(Command("new"))
async def cmd_new(m: Message):
    if allowed(m.from_user.id):
        new_draft(m.chat.id)
        await m.answer("Новый проект. Присылайте исходники.")


@router.message(Command("templates"))
async def cmd_templates(m: Message):
    await m.answer("\n\n".join(f"<b>{k}</b>\n{v}" for k, v in templates().items()))


# ---------------------------------------------------------------- collecting sources

@router.message(F.video | F.document | F.video_note)
async def on_file(m: Message):
    if not allowed(m.from_user.id):
        return
    d = draft(m.chat.id)
    if d.stage not in ("collect",):
        d = new_draft(m.chat.id)
    obj = m.video or m.video_note or m.document
    if m.document and not (m.document.mime_type or "").startswith("video/"):
        return await m.answer("Это не видео. Пришлите видеофайл или ссылку на Google Drive.")
    if obj.file_size and obj.file_size > 20 * 1024 * 1024 and not LOCAL_API:
        return await m.answer("Файл больше 20 МБ — облачный Telegram API не отдаёт такие боту. "
                              "Пришлите ссылку на Google Drive (или включите свой Bot API сервер).")
    work, _ = proj_dirs(d.proj)
    inbox = work / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    ext = Path(getattr(obj, "file_name", None) or "video.mp4").suffix or ".mp4"
    dst = inbox / f"src{len(d.inputs)}{ext.lower()}"
    note = await m.answer("⬇️ Скачиваю…")
    f = await m.bot.get_file(obj.file_id)
    if LOCAL_API and Path(f.file_path).is_absolute():  # local server: the file is already on the shared volume
        shutil.copy(f.file_path, dst)
    else:
        await m.bot.download_file(f.file_path, dst)
    d.inputs.append(str(dst))
    await note.delete()
    await show_menu(m, d)


@router.message(F.text.regexp(DRIVE))
async def on_link(m: Message):
    if not allowed(m.from_user.id):
        return
    d = draft(m.chat.id)
    if d.stage == "feedback":
        return await on_feedback(m)
    if d.stage != "collect":
        d = new_draft(m.chat.id)
    d.inputs += DRIVE.findall(m.text)
    await show_menu(m, d)


@router.callback_query(F.data.startswith("tpl:"))
async def cb_tpl(c: CallbackQuery):
    d = draft(c.message.chat.id)
    d.template = c.data[4:]
    await c.message.edit_text(menu_text(d), reply_markup=menu(d))
    await c.answer()


@router.callback_query(F.data.startswith("n:"))
async def cb_n(c: CallbackQuery):
    d = draft(c.message.chat.id)
    d.variants = int(c.data[2:])
    await c.message.edit_text(menu_text(d), reply_markup=menu(d))
    await c.answer()


@router.callback_query(F.data == "reset")
async def cb_reset(c: CallbackQuery):
    new_draft(c.message.chat.id)
    await c.message.edit_text("Сбросил. Присылайте исходники.")
    await c.answer()


# ---------------------------------------------------------------- the pipeline

async def heavy(msg: Message, title: str, fn, *args):
    """run a blocking stage in a thread, one at a time, with a status line in the chat"""
    status = await msg.answer(f"⏳ {title}" + (" — в очереди" if JOB.locked() else ""))
    async with JOB:
        await status.edit_text(f"⏳ {title}…")
        t0 = time.time()
        try:
            res = await asyncio.to_thread(fn, *args)
        except Exception as e:  # report, keep the bot alive
            log.error(traceback.format_exc())
            await status.edit_text(f"❌ {title}: {type(e).__name__}: {str(e)[:300]}")
            raise
        await status.edit_text(f"✅ {title} — {time.time() - t0:.0f} с")
        return res


def review_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🎬 Рендер", callback_data="render")
    kb.button(text="✏️ Правки", callback_data="edit")
    kb.adjust(2)
    return kb.as_markup()


async def send_plan(msg: Message, d: Draft):
    work, _ = proj_dirs(d.proj)
    text = (work / "plans.md").read_text()
    chk = work / "check.json"
    if chk.exists():
        rep = json.loads(chk.read_text())["checks"]
        text += "\n\nПроверка смысла:\n" + "\n".join(
            f"{'✅' if r['ok'] else '⚠️'} {r['plan_id']}" + "".join(f"\n   – {p}" for p in r["problems"]) for r in rep)
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)]
    for i, ch in enumerate(chunks):
        await msg.answer(ch, parse_mode=None, reply_markup=review_kb() if i == len(chunks) - 1 else None)
    d.stage = "review"


def _plan(d: Draft, feedback: str | None):
    from . import brain

    work, _ = proj_dirs(d.proj)
    pj = json.load(open(work / "project.json"))
    pj["template"] = d.template
    json.dump(pj, open(work / "project.json", "w"), ensure_ascii=False, indent=1)
    ps = brain.plan(d.proj, d.template, d.variants, feedback)
    rep = brain.check(d.proj, ps)
    (work / "check.json").write_text(rep.model_dump_json(indent=1))


@router.callback_query(F.data == "go")
async def cb_go(c: CallbackQuery):
    d = draft(c.message.chat.id)
    await c.answer()
    if not d.inputs:
        return await c.message.answer("Сначала пришлите исходники.")
    if d.stage != "collect":
        return
    d.stage = "planning"
    await c.message.edit_reply_markup(reply_markup=None)
    from .ingest import ingest

    try:
        await heavy(c.message, "Разбираю исходники (речь, кадры, лица)", ingest, d.proj, d.inputs)
        await heavy(c.message, f"Монтирую по шаблону {d.template}", _plan, d, None)
    except Exception:
        d.stage = "collect"
        return
    await send_plan(c.message, d)


@router.callback_query(F.data == "edit")
async def cb_edit(c: CallbackQuery):
    d = draft(c.message.chat.id)
    d.stage = "feedback"
    await c.answer()
    await c.message.answer("Напишите, что поменять — обычными словами. Например:\n"
                           "«в v1 начни с фразы про ВБ», «убери кусок про возраст», «v2 короче, до 40 секунд».")


@router.message(F.text & ~F.text.startswith("/"))
async def on_feedback(m: Message):
    if not allowed(m.from_user.id):
        return
    d = DRAFTS.get(m.chat.id)
    if not d or d.stage != "feedback":
        return await m.answer("Пришлите видео или ссылку на Google Drive. /help — как это работает.")
    d.stage = "planning"
    try:
        await heavy(m, "Переделываю план", _plan, d, m.text)
    except Exception:
        d.stage = "review"
        return
    await send_plan(m, d)


@router.callback_query(F.data == "render")
async def cb_render(c: CallbackQuery):
    d = draft(c.message.chat.id)
    await c.answer()
    if d.stage != "review":
        return
    d.stage = "rendering"
    await c.message.edit_reply_markup(reply_markup=None)
    from .render import render

    try:
        res = await heavy(c.message, "Рендерю ролики", render, d.proj)
    except Exception:
        d.stage = "review"
        return
    for r in res:
        path = r["master"] if r["master"].stat().st_size <= SEND_LIMIT else r["preview"]
        cap = f"<b>{r['id']}</b> — {r['angle']}\n\n{r['caption']}"[:1024]
        await c.message.answer_video(FSInputFile(path), caption=cap, supports_streaming=True, width=1080, height=1920)
    d.stage = "done"
    await c.message.answer("Готово. Пришлите новые исходники — начнём следующий проект.")
    new_draft(c.message.chat.id)


# ---------------------------------------------------------------- entry point

def make_bot() -> Bot:
    session = None
    if LOCAL_API:
        session = AiohttpSession(api=TelegramAPIServer.from_base(os.environ["BOT_API_URL"], is_local=True))
    return Bot(os.environ["BOT_TOKEN"], session=session, default=DefaultBotProperties(parse_mode="HTML"))


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not ALLOWED:
        log.warning("ALLOWED_USERS is empty — the bot answers anyone")
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(make_bot())


if __name__ == "__main__":
    asyncio.run(main())
