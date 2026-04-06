from PIL import Image, ImageDraw

from briefing.config import AppConfig
from briefing.planner import _heuristic_plan
from briefing.slides import CONTENT_RIGHT, VISUAL_LEFT, _font, _wrap_text_to_width, render_section_slide


def test_render_section_slide(tmp_path) -> None:
    config = AppConfig()
    plan = _heuristic_plan("source", config, [])
    output = render_section_slide(plan.sections[0], 1, tmp_path / "slide.png", config.slides)
    assert output.exists()
    assert output.stat().st_size > 0
    with Image.open(output) as image:
        assert image.size == (1920, 1080)


def test_long_bullets_fit_before_visual_panel(tmp_path) -> None:
    config = AppConfig()
    plan = _heuristic_plan("source", config, [])
    section = plan.sections[0].model_copy(
        update={
            "slide_bullets": [
                "This intentionally long executive briefing bullet should wrap inside the left "
                "content column without crossing into the reserved visual panel area.",
            ]
        }
    )
    output = render_section_slide(section, 1, tmp_path / "long-bullet.png", config.slides)
    with Image.open(output) as image:
        draw = ImageDraw.Draw(image)
        font = _font(34)
        lines = _wrap_text_to_width(
            draw,
            section.slide_bullets[0],
            font,
            CONTENT_RIGHT - 118 - 44,
            max_lines=2,
        )
        for line in lines:
            assert draw.textbbox((0, 0), line, font=font)[2] < VISUAL_LEFT - 118 - 44


def test_render_section_slide_accepts_visual_asset(tmp_path) -> None:
    config = AppConfig()
    plan = _heuristic_plan("source", config, [])
    asset = tmp_path / "asset.png"
    Image.new("RGB", (600, 400), "#55CCDD").save(asset)

    output = render_section_slide(
        plan.sections[0],
        1,
        tmp_path / "slide-with-asset.png",
        config.slides,
        visual_asset_path=asset,
    )

    with Image.open(output) as image:
        assert image.size == (1920, 1080)
