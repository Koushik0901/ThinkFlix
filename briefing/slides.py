from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from briefing.config import SlideSettings
from briefing.models import BriefingSection


CONTENT_LEFT = 118
CONTENT_RIGHT = 1040
VISUAL_LEFT = 1180
VISUAL_RIGHT = 1800
FOOTER_Y = 1002


def render_section_slide(
    section: BriefingSection,
    index: int,
    output_path: Path,
    settings: SlideSettings,
    visual_asset_path: Path | None = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (settings.width, settings.height), settings.background)
    draw = ImageDraw.Draw(image)
    title_font = _font(78, bold=True)
    section_font = _font(26, bold=True)
    takeaway_font = _font(40)
    body_font = _font(34)
    small_font = _font(24)

    draw.rectangle((0, 0, settings.width, settings.height), fill=settings.background)
    draw.rectangle((0, 0, 18, settings.height), fill=settings.accent)
    draw.text((CONTENT_LEFT, 76), f"SECTION {index:02d}", fill=settings.accent, font=section_font)

    y = _draw_wrapped_text(
        draw,
        section.heading,
        CONTENT_LEFT,
        132,
        CONTENT_RIGHT - CONTENT_LEFT,
        title_font,
        settings.foreground,
        line_gap=10,
        max_lines=2,
    )
    y += 44
    y = _draw_wrapped_text(
        draw,
        section.takeaway,
        CONTENT_LEFT,
        y,
        CONTENT_RIGHT - CONTENT_LEFT,
        takeaway_font,
        settings.muted,
        line_gap=10,
        max_lines=3,
    )

    y += 52
    for bullet in section.slide_bullets[:4]:
        if y > FOOTER_Y - 120:
            break
        draw.ellipse((CONTENT_LEFT, y + 14, CONTENT_LEFT + 18, y + 32), fill=settings.accent)
        y = _draw_wrapped_text(
            draw,
            bullet,
            CONTENT_LEFT + 44,
            y,
            CONTENT_RIGHT - CONTENT_LEFT - 44,
            body_font,
            settings.foreground,
            line_gap=8,
            max_lines=2,
        )
        y += 24

    _draw_visual_panel(image, draw, section, index, settings, visual_asset_path)
    cite = section.citations[0].source if section.citations else "Source-backed briefing plan"
    _draw_wrapped_text(
        draw,
        f"Source: {cite}",
        CONTENT_LEFT,
        FOOTER_Y,
        CONTENT_RIGHT - CONTENT_LEFT,
        small_font,
        settings.muted,
        line_gap=6,
        max_lines=1,
    )
    if section.visual_caption:
        _draw_wrapped_text(
            draw,
            f"Visual: {section.visual_caption}",
            CONTENT_LEFT,
            FOOTER_Y + 30,
            CONTENT_RIGHT - CONTENT_LEFT,
            _font(22),
            settings.muted,
            line_gap=4,
            max_lines=1,
        )
    image.save(output_path)
    return output_path


def _draw_visual_panel(
    image: Image.Image,
    draw: ImageDraw.ImageDraw,
    section: BriefingSection,
    index: int,
    settings: SlideSettings,
    visual_asset_path: Path | None,
) -> None:
    panel_top = 150
    panel_bottom = 930
    draw.rounded_rectangle(
        (VISUAL_LEFT, panel_top, VISUAL_RIGHT, panel_bottom),
        radius=34,
        outline=settings.muted,
        width=2,
    )
    draw.rectangle((VISUAL_LEFT - 20, panel_top + 54, VISUAL_LEFT - 12, panel_bottom - 54), fill=settings.accent)

    if visual_asset_path is not None and visual_asset_path.exists():
        _draw_visual_asset(image, visual_asset_path, settings, panel_top, panel_bottom)
        return

    heading = section.heading.lower()
    if section.visual_mode == "none":
        _draw_minimal_visual(draw, settings, panel_top)
    elif section.visual_mode == "table_focus":
        _draw_spec_visual(draw, settings, panel_top)
    elif "timeline" in heading or index == 2:
        _draw_timeline_visual(draw, settings, panel_top)
    elif "variant" in heading:
        _draw_branch_visual(draw, settings, panel_top)
    elif "technical" in heading or "table" in heading:
        _draw_spec_visual(draw, settings, panel_top)
    elif "position" in heading or "access" in heading:
        _draw_positioning_visual(draw, settings, panel_top)
    elif section.kind == "summary":
        _draw_summary_visual(draw, settings, panel_top)
    else:
        _draw_briefing_visual(draw, settings, panel_top)


def _draw_visual_asset(
    canvas: Image.Image,
    visual_asset_path: Path,
    settings: SlideSettings,
    panel_top: int,
    panel_bottom: int,
) -> None:
    asset_image = Image.open(visual_asset_path).convert("RGB")
    panel_width = VISUAL_RIGHT - VISUAL_LEFT
    panel_height = panel_bottom - panel_top
    asset = _cover_image(asset_image, panel_width - 28, panel_height - 28)
    canvas.paste(asset, (VISUAL_LEFT + 14, panel_top + 14))
    overlay = Image.new("RGBA", (panel_width - 28, panel_height - 28), (11, 16, 32, 46))
    canvas.paste(overlay, (VISUAL_LEFT + 14, panel_top + 14), overlay)


