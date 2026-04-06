from pathlib import Path

from briefing.config import AppConfig
from briefing.models import BriefingPlan
from briefing.pipeline import _allocate_section_durations, run_pipeline


def test_allocate_section_durations_adds_short_tail_padding_only() -> None:
    durations = _allocate_section_durations([20.0, 30.0, 40.0], target_seconds=120, extra_visual_seconds=0)
    assert durations == [21.5, 31.5, 41.5]
    assert round(sum(durations)) < 120


def test_allocate_section_durations_does_not_shrink_long_audio() -> None:
    assert _allocate_section_durations([200.0], target_seconds=180, extra_visual_seconds=0) == [200.0]


def test_pipeline_does_not_require_visual_api_key_when_plan_has_no_generated_images(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv("LTX_API_KEY", raising=False)
    monkeypatch.delenv("LTXV_API_KEY", raising=False)
    plan = BriefingPlan.model_validate(
        {
            "title": "No Generated Visuals Briefing",
            "audience": "technical leadership",
            "target_duration_seconds": 180,
            "source_citations": [{"source": "fixture", "url": None, "note": "fixture"}],
            "sections": [
                _fixture_section("intro", "Intro", "A source-backed intro.", "diagram"),
                _fixture_section("key_point", "Point One", "A source-backed point.", "diagram"),
                _fixture_section("key_point", "Point Two", "Another source-backed point.", "diagram"),
                _fixture_section("key_point", "Point Three", "A third source-backed point.", "table_focus"),
                _fixture_section("summary", "Summary", "A source-backed summary.", "none"),
            ],
            "cost_notes": {"fixed_compute": "fixed", "bursty_compute": "bursty", "marginal_cost": "marginal"},
        }
    )
    source = tmp_path / "source.md"
    source.write_text("# Source\n\nBrief fixture.", encoding="utf-8")
    config = AppConfig()
    config.visuals.mode = "api"
    monkeypatch.setattr("briefing.pipeline.build_briefing_plan", lambda source_text, app_config: plan)
    monkeypatch.setattr("briefing.pipeline.synthesize_narration", lambda text, path, settings: 1.0)
    monkeypatch.setattr("briefing.pipeline.prepare_section_visuals", lambda sections, out_dir, cfg, slide_settings: {})
    monkeypatch.setattr("briefing.pipeline.probe_duration", lambda path: 180.0)

    def fake_render_image_segment(segment):
        segment.output_path.parent.mkdir(parents=True, exist_ok=True)
        segment.output_path.touch()
        return segment.output_path

    def fake_concat_segments(paths, output):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.touch()
        return output

    monkeypatch.setattr("briefing.pipeline.render_image_segment", fake_render_image_segment)
    monkeypatch.setattr("briefing.pipeline.concat_segments", fake_concat_segments)

    rendered_plan = run_pipeline(source, tmp_path / "out", config)

    assert all(section.visual_mode != "generated_image" for section in rendered_plan.sections)


def test_pipeline_passes_generated_visual_assets_into_slide_rendering(tmp_path, monkeypatch) -> None:
    generated_visual = tmp_path / "visual.png"
    generated_visual.touch()
    plan = BriefingPlan.model_validate(
        {
            "title": "Generated Visual Briefing",
            "audience": "technical leadership",
            "target_duration_seconds": 180,
            "source_citations": [{"source": "fixture", "url": None, "note": "fixture"}],
            "sections": [
                _fixture_section(
                    "intro",
                    "Intro",
                    "A source-backed intro.",
                    "generated_image",
                    image_prompt="grounded generated image prompt",
                ),
                _fixture_section("key_point", "Point One", "A source-backed point.", "diagram"),
                _fixture_section("key_point", "Point Two", "Another source-backed point.", "diagram"),
                _fixture_section("key_point", "Point Three", "A third source-backed point.", "table_focus"),
                _fixture_section("summary", "Summary", "A source-backed summary.", "none"),
            ],
            "cost_notes": {"fixed_compute": "fixed", "bursty_compute": "bursty", "marginal_cost": "marginal"},
        }
    )
    source = tmp_path / "source.md"
    source.write_text("# Source\n\nBrief fixture.", encoding="utf-8")
    config = AppConfig()
    captured: list[Path | None] = []

    monkeypatch.setattr("briefing.pipeline.build_briefing_plan", lambda source_text, app_config: plan)
    monkeypatch.setattr("briefing.pipeline.validate_visual_runtime", lambda sections, cfg: None)
    monkeypatch.setattr(
        "briefing.pipeline.prepare_section_visuals",
        lambda sections, out_dir, cfg, slide_settings: {1: generated_visual},
    )
    monkeypatch.setattr("briefing.pipeline.synthesize_narration", lambda text, path, settings: 1.0)
    monkeypatch.setattr("briefing.pipeline.probe_duration", lambda path: 180.0)

    def fake_render_section_slide(section, index, output_path, settings, visual_asset_path=None):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.touch()
        captured.append(visual_asset_path)
        return output_path

    def fake_render_image_segment(segment):
        segment.output_path.parent.mkdir(parents=True, exist_ok=True)
        segment.output_path.touch()
        return segment.output_path

    def fake_concat_segments(paths, output):
        output.parent.mkdir(parents=True, exist_ok=True)
        output.touch()
        return output

    monkeypatch.setattr("briefing.pipeline.render_section_slide", fake_render_section_slide)
    monkeypatch.setattr("briefing.pipeline.render_image_segment", fake_render_image_segment)
    monkeypatch.setattr("briefing.pipeline.concat_segments", fake_concat_segments)

    run_pipeline(source, tmp_path / "out", config)

    assert captured[0] == generated_visual
    assert captured[1] is None


def _fixture_section(kind: str, heading: str, takeaway: str, visual_mode: str, image_prompt: str | None = None) -> dict:
    return {
        "kind": kind,
        "heading": heading,
        "takeaway": takeaway,
        "narration": "This is a source-backed section with enough content to pass schema validation.",
        "slide_bullets": ["Source-backed", "Brief"],
        "visual_mode": visual_mode,
        "visual_role": "Support the current section.",
        "image_prompt": image_prompt,
        "visual_caption": "Helpful framing.",
        "visual_grounding_notes": "Grounded in the source.",
        "citations": [{"source": "fixture", "url": None, "note": "fixture"}],
    }
