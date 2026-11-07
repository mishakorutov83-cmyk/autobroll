"""Stage 2 — the brain: Claude reads the footage facts + a template and writes edit plans.

  plan()   → PlanSet: the main cut + N variants (one request, the model sees transcript + contact sheets)
  check()  → MeaningReport: every plan's captions/overlays compared with what was actually said

The brain only writes plans; build.py and render.py do the media work.
"""
from __future__ import annotations

import base64, json, os
from pathlib import Path

import anthropic
import yaml

from . import pricing
from .config import TEMPLATES, llm, proj_dirs
from .ingest import describe
from .plan import EditPlan, MeaningReport, PlanSet, VariantPlan, VariantSet

SYSTEM = """Ты — монтажёр коротких вертикальных роликов (Reels / Shorts / TikTok, 9:16).
Тебе дают факты об исходниках (транскрипт с таймингом каждого слова, где в кадре лицо, контактные листы кадров
с подписью «s<номер> <секунда>»), ШАБЛОН монтажа и иногда ЗАДАНИЕ человека своими словами. Ты пишешь монтажные планы.

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
6. Длительность итога (сумма клипов / speed) — в пределах length шаблона, если задание не говорит другое.
7. Варианты отличаются для зрителя по-настоящему: другой хук (другая реальная фраза или другой заголовок), другой
   порядок блоков, другая длина, другой стиль (accent, caption_top, zoom_bias). Смысл и факты у всех одинаковые.
   Не делай варианты, отличающиеся только цветом.
8. ЗАДАНИЕ человека важнее шаблона: длина, порядок, с чего начать, что убрать, стиль субтитров (style.caption_style,
   accent, caption_top), заголовки и подписи — делай, как он просит. Но правила 1–5 (смысл, резка по словам, точный
   текст, никаких выдуманных фактов) задание не отменяет: если просьба требует исказить смысл или придумать факт,
   сделай ближайшее честное решение и объясни это в notes. Задание относится ко всем вариантам, если в нём не сказано иное.

notes пиши по-русски, коротко: логика истории, что вырезано и почему — это читает человек перед рендером."""


def load_template(name: str) -> str:
    path = Path(name) if Path(name).exists() else TEMPLATES / f"{name}.yaml"
    text = path.read_text()
    yaml.safe_load(text)  # fail early on a broken template
    return text


def _image(path: Path) -> dict:
    return {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg",
                                        "data": base64.b64encode(path.read_bytes()).decode()}}


FALLBACK_MODELS = ("claude-fable-5-1", "claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5")


def _call(messages: list, schema, step: str, proj: str, max_tokens: int = 64000):
    """one Claude request for a pipeline step (main | variants | check | revise): its model and effort come from
    config.llm(); the cost is written to the project's usage ledger. If a cheaper model rejects the request
    (unknown model, unsupported parameter), the step is retried once on the main model instead of failing the video."""
    model, effort = llm(step)
    try:
        return _request(messages, schema, step, proj, max_tokens, model, effort)
    except anthropic.APIStatusError as e:
        main_model, main_effort = llm("main")
        if e.status_code in (400, 404) and step in ("variants", "check") and model != main_model \
                and "credit balance" not in str(e).lower():
            print(f"  {step}: {model} refused ({str(e)[:160]}) — retrying on {main_model}", flush=True)
            return _request(messages, schema, step, proj, max_tokens, main_model, main_effort)
        raise


def _request(messages: list, schema, step: str, proj: str, max_tokens: int, model: str, effort: str):
    extra = {}
    if model.startswith(FALLBACK_MODELS):  # if a safety classifier declines, the API re-runs the request on a fallback model
        extra = {"betas": ["server-side-fallback-2026-07-01"], "fallbacks": "default"}
    client = anthropic.Anthropic()
    with client.beta.messages.stream(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM,
        messages=messages,
        output_config={"effort": effort},
        output_format=schema,
        **extra,
    ) as stream:
        msg = stream.get_final_message()
    usd = pricing.record(proj, step, msg.model or model, msg.usage)
    u = msg.usage
    print(f"  {step} {msg.model} ({effort}): in {u.input_tokens} + cache {getattr(u, 'cache_read_input_tokens', 0) or 0} / out {u.output_tokens} tokens ≈ ${usd:.3f}", flush=True)
    if msg.stop_reason == "refusal":
        raise RuntimeError(f"model refused: {msg.stop_details}")
    if msg.stop_reason == "max_tokens":
        raise RuntimeError("plan was cut off by max_tokens")
    parsed = getattr(msg, "parsed_output", None)
    if parsed is None:
        text = next(b.text for b in msg.content if b.type == "text")
        parsed = schema.model_validate_json(text)
    return parsed