def _cover_image(image: Image.Image, target_width: int, target_height: int) -> Image.Image:
    src_width, src_height = image.size
    scale = max(target_width / src_width, target_height / src_height)
    resized = image.resize((int(src_width * scale), int(src_height * scale)))
    left = max(0, (resized.width - target_width) // 2)
    top = max(0, (resized.height - target_height) // 2)
    return resized.crop((left, top, left + target_width, top + target_height))


def _draw_timeline_visual(draw: ImageDraw.ImageDraw, settings: SlideSettings, top: int) -> None:
    x = VISUAL_LEFT + 112
    y = top + 148
    draw.line((x, y, x, y + 470), fill=settings.muted, width=4)
    for idx, label in enumerate(("G1", "G2", "G3", "G4")):
        cy = y + idx * 150
        draw.ellipse((x - 22, cy - 22, x + 22, cy + 22), fill=settings.accent)
        draw.rounded_rectangle((x + 72, cy - 34, VISUAL_RIGHT - 90, cy + 34), radius=18, outline=settings.accent, width=3)
        draw.text((x + 104, cy - 20), label, fill=settings.foreground, font=_font(28, bold=True))


def _draw_branch_visual(draw: ImageDraw.ImageDraw, settings: SlideSettings, top: int) -> None:
    center = (VISUAL_LEFT + 276, top + 390)
    draw.ellipse((center[0] - 58, center[1] - 58, center[0] + 58, center[1] + 58), outline=settings.accent, width=5)
    for dx, dy in ((-120, -210), (185, -180), (-170, 170), (210, 150)):
        tx, ty = center[0] + dx, center[1] + dy
        draw.line((center[0], center[1], tx, ty), fill=settings.muted, width=3)
        draw.rounded_rectangle((tx - 58, ty - 38, tx + 58, ty + 38), radius=18, outline=settings.accent, width=3)


def _draw_spec_visual(draw: ImageDraw.ImageDraw, settings: SlideSettings, top: int) -> None:
    x0 = VISUAL_LEFT + 92
    y0 = top + 170
    width = VISUAL_RIGHT - VISUAL_LEFT - 184
    for row in range(6):
        y = y0 + row * 76
        color = settings.accent if row == 0 else settings.muted
        draw.rounded_rectangle((x0, y, x0 + width, y + 44), radius=12, outline=color, width=3 if row == 0 else 2)
        for col in range(1, 4):
            x = x0 + col * width // 4
            draw.line((x, y + 8, x, y + 36), fill=color, width=2)


def _draw_positioning_visual(draw: ImageDraw.ImageDraw, settings: SlideSettings, top: int) -> None:
    x0 = VISUAL_LEFT + 100
    y0 = top + 230
    draw.line((x0, y0 + 360, VISUAL_RIGHT - 100, y0 + 360), fill=settings.muted, width=3)
    draw.line((x0, y0 + 360, x0, y0), fill=settings.muted, width=3)
    for idx, radius in enumerate((34, 48, 62, 78)):
        cx = x0 + 92 + idx * 105
        cy = y0 + 308 - idx * 70
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=settings.accent, width=4)


def _draw_summary_visual(draw: ImageDraw.ImageDraw, settings: SlideSettings, top: int) -> None:
    cx = VISUAL_LEFT + 310
    cy = top + 390
    for radius in (240, 170, 96):
        draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), outline=settings.muted, width=2)
    draw.ellipse((cx - 62, cy - 62, cx + 62, cy + 62), fill=settings.accent)


def _draw_briefing_visual(draw: ImageDraw.ImageDraw, settings: SlideSettings, top: int) -> None:
    x0 = VISUAL_LEFT + 110
    y0 = top + 210
    for idx in range(5):
        x = x0 + idx * 70
        y = y0 + idx * 74
        draw.rounded_rectangle((x, y, x + 210, y + 56), radius=18, outline=settings.accent, width=3)
        if idx:
            draw.line((x - 60, y + 28, x, y + 28), fill=settings.muted, width=3)


def _draw_minimal_visual(draw: ImageDraw.ImageDraw, settings: SlideSettings, top: int) -> None:
    cx = VISUAL_LEFT + 300
    cy = top + 360
    for radius in (220, 150):
        draw.arc((cx - radius, cy - radius, cx + radius, cy + radius), 210, 20, fill=settings.muted, width=3)
    draw.ellipse((cx - 38, cy - 38, cx + 38, cy + 38), fill=settings.accent)


def _draw_wrapped_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    x: int,
    y: int,
    max_width: int,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill: str,
    line_gap: int,
    max_lines: int,
) -> int:
    lines = _wrap_text_to_width(draw, text, font, max_width, max_lines)
    line_height = _text_height(draw, "Ag", font) + line_gap
    for line in lines:
        draw.text((x, y), line, fill=fill, font=font)
        y += line_height
    return y


def _wrap_text_to_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    max_lines: int,
) -> list[str]:
    wrapped: list[str] = []
    for paragraph in textwrap.wrap(text, width=72) or [""]:
        line = ""
        for word in paragraph.split():
            candidate = f"{line} {word}".strip()
            if _text_width(draw, candidate, font) <= max_width:
                line = candidate
            else:
                if line:
                    wrapped.append(line)
                line = word
            if len(wrapped) == max_lines:
                break
        if len(wrapped) == max_lines:
            break
        if line:
            wrapped.append(line)
        if len(wrapped) == max_lines:
            break
    if len(wrapped) == max_lines and _text_width(draw, wrapped[-1], font) > max_width:
        wrapped[-1] = wrapped[-1][: max(1, len(wrapped[-1]) - 1)].rstrip() + "..."
    return wrapped[:max_lines]


def _text_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _text_height(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
) -> int:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
        if bold
        else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()
