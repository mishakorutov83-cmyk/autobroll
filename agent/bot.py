"""Telegram bot — the interface to the video agent.

  python3 -m agent.bot          (env: BOT_TOKEN, ANTHROPIC_API_KEY, ALLOWED_USERS, BOT_API_URL)

Flow in the chat:
  1. send video files (as video or as file) and/or Google Drive links — all of them go into one project
  2. pick a template and the number of variants → «Монтировать»
  3. the bot sends the plan (hook, clips, captions, post text) + the meaning check
  4. «Рендер» — or «Правки» and write what to change in plain words → a new plan
  5. the bot sends every variant as a video with the post caption

Files > 20 MB: the official cloud Bot API refuses to download them, so in production the bot talks
to a self-hosted telegram-bot-api server (BOT_API_URL, docker-compose.yml) — up to 2 GB both ways,
or the user uploads through the web app (agent/web.py) — same projects, same job queue.
Projects live on disk (agent/projects.py), so a restart does not lose a chat's project.
"""
from __future__ import annotations

import asyncio, json, logging, os, re, shutil
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from . import jobs, projects
from .config import ROOT
from .projects import State, templates

# .env saved by Windows Notepad can leave a stray \r or spaces around values
for _k in ("BOT_TOKEN", "ANTHROPIC_API_KEY", "ALLOWED_USERS", "BOT_API_URL", "AGENT_MODEL", "AGENT_EFFORT"):
    if _k in os.environ:
        os.environ[_k] = os.environ[_k].strip().strip('"').strip("'")
        if not os.environ[_k]:
            del os.environ[_k]

log = logging.getLogger("agent.bot")
router = Router()
ALLOWED = {int(x) for x in re.findall(r"\d+", os.environ.get("ALLOWED_USERS", ""))}
LOCAL_API = bool(os.environ.get("BOT_API_URL"))
SEND_LIMIT = (2000 if LOCAL_API else 49) * 1024 * 1024
DRIVE = re.compile(r"https?://drive\.google\.com/\S+")
MAX_VARIANTS = int(os.environ.get("MAX_VARIANTS", 30))


CHATS = ROOT / "work" / "agent" / "tg_chats.json"  # chat id → its current project
MENUS: dict[int, int] = {}  # chat id → message id of the project menu


def _chats() -> dict:
    return json.loads(CHATS.read_text()) if CHATS.exists() else {}


def new_draft(chat: int) -> State:
    st = projects.create(owner=str(chat), prefix=f"tg{chat}", title="Ролик из Telegram")
    c = _chats()
    c[str(chat)] = st.id
    CHATS.parent.mkdir(parents=True, exist_ok=True)
    CHATS.write_text(json.dumps(c))
    return st


def draft(chat: int) -> State:
    pid = _chats().get(str(chat))
    return (projects.load(pid) if pid else None) or new_draft(chat)


def menu(d: State):
    kb = InlineKeyboardBuilder()
    for name in templates():
        kb.button(text=("✅ " if name == d.template else "") + name, callback_data=f"tpl:{name}")
    for n in (1, 3, 5, 10):
        kb.button(text=("✅ " if n == d.variants else "") + f"{n} вар.", callback_data=f"n:{n}")
    custom = d.variants not in (1, 3, 5, 10)
    kb.button(text=(f"✅ {d.variants} вар." if custom else "✏️ Своё число"), callback_data="n:custom")
    kb.button(text="▶️ Монтировать", callback_data="go")
    kb.button(text="🗑 Сбросить", callback_data="reset")
    kb.adjust(*([1] * len(templates())), 5, 2)
    return kb.as_markup()


def menu_text(d: State) -> str:
    src = "\n".join(f"  {i + 1}. {Path(x).name if not x.startswith('http') else 'Google Drive'}" for i, x in enumerate(d.inputs)) or "  —"
    return (f"<b>Проект</b> {d.id}\nИсходники:\n{src}\n\n<b>Шаблон:</b> {d.template}\n<i>{templates().get(d.template, '')}</i>\n"
            f"<b>Вариантов:</b> {d.variants} (+ основной монтаж)\n\nМожно прислать ещё файлы или нажать «Монтировать».")


