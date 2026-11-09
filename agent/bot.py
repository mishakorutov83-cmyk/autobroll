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

import asyncio, html, json, logging, os, re, shutil, time
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.telegram import TelegramAPIServer
from aiogram.filters import Command, CommandStart
from aiogram.types import BotCommand, CallbackQuery, FSInputFile, KeyboardButton, Message, ReplyKeyboardMarkup, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder

from . import inbox, jobs, pricing, projects
from .config import ROOT
from .links import public_url
from .projects import State, templates

# .env saved by Windows Notepad can leave a stray \r or spaces around values
for _k in ("BOT_TOKEN", "ANTHROPIC_API_KEY", "ALLOWED_USERS", "BOT_API_URL", "AGENT_MODEL", "AGENT_EFFORT", "PUBLIC_URL"):
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
    kb.button(text="📁 Папка сервера", callback_data="inbox")
    kb.button(text="▶️ Монтировать", callback_data="go")
    kb.button(text="🗑 Сбросить", callback_data="reset")
    kb.adjust(*([1] * len(templates())), 5, 1, 2)
    return kb.as_markup()


def menu_text(d: State) -> str:
    src = "\n".join(f"  {i + 1}. {Path(x).name if not x.startswith('http') else 'Google Drive'}" for i, x in enumerate(d.inputs)) or "  —"
    return (f"<b>Проект</b> {d.id}\nИсходники:\n{src}\n\n<b>Шаблон:</b> {d.template}\n<i>{templates().get(d.template, '')}</i>\n"
            f"<b>Вариантов:</b> {d.variants} (+ основной монтаж)\n"
            + (f"<b>Задание:</b> {html.escape(d.brief[:600])}\n" if d.brief else "")
            + "\nВидео: пришлите сюда, ссылкой Google Drive или положите в папку сервера и нажмите «📁 Папка сервера». "
              "Можно написать задание — как монтировать своими словами — и нажать «Монтировать».")


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
async def start(m: Message):  # the panel of buttons comes with the help text
    if not allowed(m.from_user.id):
        return await m.answer(f"Нет доступа. Ваш id: {m.from_user.id} — передайте его владельцу бота.")
    await cmd_menu(m)
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


@router.message(Command("clearbrief"))
async def cmd_clearbrief(m: Message):
    if allowed(m.from_user.id):
        d = draft(m.chat.id)
        d.brief = ""
        d.save()
        await show_menu(m, d)


@router.message(Command("templates"))
async def cmd_templates(m: Message):
    await m.answer("\n\n".join(f"<b>{k}</b>\n{v}" for k, v in templates().items()))


# ---------------------------------------------------------------- the button panel (always at the bottom of the chat)

BTN_UPLOAD, BTN_INBOX, BTN_NEW, BTN_PROJECTS, BTN_HELP = "⬆️ Загрузить видео на сервер", "📁 Папка сервера", "🎬 Новый ролик", "📋 Мои проекты", "❓ Помощь"
STAGE_RU = {"collect": "собираю видео", "analysing": "разбираю", "planning": "монтирую", "review": "план готов",
            "rendering": "рендер", "done": "готово", "error": "ошибка"}


async def panel() -> ReplyKeyboardMarkup:
    """the upload button opens the web app inside Telegram (needs the app's HTTPS address); signed in automatically"""
    url = await asyncio.to_thread(public_url)
    # Telegram accepts only https addresses for a web-app button — with anything else it would refuse the whole message
    up = KeyboardButton(text=BTN_UPLOAD, web_app=WebAppInfo(url=f"{url}/?go=inbox")) if url.startswith("https://") else KeyboardButton(text=BTN_UPLOAD)
    return ReplyKeyboardMarkup(keyboard=[[up], [KeyboardButton(text=BTN_INBOX), KeyboardButton(text=BTN_NEW)],
                                         [KeyboardButton(text=BTN_PROJECTS), KeyboardButton(text=BTN_HELP)]],
                               resize_keyboard=True, is_persistent=True)


