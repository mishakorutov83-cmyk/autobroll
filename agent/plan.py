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


class Style(Strict):
    accent: str = Field(description="accent colour for highlighted words and graphics, #RRGGBB")
    caption_top: float = Field(description="vertical position of captions, % of frame height (55-72)")
    zoom_bias: float = Field(description="extra zoom multiplier on top of the shot sizes, 1.0-1.08")


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


class PlanSet(Strict):
    plans: list[EditPlan] = Field(description="the main cut first (id 'main'), then the variants")


class MeaningCheck(Strict):
    plan_id: str
    ok: bool
    problems: list[str] = Field(description="every place where the meaning differs from the source, empty if ok")


class MeaningReport(Strict):
    checks: list[MeaningCheck]
