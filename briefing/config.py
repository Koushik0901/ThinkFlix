from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field


class LLMSettings(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    provider: Literal["auto", "ollama", "heuristic"] = "ollama"
    model: str = "gemma4"
    fallback_model: str = "gemma4:e4b"
    ollama_url: str = "http://localhost:11434"
    timeout_seconds: int = Field(default=180, ge=5)
    retries: int = Field(default=2, ge=0, le=5)


class BriefingSettings(BaseModel):
    audience: str = "busy technical leadership"
    target_duration_seconds: int = Field(default=240, ge=180, le=300)
    max_sections: int = Field(default=6, ge=5, le=7)
    min_sections: int = Field(default=5, ge=5, le=7)


class SlideSettings(BaseModel):
    width: int = Field(default=1920, ge=640)
    height: int = Field(default=1080, ge=360)
    background: str = "#0B1020"
    foreground: str = "#F8FAFC"
    accent: str = "#6EE7B7"
    muted: str = "#94A3B8"


class AudioSettings(BaseModel):
    repo_id: str = "hexgrad/Kokoro-82M"
    voice: str = "af_heart"
    language_code: str = "a"
    sample_rate: int = Field(default=24000, ge=8000)
    fallback_words_per_minute: int = Field(default=145, ge=80, le=220)


class VisualSettings(BaseModel):
    mode: Literal["local", "api"] = "api"
    max_generated_images: int = Field(default=2, ge=0, le=3)
    provider_video_duration_seconds: int = Field(default=6, ge=4, le=20)
    api_provider: Literal["ltx"] = "ltx"
    api_endpoint: str = "https://api.ltx.video/v1/text-to-video"
    api_key_env_vars: list[str] = Field(default_factory=lambda: ["LTX_API_KEY", "LTXV_API_KEY"])
    api_model: str = "ltx-2-3-fast"
    api_resolution: str = "1920x1080"
    api_client_timeout_seconds: int = Field(default=900, ge=60)
    api_retries: int = Field(default=2, ge=0, le=5)
    api_fallback_to_placeholder: bool = True


class AppConfig(BaseModel):
    llm: LLMSettings = Field(default_factory=LLMSettings)
    briefing: BriefingSettings = Field(default_factory=BriefingSettings)
    slides: SlideSettings = Field(default_factory=SlideSettings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    visuals: VisualSettings = Field(default_factory=VisualSettings)


def load_config(path: Path | None) -> AppConfig:
    if path is None:
        return AppConfig()
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return AppConfig.model_validate(raw)
