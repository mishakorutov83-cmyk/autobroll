"""The public HTTPS address of the web app — what the Telegram «Загрузить видео» button opens.

PUBLIC_URL in .env wins (a server with its own domain). Otherwise the address of the Cloudflare quick tunnel
(profile «tunnel») is read from its metrics endpoint, but only while the tunnel is connected; it changes whenever the
tunnel restarts, so it is re-read."""
from __future__ import annotations

import json, os, time, urllib.request

_cache = {"t": 0.0, "url": ""}
METRICS = os.environ.get("TUNNEL_METRICS", "http://tunnel:20241")


def _get(path: str) -> dict:
    with urllib.request.urlopen(METRICS + path, timeout=2) as r:
        return json.load(r)


def public_url() -> str:
    env = os.environ.get("PUBLIC_URL", "").strip().strip('"').rstrip("/")
    if env:
        return env if env.startswith("http") else f"https://{env}"
    if time.time() - _cache["t"] < 30:
        return _cache["url"]
    _cache["t"], _cache["url"] = time.time(), ""
    try:
        # a quick tunnel is given an address the moment it is requested; the address works only once the tunnel has
        # connected to Cloudflare — /ready answers 200 only then (503 otherwise). A dead address is worse than none.
        if int(_get("/ready").get("readyConnections", 0)) > 0:
            host = _get("/quicktunnel").get("hostname", "")
            _cache["url"] = f"https://{host}" if host else ""
    except Exception:
        pass  # no tunnel container, not connected (VPN? firewall?), not up yet: the button then explains what to do
    return _cache["url"]
