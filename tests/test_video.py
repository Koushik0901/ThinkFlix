from pathlib import Path

import httpx
import pytest

from briefing.config import AppConfig
from briefing.images import (
    _ltx_api_key,
    _run_ltx_visual,
    _submit_ltx_visual_request,
    prepare_section_visuals,
    validate_visual_runtime,
)
from briefing.models import BriefingSection


def test_validate_visual_runtime_requires_ltx_token_for_generated_images(monkeypatch) -> None:
    monkeypatch.delenv("LTX_API_KEY", raising=False)
    monkeypatch.delenv("LTXV_API_KEY", raising=False)
    config = AppConfig()
    config.visuals.mode = "api"

    with pytest.raises(RuntimeError, match="LTX_API_KEY"):
        validate_visual_runtime([_generated_image_section()], config)


def test_validate_visual_runtime_does_not_require_key_without_generated_images(monkeypatch) -> None:
    monkeypatch.delenv("LTX_API_KEY", raising=False)
    monkeypatch.delenv("LTXV_API_KEY", raising=False)
    config = AppConfig()
    config.visuals.mode = "api"

    validate_visual_runtime([_diagram_section()], config)


def test_ltx_api_key_accepts_legacy_documented_name(monkeypatch) -> None:
    monkeypatch.delenv("LTX_API_KEY", raising=False)
    monkeypatch.setenv("LTXV_API_KEY", "ltxv_test")

    assert _ltx_api_key(AppConfig()) == "ltxv_test"


def test_prepare_section_visuals_skips_non_generated_sections(tmp_path, monkeypatch) -> None:
    config = AppConfig()
    config.visuals.mode = "local"
    rendered = prepare_section_visuals([_diagram_section(), _none_section()], tmp_path, config, config.slides)

    assert rendered == {}


def test_prepare_section_visuals_caps_generated_images(tmp_path, monkeypatch) -> None:
    config = AppConfig()
    config.visuals.mode = "local"
    config.visuals.max_generated_images = 1
    sections = [_generated_image_section(), _generated_image_section("Second prompt")]

    rendered = prepare_section_visuals(sections, tmp_path, config, config.slides)

    assert list(rendered.keys()) == [1]