def plan(proj: str, template: str, variants: int, feedback: str | None = None, brief: str = "") -> PlanSet:
    if os.environ.get("AGENT_FAKE_BRAIN"):
        ps = _fake_plan(proj, variants)
        save(proj, ps)
        return ps
    work, _ = proj_dirs(proj)
    facts, images = describe(proj)
    shared = [{"type": "text", "text": f"# ШАБЛОН\n```yaml\n{load_template(template)}\n```"},
              *([{"type": "text", "text": f"# ЗАДАНИЕ ЧЕЛОВЕКА (важнее шаблона, см. правило 8)\n{brief.strip()}"}] if brief.strip() else []),
              {"type": "text", "text": f"# ИСХОДНИКИ\n{facts}"},
              {"type": "text", "text": "Контактные листы кадров (подпись на каждом кадре: источник и секунда):"},
              *[_image(p) for p in images]]
    # everything above is identical in every request of this video (main cut, each batch of variants, a revision):
    # the cache breakpoint makes the repeats read it at a fraction of the price
    shared[-1] = {**shared[-1], "cache_control": {"type": "ephemeral"}}
    prev = work / "plans.json"

    if feedback and prev.exists():  # a revision rewrites the whole set in the full format, following the human's notes
        messages = [{"role": "user", "content": shared + [{"type": "text", "text": "Сделай монтаж по шаблону — он уже сделан, см. ниже."}]},
                    {"role": "assistant", "content": PlanSet.model_validate_json(prev.read_text()).model_dump_json()},
                    {"role": "user", "content": f"Правки от человека:\n{feedback}\n\nПерепиши планы с учётом правок. "
                                                "То, что правки не затрагивают, оставь как было."}]
        ps = _call(messages, PlanSet, "revise", proj)
        save(proj, ps)
        return ps

    ask = ("Сделай ТОЛЬКО основной монтаж (id main). Варианты будут отдельным запросом. "
           "Сначала найди в транскрипте лучшую историю под шаблон" + (" и задание" if brief.strip() else "") + ", потом режь.")
    main = _call([{"role": "user", "content": shared + [{"type": "text", "text": ask}]}], EditPlan, "main", proj)
    main.id = "main"
    ps = PlanSet(plans=[main])
    if variants:
        ps = _variants(shared, ps, variants, proj)
    save(proj, ps)
    return ps


BATCH = 8  # variants per request — keeps one answer well under the output limit


def _variants(shared: list, ps: PlanSet, variants: int, proj: str) -> PlanSet:
    """variants are recipes over the main cut (reuse its clips by id, reorder, drop, add a few new ones), asked in
    batches; each batch is told which angles exist. Only the new material is written out, so the answer stays short."""
    main, plans = ps.plans[0], list(ps.plans)
    main_json = main.model_dump_json()
    while len(plans) - 1 < variants:
        have = len(plans) - 1
        k = min(BATCH, variants - have)
        known = "\n".join(f"- {p.id}: {p.angle}; начинается с: «{p.clips[0].caption[:60] if p.clips else ''}»" for p in plans)
        ask = (f"Основной монтаж (main) уже сделан:\n{main_json}\n\nУже есть:\n{known}\n\n"
               f"Сделай ещё {k} вариантов с id v{have + 1}..v{have + k} как РЕЦЕПТЫ: items — упорядоченный список; "
               "{ref: id клипа из main} берёт клип как есть (так ответ короче — используй это везде, где можно), "
               "новый клип (clip, id с 'n') — только если нужен другой отрезок исходника. "
               "Каждый вариант должен отличаться для зрителя от main и от всех уже сделанных: другой хук (первый клип и/или заголовок), "
               "другой порядок блоков, другая длина (убрать или добавить клипы), другая подача (shot, style). "
               "Смысл не меняй: переставляй только независимые по смыслу блоки — не разрывай «вопрос → ответ», «причина → следствие», "
               "«до → после»; не обрывай мысль.")
        got = _call([{"role": "user", "content": shared + [{"type": "text", "text": ask}]}], VariantSet, "variants", proj).variants
        made = [x for x in (_expand(main, v) for v in got) if x][:k]
        if not made:
            break
        for i, x in enumerate(made):  # ids must stay unique whatever the model returned
            x.id = f"v{have + 1 + i}"
        plans += made
    return PlanSet(plans=plans)


