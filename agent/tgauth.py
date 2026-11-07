"""Sign-in through Telegram: the «Загрузить видео» button opens the web app inside Telegram, which hands the page
signed launch data (initData). The server checks the signature with the bot token and lets in only users from
ALLOWED_USERS — no access code to type. https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
from __future__ import annotations

import hashlib, hmac, json, os, re, time
from urllib.parse import parse_qsl


def allowed_ids() -> set[int]:
    return {int(x) for x in re.findall(r"\d+", os.environ.get("ALLOWED_USERS", ""))}


def verify(init_data: str, bot_token: str, max_age: int = 86400) -> int | None:
    """→ the Telegram user id if the data is genuine and fresh, else None"""
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True))
        got = pairs.pop("hash", "")
        check = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        mine = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not got or not hmac.compare_digest(mine, got):
            return None
        if time.time() - int(pairs.get("auth_date", "0")) > max_age:
            return None
        return int(json.loads(pairs["user"])["id"])
    except Exception:
        return None