def test_run_ltx_visual_writes_provider_frame(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LTX_API_KEY", "ltxv_test")
    monkeypatch.setattr("briefing.images._submit_ltx_visual_request", lambda config, payload: b"video-bytes")

    def fake_extract_frame(video_path: Path, image_path: Path, timestamp_seconds: float) -> None:
        image_path.write_bytes(b"png-bytes")

    monkeypatch.setattr("briefing.images._extract_frame", fake_extract_frame)
    section = _generated_image_section()
    output_path = _run_ltx_visual(section, 1, tmp_path, AppConfig())

    assert output_path.read_bytes() == b"png-bytes"
    manifest = (tmp_path / "section_01_api_job.json").read_text(encoding="utf-8")
    assert '"provider": "ltx"' in manifest
    assert section.image_prompt in manifest


def test_prepare_section_visuals_falls_back_to_placeholder_on_provider_error(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("LTX_API_KEY", "ltxv_test")
    monkeypatch.setattr(
        "briefing.images._run_ltx_visual",
        lambda section, index, out_dir, config: (_ for _ in ()).throw(RuntimeError("provider failed")),
    )
    config = AppConfig()
    config.visuals.mode = "api"

    rendered = prepare_section_visuals([_generated_image_section()], tmp_path, config, config.slides)

    assert rendered[1].exists()
    assert (tmp_path / "section_01_api_failure.json").exists()


def test_ltx_submission_passes_gemma_prompt_without_rewriting(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeResponse:
        content = b"video-bytes"
        headers = {"content-type": "video/mp4"}

        def raise_for_status(self) -> None:
            return None

    def fake_post(url: str, **kwargs) -> FakeResponse:
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse()

    monkeypatch.setenv("LTX_API_KEY", "ltxv_test")
    monkeypatch.setattr("briefing.images.httpx.post", fake_post)
    config = AppConfig()
    payload = {
        "prompt": "Gemma-authored fully grounded provider prompt",
        "model": "ltx-2-3-fast",
        "duration": 6,
        "resolution": "1920x1080",
    }

    video = _submit_ltx_visual_request(config, payload)

    assert video == b"video-bytes"
    kwargs = captured["kwargs"]  # type: ignore[assignment]
    assert kwargs["json"]["prompt"] == "Gemma-authored fully grounded provider prompt"  # type: ignore[index]


def test_ltx_submission_retries_transient_errors(monkeypatch) -> None:
    calls = {"count": 0}
    config = AppConfig()
    config.visuals.api_retries = 1

    class FakeResponse:
        content = b"video-bytes"
        headers = {"content-type": "video/mp4"}

        def raise_for_status(self) -> None:
            return None

    def fake_post(url: str, **kwargs):
        calls["count"] += 1
        if calls["count"] == 1:
            raise ConnectionError("transient reset")
        return FakeResponse()

    monkeypatch.setenv("LTX_API_KEY", "ltxv_test")
    monkeypatch.setattr("briefing.images.time.sleep", lambda seconds: None)
    monkeypatch.setattr("briefing.images.httpx.post", fake_post)

    video = _submit_ltx_visual_request(
        config,
        {
            "prompt": "Gemma-authored fully grounded provider prompt",
            "model": "ltx-2-3-fast",
            "duration": 6,
            "resolution": "1920x1080",
        },
    )

    assert video == b"video-bytes"
    assert calls["count"] == 2


def test_ltx_submission_reports_http_errors(monkeypatch) -> None:
    config = AppConfig()
    config.visuals.api_retries = 0

    def fake_post(url: str, **kwargs) -> httpx.Response:
        request = httpx.Request("POST", url)
        return httpx.Response(
            401,
            request=request,
            json={"error": "invalid key"},
            headers={"content-type": "application/json"},
        )

    monkeypatch.setenv("LTX_API_KEY", "ltxv_bad")
    monkeypatch.setattr("briefing.images.httpx.post", fake_post)

    with pytest.raises(httpx.HTTPStatusError):
        _submit_ltx_visual_request(
            config,
            {
                "prompt": "Gemma-authored fully grounded provider prompt",
                "model": "ltx-2-3-fast",
                "duration": 6,
                "resolution": "1920x1080",
            },
        )


def _generated_image_section(prompt: str = "Gemma-authored provider prompt") -> BriefingSection:
    return BriefingSection.model_validate(
        {
            "kind": "intro",
            "heading": "Intro",
            "takeaway": "Takeaway",
            "narration": "This is enough narration to pass validation.",
            "slide_bullets": ["One", "Two"],
            "visual_mode": "generated_image",
            "visual_role": "Support the topic.",
            "image_prompt": prompt,
            "visual_caption": "Helpful framing.",
            "visual_grounding_notes": "Grounded in the source.",
            "citations": [{"source": "fixture", "url": None, "note": "fixture"}],
        }
    )


def _diagram_section() -> BriefingSection:
    return BriefingSection.model_validate(
        {
            "kind": "key_point",
            "heading": "Point",
            "takeaway": "Takeaway",
            "narration": "This is enough narration to pass validation.",
            "slide_bullets": ["One", "Two"],
            "visual_mode": "diagram",
            "visual_role": "Support the topic.",
            "visual_caption": "Helpful framing.",
            "visual_grounding_notes": "Grounded in the source.",
            "citations": [{"source": "fixture", "url": None, "note": "fixture"}],
        }
    )


def _none_section() -> BriefingSection:
    return BriefingSection.model_validate(
        {
            "kind": "summary",
            "heading": "Summary",
            "takeaway": "Takeaway",
            "narration": "This is enough narration to pass validation.",
            "slide_bullets": ["One", "Two"],
            "visual_mode": "none",
            "visual_role": "Support the topic.",
            "visual_caption": "Helpful framing.",
            "visual_grounding_notes": "Grounded in the source.",
            "citations": [{"source": "fixture", "url": None, "note": "fixture"}],
        }
    )