def _expand(main: EditPlan, v: VariantPlan) -> EditPlan | None:
    """recipe → a full plan: refs are copied from the main cut, new clips taken as written; broken refs are dropped"""
    by_id = {c.id: c for c in main.clips}
    clips, ids = [], set()
    for it in v.items:
        if it.ref:
            c = by_id.get(it.ref)
            if c is None or c.id in ids:  # unknown id or the same clip twice
                continue
            c = c.model_copy(deep=True)
        elif it.clip is not None:
            c = it.clip.model_copy(deep=True)
            while c.id in ids or c.id in by_id:
                c.id += "x"
        else:
            continue
        if it.shot:
            c.shot = it.shot
        ids.add(c.id)
        clips.append(c)
    if not clips:
        return None
    keep = lambda xs, key: [x for x in xs if getattr(x, key) in ids]  # overlays / inserts of dropped clips go with them
    return EditPlan(id=v.id, angle=v.angle, speed=v.speed, clips=clips, overlays=keep(v.overlays, "clip_id"),
                    inserts=keep(v.inserts, "clip_id"), style=v.style, caption_text=v.caption_text, hashtags=v.hashtags, notes=v.notes)


def check(proj: str, ps: PlanSet) -> MeaningReport:
    if os.environ.get("AGENT_FAKE_BRAIN"):
        return MeaningReport(checks=[{"plan_id": p.id, "ok": True, "problems": []} for p in ps.plans])
    facts, _ = describe(proj)
    plans = [{"id": p.id, "clips": [{"id": c.id, "source": c.source, "start": c.start, "end": c.end, "caption": c.caption}
                                    for c in p.clips], "overlays": [o.model_dump() for o in p.overlays]} for p in ps.plans]
    msg = [{"role": "user", "content": f"# ИСХОДНИКИ\n{facts}\n\n# ПЛАНЫ\n{json.dumps(plans, ensure_ascii=False)}\n\n"
                                       "Проверь каждый план: совпадает ли смысл склеенных клипов, субтитров и надписей с тем, "
                                       "что человек сказал в исходнике? Ищи искажения: вырванные из контекста фразы, "
                                       "потерянные отрицания и условия, неверные цифры/имена, выдуманные факты в надписях."}]
    return _call(msg, MeaningReport, "check", proj, max_tokens=32000)


def save(proj: str, ps: PlanSet):
    work, _ = proj_dirs(proj)
    (work / "plans.json").write_text(ps.model_dump_json(indent=1))
    (work / "plans.md").write_text(review(ps))


def load(proj: str) -> PlanSet:
    work, _ = proj_dirs(proj)
    d = json.loads((work / "plans.json").read_text())
    for p in d["plans"]:  # plans written before a field existed
        p["style"].setdefault("caption_style", "template")
        for x in p.get("inserts", []):
            x.setdefault("mode", "full")
    return PlanSet.model_validate(d)


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


def _fake_plan(proj: str, variants: int) -> PlanSet:
    """AGENT_FAKE_BRAIN=1 — no Claude call: transcript phrases in order (rotated per variant).
    Only for testing the bot / web app / render end to end without an API key."""
    work, _ = proj_dirs(proj)
    segs = [g for g in json.load(open(work / "s0" / "words.json")) if g["end"] - g["start"] > 0.8][:12]
    clips = [{"id": f"c{i:02d}", "source": 0, "start": g["start"], "end": g["end"], "shot": "NMC"[i % 3], "punch_at": None,
              "caption": g["text"], "accents": [], "muted": False} for i, g in enumerate(segs)]
    plans = []
    for k in range(variants + 1):
        order = clips[k % len(clips):] + clips[:k % len(clips)]
        plans.append({"id": "main" if k == 0 else f"v{k}", "angle": "тест без Claude" if k == 0 else f"тест: старт с фразы {k + 1}",
                      "speed": 1.05, "clips": order, "overlays": [], "inserts": [],
                      "style": {"accent": "#FFFFFF", "caption_top": 66 + k % 3 * 3, "zoom_bias": 1.0, "caption_style": "template"},
                      "caption_text": "Тестовый монтаж без Claude", "hashtags": ["#тест"], "notes": "AGENT_FAKE_BRAIN"})
    return PlanSet.model_validate({"plans": plans})
