"""Edit plan — the contract between the brain (Claude) and the renderer.

The brain never touches media. It returns an EditPlan (or several, one per
variant); build.py turns a plan into a Remotion project, render.py renders it.
Every field is required on purpose: strict structured outputs stay simple and the
model has to decide every value explicitly.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PlanClip(Strict):
    id: str = Field(description="unique id inside the plan, e.g. c01")
    source: int = Field(description="index of the source file (0-based)")
    start: float = Field(description="in-point, seconds in the source; start of the first word")
    end: float = Field(description="out-point, seconds in the source; end of the last word")
    shot: Literal["N", "M", "C", "push"] = Field(description="digital shot size: normal / medium / close-up / slow push-in")
    punch_at: float | None = Field(description="source time of a hard change to the next shot size inside a long clip, or null")
    caption: str = Field(description="exact spoken words of this clip, proofread (names, brands, punctuation); empty string = no captions")
    accents: list[str] = Field(description="0-2 words from caption (copied exactly, with punctuation) to highlight")
    muted: bool = Field(description="true = drop the clip's own sound (pure picture)")


class Overlay(Strict):
    kind: Literal["hook", "label"] = Field(description="hook = big headline at the top; label = short on-screen note (e.g. product name)")
    clip_id: str = Field(description="clip the overlay is anchored to")
    offset: float = Field(description="seconds from the start of that clip on the timeline")
    duration: float
    text: str


class Insert(Strict):
    clip_id: str = Field(description="clip whose sound keeps playing under the inserted picture")
    at: float = Field(description="source time inside that clip where the picture starts")
    duration: float = Field(description="seconds of source time (0.8-4)")
    source: int = Field(description="source file the picture is taken from")
    from_time: float = Field(description="source time of the picture to show (must not contain black / empty frames)")
    mode: Literal["full", "pip"] = Field(description="full = replace the picture; pip = small window on the right, the speaker stays visible")


class Style(Strict):
    accent: str = Field(description="accent colour for highlighted words and graphics, #RRGGBB")
    caption_top: float = Field(description="vertical position of captions, % of frame height (55-72)")
    zoom_bias: float = Field(description="extra zoom multiplier on top of the shot sizes, 1.0-1.08")
    caption_style: Literal["template", "plain", "clean", "pop"] = Field(
        description="template = as the template says; plain = small white text, no highlight colour; "
                    "clean = bold Inter, words brighten as spoken, accent colour on key words; "
                    "pop = big bold words, the spoken word pops — use only if the human's brief asks for it")


class EditPlan(Strict):
    id: str = Field(description="main | v1 | v2 ...")
    angle: str = Field(description="one line: what makes this cut different (hook / order / length)")
    speed: float = Field(description="playback speed of speech, pitch preserved (1.0-1.2)")
    clips: list[PlanClip]
    overlays: list[Overlay]
    inserts: list[Insert] = Field(description="cut-aways: show another moment's picture over a clip's sound, e.g. the exact product being named")
    style: Style
    caption_text: str = Field(description="post caption for the social network, 1-3 sentences")
    hashtags: list[str]
    notes: str = Field(description="for the human reviewer: the story logic and what was cut out and why")


class VariantItem(Strict):
    ref: str = Field(description="id of a clip of the MAIN plan to reuse exactly as it is (its captions and accents come with it); "
                                 "empty string when this item is a new clip. Prefer ref: it keeps the answer short.")
    shot: Literal["", "N", "M", "C", "push"] = Field(description="empty = keep the shot size of the reused clip; otherwise a new size for a visual difference")
    clip: PlanClip | None = Field(description="only when ref is empty: a different cut of the source (other start/end, other caption); "
                                              "its id must start with 'n' (n1, n2 …)")


class VariantPlan(Strict):
    id: str = Field(description="v1, v2 …")
    angle: str = Field(description="one line: what makes this variant different (hook / order / length)")
    speed: float = Field(description="playback speed of speech, pitch preserved (1.0-1.2)")
    items: list[VariantItem] = Field(description="the cut, in order")
    overlays: list[Overlay] = Field(description="clip_id is a main clip id (a ref) or the id of a new clip")
    inserts: list[Insert]
    style: Style
    caption_text: str = Field(description="post caption for the social network, 1-3 sentences")
    hashtags: list[str]
    notes: str = Field(description="for the human reviewer: what differs from the main cut and why the meaning is unchanged")


class VariantSet(Strict):
    variants: list[VariantPlan]


class PlanSet(Strict):
    plans: list[EditPlan] = Field(description="the main cut first (id 'main'), then the variants")


class MeaningCheck(Strict):
    plan_id: str
    ok: bool
    problems: list[str] = Field(description="every place where the meaning differs from the source, empty if ok")


class MeaningReport(Strict):
    checks: list[MeaningCheck]