HELP = ("Я монтирую ролики по шаблону и делаю варианты с тем же смыслом.\n\n"
        f"1. Видео на сервер: кнопка «{BTN_UPLOAD}» (с телефона, любой размер) или положите файлы в папку <b>inbox</b> на сервере.\n"
        f"2. «{BTN_NEW}» → «{BTN_INBOX}» → выберите видео. Выберите шаблон и число вариантов; можно написать задание своими словами — "
        "например «до 30 секунд, начни с цены, жёлтые субтитры». → «Монтировать».\n"
        "3. Я пришлю план — подтвердите или напишите правки словами.\n"
        "4. Получите готовые ролики с текстом поста; полное качество лежит на сервере в out/ready.\n\n"
        f"«{BTN_PROJECTS}» — вернуться к любому проекту.")


@router.message(Command("menu"))
@router.message(F.text == BTN_HELP)
async def cmd_menu(m: Message):
    if not allowed(m.from_user.id):
        return await m.answer(f"Нет доступа. Ваш id: {m.from_user.id} — передайте его владельцу бота.")
    kb = await panel()
    await m.answer(HELP, reply_markup=kb)
    if not any(b.web_app for row in kb.keyboard for b in row):
        await m.answer("ℹ️ Кнопка «⬆️ Загрузить видео на сервер» заработает, когда у приложения будет рабочий адрес с HTTPS: "
                       "туннель Cloudflare должен быть подключён (docker compose logs tunnel — ищите «Registered tunnel connection»; "
                       "не подключается — проверьте VPN «для всей системы») или задайте PUBLIC_URL в .env. "
                       "Пока кладите видео в папку inbox на сервере. Когда адрес появится, отправьте /menu — кнопка обновится.")


@router.message(F.text == BTN_UPLOAD)
async def btn_upload(m: Message):  # only reached when the button has no web app address
    if allowed(m.from_user.id):
        await m.answer("Адреса приложения пока нет. Запустите туннель (docker compose --profile tunnel up -d) или задайте PUBLIC_URL "
                       "в .env и отправьте /menu — кнопка станет открывать страницу загрузки. Пока положите видео в папку inbox на сервере.")


@router.message(F.text == BTN_INBOX)
async def btn_inbox(m: Message):
    if allowed(m.from_user.id):
        await show_inbox(m, draft(m.chat.id))


@router.message(F.text == BTN_NEW)
async def btn_new(m: Message):
    if allowed(m.from_user.id):
        await show_menu(m, new_draft(m.chat.id))


@router.message(Command("projects"))
@router.message(F.text == BTN_PROJECTS)
async def btn_projects(m: Message):
    if not allowed(m.from_user.id):
        return
    items = [x for x in projects.list_projects() if not (x.stage == "collect" and not x.inputs)][:6]  # skip empty drafts
    if not items:
        return await m.answer(f"Проектов пока нет. Нажмите «{BTN_NEW}».")
    kb, lines = InlineKeyboardBuilder(), []
    for st in items:
        src = Path(st.inputs[0]).name if st.inputs and not st.inputs[0].startswith("http") else st.title
        when = time.strftime("%d.%m %H:%M", time.localtime(st.created))
        lines.append(f"{when} · {html.escape(src[:30])} — {STAGE_RU.get(st.stage, st.stage)}")
        kb.button(text=f"{when} · {STAGE_RU.get(st.stage, st.stage)}", callback_data=f"op:{st.id}")
    kb.adjust(1)
    await m.answer("<b>Проекты</b> (новые сверху):\n" + "\n".join(lines), reply_markup=kb.as_markup())


def set_current(chat: int, pid: str):
    c = _chats()
    c[str(chat)] = pid
    CHATS.write_text(json.dumps(c))


