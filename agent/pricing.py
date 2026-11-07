"""What the Claude calls cost — logged per project so the real price of a video is visible.

work/agent/<proj>/usage.json: one entry per API call (step, model, tokens, ≈ dollars).
Prices are list prices per million tokens; the figure shown to the user is an estimate («≈»).
"""
from __future__ import annotations

import json, threading, time

from .config import proj_dirs

# $ per million tokens: input, output, cache read (None = 10 % of input). Cache write (5 min) = 1.25 × input.
PRICES: dict[str, tuple[float, float, float | None]] = {
    "claude-opus-5-5": (4.0, 20.0, 0.20),
    "claude-opus-5": (5.0, 25.0, None),
    "claude-sonnet-5-5": (2.0, 10.0, 0.20),
    "claude-sonnet-5": (2.0, 10.0, 0.20),
    "claude-haiku-5-5": (0.10, 0.50, None),
    "claude-fable-5-1": (10.0, 50.0, 0.25),
}
_lock = threading.Lock()


def cost(model: str, inp: int, out: int, cache_write: int = 0, cache_read: int = 0) -> float:
    key = next((k for k in PRICES if model.startswith(k)), None)
    p_in, p_out, p_read = PRICES[key] if key else PRICES["claude-opus-5-5"]  # unknown model: assume the dearest common one
    p_read = p_read if p_read is not None else p_in * 0.1
    return (inp * p_in + out * p_out + cache_write * p_in * 1.25 + cache_read * p_read) / 1e6


def record(proj: str, step: str, model: str, usage) -> float:
    """append one call to the project's ledger → dollars for this call"""
    g = lambda n: int(getattr(usage, n, 0) or 0)
    inp, out, cw, cr = g("input_tokens"), g("output_tokens"), g("cache_creation_input_tokens"), g("cache_read_input_tokens")
    usd = cost(model, inp, out, cw, cr)
    path = proj_dirs(proj)[0] / "usage.json"
    with _lock:
        rows = json.loads(path.read_text()) if path.exists() else []
        rows.append({"t": round(time.time()), "step": step, "model": model, "in": inp, "out": out,
                     "cache_write": cw, "cache_read": cr, "usd": round(usd, 4)})
        path.write_text(json.dumps(rows, ensure_ascii=False))
    return usd


def summary(proj: str) -> dict:
    path = proj_dirs(proj)[0] / "usage.json"
    rows = json.loads(path.read_text()) if path.exists() else []
    by: dict[str, float] = {}
    for r in rows:
        by[r["step"]] = by.get(r["step"], 0) + r["usd"]
    return {"usd": round(sum(r["usd"] for r in rows), 3), "calls": len(rows), "by_step": {k: round(v, 3) for k, v in by.items()},
            "out_tokens": sum(r["out"] for r in rows)}


def line(proj: str) -> str:
    s = summary(proj)
    if not s["calls"]:
        return ""
    steps = {"main": "основной монтаж", "variants": "варианты", "check": "проверка смысла", "revise": "правки"}
    parts = " · ".join(f"{steps.get(k, k)} ${v:.2f}" for k, v in s["by_step"].items())
    return f"Claude ≈ ${s['usd']:.2f} ({s['calls']} запр.): {parts}"
