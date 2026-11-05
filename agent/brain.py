"""Stage 2 — the brain: Claude reads the footage facts + a template and writes edit plans.

  plan()   → PlanSet: the main cut + N variants (one request, the model sees transcript + contact sheets)
  check()  → MeaningReport: every plan's captions/overlays compared with what was actually said

The brain only writes plans; build.py and render.py do the media work.
"""
from __future__ import annotations

import base64, json
from pathlib import Path

import anthropic
import yaml

from .config import EFFORT, MODEL, TEMPLATES, proj_dirs
from .ingest import describe
from .plan import EditPlan, MeaningReport, PlanSet

SYSTEM = """Ты — монтажёр коротких вертикальных роликов (Reels / Shorts / TikTok, 9:16).
Тебе дают факты об исходниках (транскрипт с таймингом каждого слова, где в кадре лицо, контактные листы кадров
с подписью «s<номер> <секунда>») и ШАБЛОН монтажа. Ты пишешь монтажные планы.

Правила, которые важнее шаблона:
1. Смысл сказанного не меняется никогда. Нельзя склеивать фразы так, чтобы получилось утверждение, которого человек
   не делал; нельзя вырезать отрицания, оговорки-условия, цифры и имена из сохранённых фраз.
2. Режь только по границам слов: start клипа = время начала первого слова (word@start), end = конец последнего слова
   (начало следующего слова минус 0.05 с, если не ясно). Не начинай и не заканчивай клип посреди фразы-мысли.
3. caption — ровно те слова, что звучат в клипе, но вычитанные: имена, бренды (Dior Maison и т.п.), топонимы,
   пунктуация, «ё». Whisper ошибается — исправляй по смыслу и по кадрам.
4. Кадры без лица с речью (товар, перебивки внутри исходника) — это тот же голос. Если голос называет предмет,
   а в кадре другое — поставь insert: картинку нужного предмета из другого момента (по контактным листам) поверх
   звука клипа. Пустые проводки, чёрные кадры, руки, расфокус — вырезай или перекрывай insert'ом.
5. Заголовки (hook) и подписи (label) — только факты из речи или того, что видно в кадре. Без выдуманных цифр и обещаний.
6. Длительность итога (сумма клипов / speed) — в пределах length шаблона.
7. Варианты отличаются для зрителя по-настоящему: другой хук (другая реальная фраза или другой заголовок), другой
   порядок блоков, другая длина, другой стиль (accent, caption_top, zoom_bias). Смысл и факты у всех одинаковые.
   Не делай варианты, отличающиеся только цветом.

notes пиши по-русски, коротко: логика истории, что вырезано и почему — это читает человек перед рендером."""


def load_template(name: str) -> str:
    path = Path(name) if Path(name).exists() else TEMPLATES / f"{name}.yaml"
    text = path.read_text()
    yaml.safe_load(text)  # fail early on a broken template
    return text


def _image(path: Path) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                        "data": base64.b64encode(path.read_bytes()).decode()}}


def _call(messages: list, schema, max_tokens: int = 64000):
    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=MODEL,
        max_tokens=max_tokens,
        system=SYSTEM,
        messages=messages,
        output_config={"effort": EFFORT},
        output_format=schema,
        # if a safety classifier declines, the API re-runs the request on a fallback model
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    ) as stream:
        msg = stream.get_final_message()
    if msg.stop_reason == "refusal":
        raise RuntimeError(f"model refused: {msg.stop_details}")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("plan was cut off by max_tokens")
    parsed = getattr(msg, "parsed_output", None)
    if parsed is None:
        text = next(b.text for b in msg.content if b.type == "text")
        parsed = schema.model_validate_json(text)
    u = msg.usage
    print(f"  {msg.model}: in {u.input_tokens} / out {u.output_tokens} tokens", flush=True)
    return parsed


def plan(proj: str, template: str, variants: int, feedback: str | None = None) -> PlanSet:
    work, _ = proj_dirs(proj)
    facts, images = describe(proj)
    content = [{"type": "text", "text": f"# ШАБЛОН\n```yaml\n{load_template(template)}\n```"},
               {"type": "text", "text": f"# ИСХОДНИКИ\n{facts}"},
               {"type": "text", "text": "Контактные листы кадров (подпись на каждом кадре: источник и секунда):"},
               *[_image(p) for p in images],
               {"type": "text", "text": f"Сделай основной монтаж (id main) и {variants} вариантов (v1..v{variants}). "
                                        "Сначала найди в транскрипте лучшую историю под шаблон, потом режь."}]
    messages = [{"role": "user", "content": content}]
    prev = work / "plans.json"
    if feedback and prev.exists():
        messages += [{"role": "assistant", "content": prev.read_text()},
                     {"role": "user", "content": f"Правки от человека:\n{feedback}\n\nПерепиши планы с учётом правок. "
                                                 "То, что правки не затрагивают, оставь как было."}]
    ps = _call(messages, PlanSet)
    save(proj, ps)
    return ps


def check(proj: str, ps: PlanSet) -> MeaningReport:
    facts, _ = describe(proj)
    plans = [{"id": p.id, "clips": [{"id": c.id, "source": c.source, "start": c.start, "end": c.end, "caption": c.caption}
                                    for c in p.clips], "overlays": [o.model_dump() for o in p.overlays]} for p in ps.plans]
    msg = [{"role": "user", "content": f"# ИСХОДНИКИ\n{facts}\n\n# ПЛАНЫ\n{json.dumps(plans, ensure_ascii=False)}\n\n"
                                       "Проверь каждый план: совпадает ли смысл склеенных клипов, субтитров и надписей с тем, "
                                       "что человек сказал в исходнике? Ищи искажения: вырванные из контекста фразы, "
                                       "потерянные отрицания и условия, неверные цифры/имена, выдуманные факты в надписях."}]
    return _call(msg, MeaningReport, max_tokens=32000)


def save(proj: str, ps: PlanSet):
    work, _ = proj_dirs(proj)
    (work / "plans.json").write_text(ps.model_dump_json(indent=1))
    (work / "plans.md").write_text(review(ps))


def load(proj: str) -> PlanSet:
    work, _ = proj_dirs(proj)
    return PlanSet.model_validate_json((work / "plans.json").read_text())


def review(ps: PlanSet) -> str:
    """Human-readable plan for approval (this is what the bot will send before rendering)."""
    out = []
    for p in ps.plans:
        dur = sum(c.end - c.start for c in p.clips) / p.speed
        out.append(f"## {p.id} — {p.angle}  ({dur:.0f} с, ×{p.speed})")
        hooks = [o.text for o in p.overlays if o.kind == "hook"]
        if hooks:
            out.append(f"Заголовок: «{hooks[0]}»")
        for c in p.clips:
            txt = c.caption or ("(без звука)" if c.muted else "(без субтитров)")
            out.append(f"- s{c.source} {c.start:6.2f}–{c.end:6.2f} [{c.shot}] {txt}")
        labels = [f"{o.text}" for o in p.overlays if o.kind == "label"]
        if labels:
            out.append("Подписи: " + " · ".join(labels))
        out.append(f"Пост: {p.caption_text} {' '.join(p.hashtags)}")
        out.append(f"Логика: {p.notes}\n")
    return "\n".join(out)


def as_plan(obj) -> EditPlan:
    return obj if isinstance(obj, EditPlan) else EditPlan.model_validate(obj)