@router.callback_query(F.data.startswith("op:"))
async def cb_open(c: CallbackQuery):
    st = projects.load(c.data[3:])
    await c.answer()
    if not st:
        return await c.message.answer("Проект не найден.")
    set_current(c.message.chat.id, st.id)
    m = c.message
    if st.stage == "collect":
        return await show_menu(m, st)
    if st.stage == "review":
        return await send_plan(m, st)
    kb, has_button = InlineKeyboardBuilder(), st.stage in ("done", "error")
    if st.stage == "done":
        kb.button(text="📤 Прислать превью", callback_data=f"pv:{st.id}")
        folder = next((l for l in reversed(st.status) if l.startswith("📁")), "")
        text = f"✅ Готово: {len(projects.results(st))} роликов. {folder}\n{pricing.line(st.id)}"
    elif st.stage == "error":
        kb.button(text="↻ Повторить", callback_data=f"rt:{st.id}")
        text = "❌ " + st.error
    else:
        last = " / ".join(st.status[-2:]) or STAGE_RU.get(st.stage, st.stage)
        text = (last if last.startswith("⏳") else "⏳ " + last) + "\nПроект в работе — откройте его позже."
    await m.answer(text.strip(), parse_mode=None, reply_markup=kb.as_markup() if has_button else None)


@router.callback_query(F.data.startswith("pv:"))
async def cb_previews(c: CallbackQuery):
    st = projects.load(c.data[3:])
    await c.answer()
    if st:
        await send_results(c.message, st, projects.results(st))


@router.callback_query(F.data.startswith("rt:"))
async def cb_retry(c: CallbackQuery):
    st = projects.load(c.data[3:])
    await c.answer()
    if not st or st.stage != "error":
        return await c.message.answer("Нечего повторять.")
    await c.message.edit_reply_markup(reply_markup=None)
    res = await follow(c.message, st, jobs.retry(st))
    if st.stage == "review":
        await send_plan(c.message, st)
    elif st.stage == "done" and res:
        await send_results(c.message, st, res)


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
        return await m.answer("Файл больше 20 МБ — облачный Telegram API не отдаёт такие боту. Положите его в папку inbox "
                              "на сервере и нажмите «📁 Папка сервера» в меню (или пришлите ссылку на Google Drive).")
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
    if m.caption and m.caption.strip():
        d.brief = (d.brief + "\n" + m.caption.strip()).strip()[:4000]
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


INBOX_LIST: dict[int, list[str]] = {}  # chat id → files shown in its last «Папка сервера» list


@router.callback_query(F.data == "inbox")
async def cb_inbox(c: CallbackQuery):
    await c.answer()
    await show_inbox(c.message, draft(c.message.chat.id))


async def show_inbox(m: Message, d: State):
    if d.stage != "collect":
        d = new_draft(m.chat.id)  # the previous project is already running: pick videos for a new one
    items = inbox.list_videos()
    if not items:
        return await m.answer(f"В папке сервера пока нет видео. Загрузите их кнопкой «{BTN_UPLOAD}» или положите файлы в папку "
                              f"<b>inbox</b> ({inbox.INBOX}) и нажмите «{BTN_INBOX}» ещё раз.")
    INBOX_LIST[m.chat.id] = [str(i["path"]) for i in items]
    used = set(d.inputs)
    kb = InlineKeyboardBuilder()
    lines = []
    for n, i in enumerate(items):
        mark = "✅" if str(i["path"]) in used else ("⏳" if i["fresh"] else "➕")
        lines.append(f"{mark} {html.escape(i['name'])} — {inbox.human_size(i['size'])}")
        kb.button(text=f"{mark} {i['name'][:34]}", callback_data=f"ib:{n}")
    kb.button(text="➕ Добавить все", callback_data="ib:all")
    kb.button(text="↩️ К меню", callback_data="ib:menu")
    kb.adjust(*([1] * len(items)), 2)
    await m.answer("<b>Папка сервера</b> (новые сверху). ⏳ — файл ещё копируется.\n\n" + "\n".join(lines), reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("ib:"))
