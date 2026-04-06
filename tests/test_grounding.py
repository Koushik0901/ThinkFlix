from pathlib import Path

from briefing.config import AppConfig
from briefing.ingest import read_input
from briefing.planner import build_briefing_plan


def test_gemma_fallback_briefing_claims_are_source_grounded() -> None:
    source_text = read_input(Path("data/input/Gemma_(language_model).pdf"))
    config = AppConfig()
    config.llm.provider = "heuristic"

    plan = build_briefing_plan(source_text, config)
    source_lower = source_text.lower()
    briefing_lower = " ".join(
        [
            *(section.narration for section in plan.sections),
            *(section.takeaway for section in plan.sections),
            *(bullet for section in plan.sections for bullet in section.slide_bullets),
            *(section.visual_grounding_notes for section in plan.sections),
        ]
    ).lower()

    required_source_facts = [
        "google deepmind",
        "february 2024",
        "gemma 2",
        "gemma 3",
        "gemma 4",
        "codegemma",
        "paligemma",
        "shieldgemma",
        "medgemma",
        "150 million downloads",
        "70,000 variants",
        "phones, laptops, and tablets",
    ]
    for fact in required_source_facts:
        assert fact in source_lower
        assert fact in briefing_lower

    unsupported_project_meta = [
        "for this project",
        "table-aware pdf extraction",
        "generated cutaway",
        "generated-video",
        "provider wrapper",
        "planner",
        "ffmpeg",
        "tts",
    ]
    for phrase in unsupported_project_meta:
        assert phrase not in briefing_lower