async def show_menu(m: Message, d: State):
    if m.chat.id in MENUS:
        try:
            await m.bot.delete_message(m.chat.id, MENUS[m.chat.id])
        except Exception:
            pass
    MENUS[m.chat.id] = (await m.answer(menu_text(d), reply_markup=menu(d))).message_id


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
    pid = _chats().get(str(m.chat.id))
    d = projects.load(pid) if pid else None
    if d and d.stage == "error" and jobs.analysed(d):  # e.g. stopped on an empty API balance
        await m.answer("У вас есть разобранный ролик, который не успел смонтироваться:\n" + d.error, parse_mode=None)
        await show_menu(m, d)


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
    inbox = d.work / "inbox"
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
    d.save()
    await note.delete()
    await show_menu(m, d)


@router.message(F.text.regexp(DRIVE))
async def on_link(m: Message):
    if not allowed(m.from_user.id):
        return
    d = draft(m.chat.id)
    if m.chat.id in EDITING:
        return await on_feedback(m)
    if d.stage != "collect":
        d = new_draft(m.chat.id)
    d.inputs += DRIVE.findall(m.text)
    d.save()
    await show_menu(m, d)


@router.callback_query(F.data.startswith("tpl:"))
async def cb_tpl(c: CallbackQuery):
    d = draft(c.message.chat.id)
    d.template = c.data[4:]
    d.save()
    await c.message.edit_text(menu_text(d), reply_markup=menu(d))
    await c.answer()


@router.callback_query(F.data.startswith("n:"))
async def cb_n(c: CallbackQuery):
    d = draft(c.message.chat.id)
    if c.data == "n:custom":
        await c.answer()
        return await c.message.answer(f"Напишите число вариантов — от 1 до {MAX_VARIANTS}.")
    d.variants = int(c.data[2:])
    d.save()
    await c.message.edit_text(menu_text(d), reply_markup=menu(d))
    await c.answer()


@router.callback_query(F.data == "reset")
async def cb_reset(c: CallbackQuery):
    new_draft(c.message.chat.id)
    await c.message.edit_text("Сбросил. Присылайте исходники.")
    await c.answer()


# ---------------------------------------------------------------- the pipeline

async def follow(msg: Message, st: State, job):
    """run a job from jobs.py, mirroring the project's progress into one chat message"""
    status = await msg.answer("⏳ …")
    task = asyncio.create_task(job)
    shown = ""
    while not task.done():
        line = "\n".join(st.status[-3:]) or "⏳ …"
        if line != shown:
            shown = line
            try:
                await status.edit_text(line, parse_mode=None)
            except Exception:
                pass
        await asyncio.sleep(3)
    res = task.result()
    if st.stage == "error":
        await status.edit_text("❌ " + st.error, parse_mode=None)
    else:
        try:
            await status.edit_text("\n".join(l for l in st.status if l.startswith("✅"))[-3500:] or "✅", parse_mode=None)
        except Exception:
            pass
    return res


def review_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🎬 Рендер", callback_data="render")
    kb.button(text="✏️ Правки", callback_data="edit")
    kb.adjust(2)
    return kb.as_markup()


async def send_plan(msg: Message, d: State):
    text = (d.work / "plans.md").read_text()
    chk = d.work / "check.json"
    if chk.exists():
        rep = json.loads(chk.read_text())["checks"]
        text += "\n\nПроверка смысла:\n" + "\n".join(
            f"{'✅' if r['ok'] else '⚠️'} {r['plan_id']}" + "".join(f"\n   – {p}" for p in r["problems"]) for r in rep)
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)]
    for i, ch in enumerate(chunks):
        await msg.answer(ch, parse_mode=None, reply_markup=review_kb() if i == len(chunks) - 1 else None)


