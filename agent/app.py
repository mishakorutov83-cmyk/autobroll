"""Run everything in one process: the web app (FastAPI on PORT, default 8080) and, if BOT_TOKEN is set,
the Telegram bot — one event loop, so both share the job queue (one heavy job at a time) and projects.

  python3 -m agent.app          env: WEB_PASSWORD, ANTHROPIC_API_KEY, [BOT_TOKEN, ALLOWED_USERS, BOT_API_URL, PORT]
"""
import asyncio, logging, os

import uvicorn

# .env saved by Windows Notepad can leave a stray \r, spaces or quotes around values
for _k in ("BOT_TOKEN", "ANTHROPIC_API_KEY", "ALLOWED_USERS", "BOT_API_URL", "AGENT_MODEL", "AGENT_EFFORT", "WEB_PASSWORD", "PORT"):
    if _k in os.environ:
        os.environ[_k] = os.environ[_k].strip().strip('"').strip("'")
        if not os.environ[_k]:
            del os.environ[_k]

from . import projects  # noqa: E402
from .web import app  # noqa: E402

log = logging.getLogger("agent.app")


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    projects.recover_after_restart()
    port = int(os.environ.get("PORT", 8080))
    server = uvicorn.Server(uvicorn.Config(app, host="0.0.0.0", port=port, log_level="warning", proxy_headers=True,
                                           forwarded_allow_ips="*"))
    tasks = [server.serve()]
    if os.environ.get("BOT_TOKEN"):
        from .bot import run_polling

        tasks.append(run_polling())
    else:
        log.info("BOT_TOKEN is not set — Telegram bot is off, web app only")
    if not os.environ.get("WEB_PASSWORD"):
        log.warning("WEB_PASSWORD is not set — the web app will refuse every login")
    log.info(f"web app on http://0.0.0.0:{port}")
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
