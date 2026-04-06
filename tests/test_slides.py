from briefing.config import AppConfig
from briefing.planner import _heuristic_plan
from briefing.slides import render_section_slide


def test_render_section_slide(tmp_path) -> None:
    config = AppConfig()
    plan = _heuristic_plan("source", config, [])
    output = render_section_slide(plan.sections[0], 1, tmp_path / "slide.png", config.slides)
    assert output.exists()
    assert output.stat().st_size > 0

