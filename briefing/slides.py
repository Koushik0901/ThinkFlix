from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from briefing.config import SlideSettings
from briefing.models import BriefingSection


def render_section_slide(
    section: BriefingSection, index: int, output_path: Path, settings: SlideSettings
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (settings.width, settings.height), settings.background)
    draw = ImageDraw.Draw(image)
    title_font = _font(76)
    heading_font = _font(46)
    body_font = _font(38)
    small_font = _font(28)

    margin_x = 120
    draw.rectangle((0, 0, settings.width, 18), fill=settings.accent)
    draw.text((margin_x, 80), f"{index:02d}", fill=settings.accent, font=heading_font)
    draw.text((margin_x, 150), section.heading, fill=settings.foreground, font=title_font)

    y = 300
    for line in textwrap.wrap(section.takeaway, width=58):
        draw.text((margin_x, y), line, fill=settings.muted, font=heading_font)
        y += 58

    y += 30
    for bullet in section.slide_bullets:
        draw.ellipse((margin_x, y + 16, margin_x + 20, y + 36), fill=settings.accent)
        wrapped = textwrap.wrap(bullet, width=64)
        for idx, line in enumerate(wrapped):
            draw.text((margin_x + 42, y + idx * 46), line, fill=settings.foreground, font=body_font)
        y += max(1, len(wrapped)) * 46 + 26

    _draw_visual_motif(draw, settings)
    cite = section.citations[0].source if section.citations else "Source-backed briefing plan"
    draw.text((margin_x, settings.height - 90), f"Source: {cite}", fill=settings.muted, font=small_font)
    image.save(output_path)
    return output_path


def render_cutaway_placeholder(prompt: str, output_path: Path, settings: SlideSettings) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (settings.width, settings.height), "#111827")
    draw = ImageDraw.Draw(image)
    title_font = _font(64)
    body_font = _font(34)
    draw.rectangle((0, 0, settings.width, settings.height), outline=settings.accent, width=14)
    draw.text((120, 120), "Generated Cutaway Placeholder", fill=settings.accent, font=title_font)
    y = 250
    for line in textwrap.wrap(prompt, width=72)[:8]:
        draw.text((120, y), line, fill=settings.foreground, font=body_font)
        y += 48
    draw.text(
        (120, settings.height - 110),
        "Replace this with Wan2.2 output when GPU generation completes.",
        fill=settings.muted,
        font=body_font,
    )
    _draw_visual_motif(draw, settings)
    image.save(output_path)
    return output_path


def _draw_visual_motif(draw: ImageDraw.ImageDraw, settings: SlideSettings) -> None:
    right = settings.width - 120
    top = 250
    for idx in range(5):
        x = right - idx * 120
        y = top + idx * 74
        draw.rounded_rectangle((x - 420, y, x, y + 62), radius=18, outline=settings.accent, width=4)
        draw.line((x - 420, y + 31, x - 540, y + 31), fill=settings.muted, width=3)
    draw.ellipse((settings.width - 560, 690, settings.width - 180, 980), outline=settings.accent, width=6)
    draw.ellipse((settings.width - 500, 740, settings.width - 240, 930), outline=settings.muted, width=3)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()

