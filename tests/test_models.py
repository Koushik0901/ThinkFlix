import pytest
from pydantic import ValidationError

from briefing.config import AppConfig
from briefing.models import BriefingPlan
from briefing.planner import _heuristic_plan, build_briefing_plan


def test_heuristic_plan_has_required_shape() -> None:
    plan = _heuristic_plan("source https://example.com/report", AppConfig(), [])
    assert plan.sections[0].kind == "intro"
    assert plan.sections[-1].kind == "summary"
    assert any(section.kind == "key_point" for section in plan.sections)
    assert plan.cutaway_jobs[0].required is True


def test_heuristic_plan_is_gemma_specific_for_gemma_pdf_text() -> None:
    plan = _heuristic_plan(
        "Gemma (language model)\nGoogle DeepMind\nTechnical specifications of Gemma models",
        AppConfig(),
        [],
    )
    assert "Gemma" in plan.title
    assert plan.cutaway_jobs[0].id.startswith("gemma")
    assert any("table" in section.narration.lower() for section in plan.sections)


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
