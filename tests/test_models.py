import pytest
from pydantic import ValidationError

from briefing.config import AppConfig
from briefing.models import BriefingPlan, BriefingSection
from briefing.planner import _heuristic_plan, _plan_with_ollama, _user_prompt, build_briefing_plan
from briefing.prompts import load_prompt_template


def test_heuristic_plan_has_required_shape() -> None:
    plan = _heuristic_plan("source https://example.com/report", AppConfig(), [])
    assert plan.sections[0].kind == "intro"
    assert plan.sections[-1].kind == "summary"
    assert any(section.kind == "key_point" for section in plan.sections)


def test_heuristic_plan_is_gemma_specific_for_gemma_pdf_text() -> None:
    plan = _heuristic_plan(
        "Gemma (language model)\nGoogle DeepMind\nTechnical specifications of Gemma models",
        AppConfig(),
        [],
    )
    assert "Gemma" in plan.title
    assert any("table" in section.narration.lower() for section in plan.sections)
    assert plan.source_citations[0].url == "data/input/Gemma_(language_model).pdf"


def test_heuristic_plan_keeps_debug_details_out_of_narration() -> None:
    plan = _heuristic_plan(
        "Gemma (language model)\nGoogle DeepMind\nTechnical specifications of Gemma models",
        AppConfig(),
        ["ollama:gemma4: unavailable"],
    )
    narration = " ".join(section.narration for section in plan.sections).lower()
    assert "local heuristic fallback" not in narration
    assert "planner errors" not in narration
    assert "ollama" not in narration


def test_gemma_heuristic_narration_is_briefing_length() -> None:
    plan = _heuristic_plan(
        "Gemma (language model)\nGoogle DeepMind\nTechnical specifications of Gemma models",
        AppConfig(),
        [],
    )

    total_words = sum(len(section.narration.split()) for section in plan.sections)

    assert 420 <= total_words <= 560
    assert all(65 <= len(section.narration.split()) <= 95 for section in plan.sections)


def test_gemma_heuristic_sections_do_not_include_project_meta_claims() -> None:
    plan = _heuristic_plan(
        "Gemma (language model)\nGoogle DeepMind\nTechnical specifications of Gemma models",
        AppConfig(),
        [],
    )

    section_text = " ".join(
        [
            *(section.narration for section in plan.sections),
            *(section.takeaway for section in plan.sections),
            *(bullet for section in plan.sections for bullet in section.slide_bullets),
            *(section.visual_grounding_notes for section in plan.sections),
        ]
    ).lower()

    assert "generated cutaway" not in section_text
    assert "generated-video" not in section_text
    assert "for this project" not in section_text
    assert "table-aware pdf extraction" not in section_text


def test_build_briefing_plan_overwrites_cost_notes_as_pipeline_metadata() -> None:
    config = AppConfig()
    config.llm.provider = "heuristic"

    plan = build_briefing_plan(
        "Gemma (language model)\nGoogle DeepMind\nTechnical specifications of Gemma models",
        config,
    )

    assert "PDF/text extraction" in plan.cost_notes.fixed_compute
    assert "still visuals" in plan.cost_notes.bursty_compute
    assert "near-zero" in plan.cost_notes.marginal_cost


def test_generic_heuristic_narration_is_briefing_length() -> None:
    plan = _heuristic_plan("source https://example.com/report", AppConfig(), [])

    total_words = sum(len(section.narration.split()) for section in plan.sections)

    assert 420 <= total_words <= 560
    assert all(65 <= len(section.narration.split()) <= 95 for section in plan.sections)


def test_gemma_visual_prompts_avoid_label_inducing_terms() -> None:
    plan = _heuristic_plan(
        "Gemma (language model)\nGoogle DeepMind\nTechnical specifications of Gemma models",
        AppConfig(),
        [],
    )
    prompts = [section.image_prompt or "" for section in plan.sections]
    combined_prompts = " ".join(prompts).lower()
    assert "dashboard" not in combined_prompts
    assert "icon" not in combined_prompts
    assert "label" not in combined_prompts
    assert "node" not in combined_prompts
    assert "ui" not in combined_prompts


