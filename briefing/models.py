from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Citation(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    source: str = Field(min_length=1)
    url: str | None = None
    note: str = Field(min_length=1)


class BriefingSection(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    kind: Literal["intro", "key_point", "summary"]
    heading: str = Field(min_length=1, max_length=90)
    takeaway: str = Field(min_length=1, max_length=220)
    narration: str = Field(min_length=20)
    slide_bullets: list[str] = Field(min_length=2, max_length=5)
    visual_prompt: str = Field(min_length=1)
    broll_prompt: str = Field(min_length=1)
    citations: list[Citation] = Field(default_factory=list)

    @field_validator("slide_bullets")
    @classmethod
    def bullets_are_brief(cls, bullets: list[str]) -> list[str]:
        for bullet in bullets:
            if len(bullet) > 130:
                raise ValueError("slide bullets must stay presentation-length")
        return bullets


class CutawayJob(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(pattern=r"^[a-z0-9_-]+$")
    prompt: str = Field(min_length=10)
    duration_seconds: float = Field(gt=0, le=12)
    required: bool = True
    status: Literal["planned", "generated", "placeholder", "skipped"] = "planned"
    output_path: str | None = None


class CostNotes(BaseModel):
    fixed_compute: str = Field(min_length=1)
    bursty_compute: str = Field(min_length=1)
    marginal_cost: str = Field(min_length=1)


class BriefingPlan(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=120)
    audience: str = Field(min_length=1)
    target_duration_seconds: int = Field(ge=180, le=300)
    sections: list[BriefingSection] = Field(min_length=5, max_length=7)
    source_citations: list[Citation] = Field(min_length=1)
    cutaway_jobs: list[CutawayJob] = Field(min_length=1)
    cost_notes: CostNotes

    @model_validator(mode="after")
    def require_briefing_shape(self) -> "BriefingPlan":
        kinds = [section.kind for section in self.sections]
        if kinds[0] != "intro":
            raise ValueError("first section must be intro")
        if kinds[-1] != "summary":
            raise ValueError("last section must be summary")
        if "key_point" not in kinds:
            raise ValueError("briefing must include key points")
        if not any(job.required for job in self.cutaway_jobs):
            raise ValueError("at least one cutaway job must be required")
        return self

