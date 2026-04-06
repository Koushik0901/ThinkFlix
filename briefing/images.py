from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path

import httpx
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

from briefing.config import AppConfig, SlideSettings
from briefing.models import BriefingSection


def validate_visual_runtime(sections: list[BriefingSection], config: AppConfig) -> None:
    if config.visuals.mode != "api":
        return
    if not any(section.visual_mode == "generated_image" for section in sections):
        return
    if _ltx_api_key(config) is None:
        env_names = ", ".join(config.visuals.api_key_env_vars)
        raise RuntimeError(
            f"{env_names} is required when Gemma selects generated_image visuals. "
            "Set one of these variables or run in local visual mode."
        )


def prepare_section_visuals(
    sections: list[BriefingSection],
    out_dir: Path,
    config: AppConfig,
    slide_settings: SlideSettings,
) -> dict[int, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rendered: dict[int, Path] = {}
    generated_so_far = 0
    for index, section in enumerate(sections, start=1):
        if section.visual_mode != "generated_image":
            continue
        if generated_so_far >= config.visuals.max_generated_images:
            continue
        generated_so_far += 1
        if config.visuals.mode == "api":
            rendered[index] = _run_provider_image_or_placeholder(
                section,
                index,
                out_dir,
                config,
                slide_settings,
            )
        else:
            rendered[index] = _render_generated_visual_placeholder(
                section,
                index,
                out_dir,
                slide_settings,
                status="local_placeholder",
            )
    return rendered


def _run_provider_image_or_placeholder(
    section: BriefingSection,
    index: int,
    out_dir: Path,
    config: AppConfig,
    slide_settings: SlideSettings,
) -> Path:
    try:
        return _run_ltx_visual(section, index, out_dir, config)
    except Exception as exc:  # noqa: BLE001
        if not config.visuals.api_fallback_to_placeholder:
            raise
        _write_visual_failure_manifest(section, index, out_dir, config, exc)
        return _render_generated_visual_placeholder(
            section,
            index,
            out_dir,
            slide_settings,
            status="api_failed_placeholder",
        )


def _run_ltx_visual(section: BriefingSection, index: int, out_dir: Path, config: AppConfig) -> Path:
    if section.image_prompt is None:
        raise RuntimeError("generated_image sections must include an image_prompt")
    prompt = section.image_prompt.strip()
    video_path = (out_dir / f"section_{index:02d}_provider.mp4").resolve()
    image_path = (out_dir / f"section_{index:02d}.png").resolve()
    manifest_path = out_dir / f"section_{index:02d}_api_job.json"
    failure_manifest_path = out_dir / f"section_{index:02d}_api_failure.json"
    payload = {
        "prompt": prompt,
        "model": config.visuals.api_model,
        "duration": config.visuals.provider_video_duration_seconds,
        "resolution": config.visuals.api_resolution,
    }
    manifest_path.write_text(
        json.dumps(
            {
                "section_index": index,
                "provider": config.visuals.api_provider,
                "endpoint": config.visuals.api_endpoint,
                "model": config.visuals.api_model,
                "request": payload,
                "visual_role": section.visual_role,
                "visual_grounding_notes": section.visual_grounding_notes,
                "expected_video_output": str(video_path),
                "expected_image_output": str(image_path),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    video_path.write_bytes(_submit_ltx_visual_request(config, payload))
    _extract_frame(video_path, image_path, timestamp_seconds=max(1.0, payload["duration"] / 2))
    failure_manifest_path.unlink(missing_ok=True)
    return image_path


def _submit_ltx_visual_request(config: AppConfig, payload: dict[str, object]) -> bytes:
    token = _ltx_api_key(config)
    if token is None:
        raise RuntimeError("LTX API key missing")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    last_exc: Exception | None = None
    for attempt in range(config.visuals.api_retries + 1):
        try:
            response = httpx.post(
                config.visuals.api_endpoint,
                json=payload,
                headers=headers,
                timeout=config.visuals.api_client_timeout_seconds,
            )
            response.raise_for_status()
            if not response.content:
                raise RuntimeError("LTX API returned an empty response for the generated visual")
            if "application/json" in response.headers.get("content-type", "").lower():
                raise RuntimeError(f"LTX API returned JSON instead of media: {response.text[:1000]}")
            return response.content
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
        if attempt < config.visuals.api_retries:
            time.sleep(min(2**attempt, 5))
    if last_exc is None:
        raise RuntimeError("LTX visual request failed without returning an exception")
    raise last_exc


def _extract_frame(video_path: Path, image_path: Path, timestamp_seconds: float) -> None:
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    image_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            ffmpeg,
            "-y",
            "-ss",
            f"{timestamp_seconds:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            str(image_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def _write_visual_failure_manifest(
    section: BriefingSection,
    index: int,
    out_dir: Path,
    config: AppConfig,
    exc: Exception,
) -> None:
    manifest_path = out_dir / f"section_{index:02d}_api_failure.json"
    manifest_path.write_text(
        json.dumps(
            {
                "section_index": index,
                "provider": config.visuals.api_provider,
                "endpoint": config.visuals.api_endpoint,
                "model": config.visuals.api_model,
                "image_prompt": section.image_prompt,
                "visual_role": section.visual_role,
                "visual_grounding_notes": section.visual_grounding_notes,
                "error_type": type(exc).__name__,
                "error": str(exc),
                "fallback": "placeholder_image",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def _render_generated_visual_placeholder(
    section: BriefingSection,
    index: int,
    out_dir: Path,
    settings: SlideSettings,
    status: str,
) -> Path:
    output_path = out_dir / f"section_{index:02d}.png"
    image = Image.new("RGB", (settings.width, settings.height), settings.background)
    draw = ImageDraw.Draw(image)
    title_font = _font(54, bold=True)
    body_font = _font(28)
    muted_font = _font(22)
    draw.rounded_rectangle((120, 120, settings.width - 120, settings.height - 120), radius=36, outline=settings.muted, width=3)
    draw.text((170, 190), "Generated Visual Placeholder", fill=settings.foreground, font=title_font)
    draw.text((170, 290), section.visual_role, fill=settings.accent, font=body_font)
    draw.text((170, 360), section.visual_grounding_notes, fill=settings.foreground, font=body_font)
    if section.image_prompt:
        _draw_wrapped(draw, f"Prompt: {section.image_prompt}", (170, 450), settings.width - 340, body_font, settings.muted)
    draw.text((170, settings.height - 170), f"Status: {status}", fill=settings.muted, font=muted_font)
    image.save(output_path)
    return output_path


def _draw_wrapped(
    draw: ImageDraw.ImageDraw,
    text: str,
    origin: tuple[int, int],
    max_width: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: str,
) -> None:
    x, y = origin
    words = text.split()
    line = ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            line = candidate
            continue
        draw.text((x, y), line, fill=fill, font=font)
        y += 40
        line = word
    if line:
        draw.text((x, y), line, fill=fill, font=font)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _ltx_api_key(config: AppConfig) -> str | None:
    for env_name in config.visuals.api_key_env_vars:
        value = os.getenv(env_name)
        if value:
            return value
    return None