async def cb_inbox_pick(c: CallbackQuery):
    d = draft(c.message.chat.id)
    what = c.data[3:]
    files = INBOX_LIST.get(c.message.chat.id, [])
    if what == "menu":
        await c.answer()
        return await show_menu(c.message, d)
    if d.stage != "collect":
        return await c.answer("Проект уже запущен", show_alert=True)
    picked = files if what == "all" else [files[int(what)]] if what.isdigit() and int(what) < len(files) else []
    fresh = {str(i["path"]) for i in inbox.list_videos() if i["fresh"]}
    added = [f for f in picked if f not in d.inputs and f not in fresh and Path(f).exists()]
    d.inputs += added
    d.save()
    if picked and not added and any(f in fresh for f in picked):
        return await c.answer("Файл ещё копируется — подождите 15 секунд и нажмите снова", show_alert=True)
    await c.answer(f"Добавлено: {len(added)}" if added else "Уже добавлено")
    await show_menu(c.message, d)


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
    cost = pricing.line(d.id)
    chunks = [text[i:i + 3900] for i in range(0, len(text), 3900)]
    if cost:
        chunks.append(cost)
    for i, ch in enumerate(chunks):
        await msg.answer(ch, parse_mode=None, reply_markup=review_kb() if i == len(chunks) - 1 else None)


@router.callback_query(F.data == "go")
async def cb_go(c: CallbackQuery):
    d = draft(c.message.chat.id)
    await c.answer()
    if not d.inputs:
        return await c.message.answer("Сначала пришлите исходники.")
    if d.template == "free" and not d.brief:
        return await c.message.answer("Для шаблона free напишите задание — как монтировать, своими словами.")
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
    if d and d.stage == "collect" and m.chat.id not in EDITING:  # «монтаж по заданию»
        d.brief = (d.brief + "\n" + m.text.strip()).strip()[:4000]
        d.save()
        await m.answer("Записал задание. Можно дописать ещё — добавлю к нему. /clearbrief — очистить.")
        return await show_menu(m, d)
    if not d or m.chat.id not in EDITING or d.stage not in ("review", "done"):
        return await m.answer("Пришлите видео или ссылку на Google Drive. /help — как это работает.")
    EDITING.discard(m.chat.id)
    if await follow(m, d, jobs.replan(d, m.text)):
        await send_plan(m, d)


async def send_results(m: Message, st: State, res: list[dict]):
    """the videos into the chat (the full-quality masters stay on the server in out/ready)"""
    for r in res[:12]:
        path = r["master"] if r["master"].stat().st_size <= SEND_LIMIT else r["preview"]
        cap = f"<b>{r['id']}</b> — {r['angle']}\n\n{r['caption']}"[:1024]
        await m.answer_video(FSInputFile(path), caption=cap, supports_streaming=True, width=1080, height=1920)
    if len(res) > 12:
        await m.answer(f"Показаны первые 12 из {len(res)}. Остальные — на сервере, в папке out/ready.")


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
    await send_results(c.message, d, res)
    where = next((l for l in reversed(d.status) if l.startswith("📁")), "")
    await c.message.answer((where + "\n" if where else "") + "Готово. Новые видео — в папку inbox или сюда, начнём следующий проект.")
    new_draft(c.message.chat.id)


# ---------------------------------------------------------------- entry point

def make_bot() -> Bot:
    session = None
    if LOCAL_API:
        session = AiohttpSession(api=TelegramAPIServer.from_base(os.environ["BOT_API_URL"], is_local=True))
    return Bot(os.environ["BOT_TOKEN"], session=session, default=DefaultBotProperties(parse_mode="HTML"))


# one dispatcher for the whole process: a router can be attached only once, so a restart after a network failure
# (agent.app retries) must reuse it instead of building a new one
DISPATCHER = Dispatcher()
DISPATCHER.include_router(router)


async def run_polling():
    if not ALLOWED:
        log.warning("ALLOWED_USERS is empty — the bot answers anyone")
    bot = make_bot()
    try:  # the «Menu» list next to the text field
        await bot.set_my_commands([BotCommand(command="menu", description="Панель кнопок и помощь"),
                                   BotCommand(command="new", description="Новый ролик"),
                                   BotCommand(command="projects", description="Мои проекты"),
                                   BotCommand(command="templates", description="Шаблоны")])
    except Exception as e:
        log.warning("set_my_commands failed: %s", e)
    await DISPATCHER.start_polling(bot, handle_signals=False)


if __name__ == "__main__":  # bot only; agent.app runs the bot and the web app together
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    projects.recover_after_restart()
    asyncio.run(run_polling())