@router.callback_query(F.data == "go")
async def cb_go(c: CallbackQuery):
    d = draft(c.message.chat.id)
    await c.answer()
    if not d.inputs:
        return await c.message.answer("Сначала пришлите исходники.")
    if d.stage not in ("collect", "error"):
        return
    await c.message.edit_reply_markup(reply_markup=None)
    ok = await follow(c.message, d, jobs.analyse_and_plan(d))
    if not ok:
        d.stage = "collect"  # buttons back, so «Монтировать» can be pressed again; the analysis is kept
        d.save()
        return await show_menu(c.message, d)
    await send_plan(c.message, d)


EDITING: set[int] = set()  # chats whose next text message is a revision request


@router.callback_query(F.data == "edit")
async def cb_edit(c: CallbackQuery):
    d = draft(c.message.chat.id)
    d.feedback, d.stage = "", "review"
    EDITING.add(c.message.chat.id)
    d.save()
    await c.answer()
    await c.message.answer("Напишите, что поменять — обычными словами. Например:\n"
                           "«в v1 начни с фразы про ВБ», «убери кусок про возраст», «v2 короче, до 40 секунд».")


@router.message(F.text & ~F.text.startswith("/"))
async def on_feedback(m: Message):
    if not allowed(m.from_user.id):
        return
    pid = _chats().get(str(m.chat.id))
    d = projects.load(pid) if pid else None
    if d and d.stage == "collect" and re.fullmatch(r"\s*\d+\s*(вар\w*)?\s*", m.text):
        n = int(re.search(r"\d+", m.text).group())
        if not 1 <= n <= MAX_VARIANTS:
            return await m.answer(f"Можно от 1 до {MAX_VARIANTS} вариантов.")
        d.variants = n
        d.save()
        extra = "\nМного вариантов — это дольше: рендер ~3–5 мин на каждый на обычном ПК." if n > 10 else ""
        await m.answer(f"Вариантов: {n} (+ основной монтаж).{extra}")
        return await show_menu(m, d)
    if not d or m.chat.id not in EDITING or d.stage not in ("review", "done"):
        return await m.answer("Пришлите видео или ссылку на Google Drive. /help — как это работает.")
    EDITING.discard(m.chat.id)
    if await follow(m, d, jobs.replan(d, m.text)):
        await send_plan(m, d)


@router.callback_query(F.data == "render")
async def cb_render(c: CallbackQuery):
    d = draft(c.message.chat.id)
    await c.answer()
    if d.stage not in ("review", "done"):
        return
    await c.message.edit_reply_markup(reply_markup=None)
    res = await follow(c.message, d, jobs.render(d))
    if res is None:
        return await c.message.answer("Нажмите «🎬 Рендер» ещё раз, когда исправите причину.", reply_markup=review_kb())
    for r in res:
        path = r["master"] if r["master"].stat().st_size <= SEND_LIMIT else r["preview"]
        cap = f"<b>{r['id']}</b> — {r['angle']}\n\n{r['caption']}"[:1024]
        await c.message.answer_video(FSInputFile(path), caption=cap, supports_streaming=True, width=1080, height=1920)
    await c.message.answer("Готово. Пришлите новые исходники — начнём следующий проект.")
    new_draft(c.message.chat.id)


# ---------------------------------------------------------------- entry point

def make_bot() -> Bot:
    session = None
    if LOCAL_API:
        session = AiohttpSession(api=TelegramAPIServer.from_base(os.environ["BOT_API_URL"], is_local=True))
    return Bot(os.environ["BOT_TOKEN"], session=session, default=DefaultBotProperties(parse_mode="HTML"))


async def run_polling():
    if not ALLOWED:
        log.warning("ALLOWED_USERS is empty — the bot answers anyone")
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(make_bot(), handle_signals=False)


if __name__ == "__main__":  # bot only; agent.app runs the bot and the web app together
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    projects.recover_after_restart()
    asyncio.run(run_polling())
