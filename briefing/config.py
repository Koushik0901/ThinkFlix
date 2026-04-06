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
    voice: str = "af_heart"
    language_code: str = "a"
    sample_rate: int = Field(default=24000, ge=8000)
    fallback_words_per_minute: int = Field(default=145, ge=80, le=220)


class VideoSettings(BaseModel):
    mode: Literal["placeholder", "wan", "api", "skip"] = "api"
    required_cutaways: int = Field(default=1, ge=1, le=3)
    opportunistic_cutaways: int = Field(default=2, ge=0, le=3)
    cutaway_duration_seconds: int = Field(default=6, ge=2, le=12)
    api_provider: Literal["fal"] = "fal"
    api_model: str = "fal-ai/wan/v2.2-a14b/text-to-video"
    api_resolution: str = "480p"
    api_aspect_ratio: str = "16:9"
    api_num_frames: int = Field(default=81, ge=17, le=161)
    api_frames_per_second: int = Field(default=16, ge=4, le=60)
    api_num_inference_steps: int = Field(default=20, ge=1, le=60)
    api_client_timeout_seconds: int = Field(default=900, ge=60)
    wan_repo_path: str = "vendor/Wan2.2"
    wan_task: str = "ti2v-5B"
    wan_size: str = "1280*704"
    wan_ckpt_dir: str = "models/Wan2.2-TI2V-5B"


class AppConfig(BaseModel):
    llm: LLMSettings = Field(default_factory=LLMSettings)
    briefing: BriefingSettings = Field(default_factory=BriefingSettings)
    slides: SlideSettings = Field(default_factory=SlideSettings)
    audio: AudioSettings = Field(default_factory=AudioSettings)
    video: VideoSettings = Field(default_factory=VideoSettings)


def load_config(path: Path | None) -> AppConfig:
    if path is None:
        return AppConfig()
    with path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    return AppConfig.model_validate(raw)
