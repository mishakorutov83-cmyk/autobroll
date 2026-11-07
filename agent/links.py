"""The public HTTPS address of the web app — what the Telegram «Загрузить видео» button opens.

PUBLIC_URL in .env wins (a server with its own domain). Otherwise the address of the Cloudflare quick tunnel
(profile «tunnel») is read from its metrics endpoint; it changes whenever the tunnel restarts, so it is re-read."""
from __future__ import annotations

import json, os, time, urllib.request

_cache = {"t": 0.0, "url": ""}


def public_url() -> str:
    env = os.environ.get("PUBLIC_URL", "").strip().strip('"').rstrip("/")
    if env:
        return env if env.startswith("http") else f"https://{env}"
    if time.time() - _cache["t"] < 30:
        return _cache["url"]
    _cache["t"], _cache["url"] = time.time(), ""
    try:
        with urllib.request.urlopen("http://tunnel:20241/quicktunnel", timeout=2) as r:
            host = json.load(r).get("hostname", "")
            _cache["url"] = f"https://{host}" if host else ""
    except Exception:
        pass  # no tunnel container (or not up yet): the button then explains what to do
    return _cache["url"]