def test_gemma_user_prompt_is_structured_and_source_grounded() -> None:
    prompt = _user_prompt(
        "Gemma source excerpt with table fields and release timeline.",
        AppConfig(),
    )

    assert "<source_context>" in prompt
    assert "</source_context>" in prompt
    assert "<task>" in prompt
    assert "<orchestration_requirements>" in prompt
    assert "<output_schema>" in prompt
    assert "Use only claims supported by the source context" in prompt
    assert "Return the JSON object now." in prompt


def test_gemma_user_prompt_comes_from_template_file() -> None:
    template = load_prompt_template("planner_gemma.md")

    assert "Create source-grounded multimedia briefing plans" in template
    assert "{{ source_context }}" in template
    assert "{{ output_schema }}" in template
    assert "You are the visual orchestrator" in template


def test_ollama_gemma_prompt_uses_single_user_message(monkeypatch) -> None:
    config = AppConfig()
    captured: dict[str, object] = {}
    valid_plan = _heuristic_plan("source", config, []).model_dump_json()

    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, dict[str, str]]:
            return {"message": {"content": valid_plan}}

    def fake_post(url: str, **kwargs) -> FakeResponse:
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse()

    monkeypatch.setattr("briefing.planner.httpx.post", fake_post)

    plan = _plan_with_ollama("source", config, "gemma4")

    assert plan.title == "AI Infrastructure Is the New AI Strategy"
    request_json = captured["kwargs"]["json"]  # type: ignore[index]
    assert request_json["format"] == "json"
    assert request_json["messages"][0]["role"] == "user"
    assert len(request_json["messages"]) == 1
    assert "<source_context>" in request_json["messages"][0]["content"]


def test_ollama_provider_tries_local_fallback_model(monkeypatch) -> None:
    config = AppConfig()
    config.llm.provider = "ollama"
    config.llm.model = "gemma4"
    config.llm.fallback_model = "gemma4:e4b"
    tried: list[str] = []

    def fake_plan_with_ollama(source_text: str, app_config: AppConfig, model: str) -> BriefingPlan:
        tried.append(model)
        if model == "gemma4":
            raise RuntimeError("primary model unavailable")
        return _heuristic_plan(source_text, app_config, [])

    monkeypatch.setattr("briefing.planner._plan_with_ollama", fake_plan_with_ollama)

    plan = build_briefing_plan("source https://example.com/report", config)

    assert plan.title == "AI Infrastructure Is the New AI Strategy"
    assert tried == ["gemma4", "gemma4:e4b"]


def test_plan_rejects_missing_summary() -> None:
    data = _heuristic_plan("source", AppConfig(), []).model_dump()
    data["sections"][-1]["kind"] = "key_point"
    with pytest.raises(ValidationError):
        BriefingPlan.model_validate(data)


def test_generated_image_section_requires_image_prompt() -> None:
    with pytest.raises(ValidationError):
        BriefingSection.model_validate(
            {
                "kind": "intro",
                "heading": "Intro",
                "takeaway": "Takeaway",
                "narration": "This is enough narration to pass validation.",
                "slide_bullets": ["One", "Two"],
                "visual_mode": "generated_image",
                "visual_role": "Support the topic.",
                "visual_grounding_notes": "Grounded in the source.",
                "citations": [{"source": "fixture", "url": None, "note": "fixture"}],
            }
        )


def test_non_generated_image_section_rejects_image_prompt() -> None:
    with pytest.raises(ValidationError):
        BriefingSection.model_validate(
            {
                "kind": "intro",
                "heading": "Intro",
                "takeaway": "Takeaway",
                "narration": "This is enough narration to pass validation.",
                "slide_bullets": ["One", "Two"],
                "visual_mode": "diagram",
                "visual_role": "Support the topic.",
                "image_prompt": "should not be here",
                "visual_grounding_notes": "Grounded in the source.",
                "citations": [{"source": "fixture", "url": None, "note": "fixture"}],
            }
        )
