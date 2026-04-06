from __future__ import annotations

import json
from pathlib import Path

from briefing.audio import synthesize_narration
from briefing.config import AppConfig
from briefing.ffmpeg import Segment, concat_segments, probe_duration, render_image_segment
from briefing.ingest import chunk_text, read_input
from briefing.models import BriefingPlan
from briefing.planner import build_briefing_plan
from briefing.slides import render_section_slide
from briefing.video import prepare_cutaways, validate_video_runtime


def run_pipeline(input_path: Path, out_dir: Path, config: AppConfig) -> BriefingPlan:
    out_dir.mkdir(parents=True, exist_ok=True)
    source_text = read_input(input_path)
    _write_source_index(input_path, source_text, out_dir / "source_index.json")

    plan = build_briefing_plan(source_text, config)
    (out_dir / "briefing_plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    validate_video_runtime(config)

    slides_dir = out_dir / "slides"
    audio_dir = out_dir / "audio"
    segments_dir = out_dir / "segments"
    section_assets: list[tuple[Path, Path, float]] = []

    for index, section in enumerate(plan.sections, start=1):
        slide_path = render_section_slide(section, index, slides_dir / f"section_{index:02d}.png", config.slides)
        audio_path = audio_dir / f"section_{index:02d}.wav"
        duration = synthesize_narration(section.narration, audio_path, config.audio)
        section_assets.append((slide_path, audio_path, duration))

    cutaway_duration = (
        sum(job.duration_seconds for job in plan.cutaway_jobs[: config.video.required_cutaways])
        if config.video.mode != "skip"
        else 0.0
    )
    section_durations = _allocate_section_durations(
        [duration for _, _, duration in section_assets],
        target_seconds=plan.target_duration_seconds,
        cutaway_seconds=cutaway_duration,
    )

    segment_paths: list[Path] = []
    for index, (slide_path, audio_path, _) in enumerate(section_assets, start=1):
        segment_path = segments_dir / f"section_{index:02d}.mp4"
        render_image_segment(
            Segment(
                image_path=slide_path,
                audio_path=audio_path,
                duration_seconds=section_durations[index - 1],
                output_path=segment_path,
            )
        )
        segment_paths.append(segment_path)
        if index == 3:
            segment_paths.extend(
                prepare_cutaways(
                    plan.cutaway_jobs[: config.video.required_cutaways],
                    out_dir / "video_clips",
                    config,
                )
            )

    final_path = concat_segments(segment_paths, out_dir / "briefing.mp4")
    _write_cost_report(out_dir / "cost_report.md", plan, final_path)
    (out_dir / "briefing_plan.json").write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    return plan


def _allocate_section_durations(
    audio_durations: list[float], target_seconds: int, cutaway_seconds: float
) -> list[float]:
    base_total = sum(audio_durations) + cutaway_seconds
    if not audio_durations or base_total >= target_seconds:
        return audio_durations
    padding = (target_seconds - base_total) / len(audio_durations)
    return [duration + padding for duration in audio_durations]


def _write_source_index(input_path: Path, source_text: str, output_path: Path) -> None:
    source_index = {
        "input": str(input_path),
        "chunks": [{"id": idx, "text": chunk} for idx, chunk in enumerate(chunk_text(source_text), start=1)],
    }
    output_path.write_text(json.dumps(source_index, indent=2), encoding="utf-8")


def _write_cost_report(path: Path, plan: BriefingPlan, final_path: Path) -> None:
    try:
        duration = probe_duration(final_path)
    except Exception:  # noqa: BLE001
        duration = 0.0
    lines = [
        "# Cost Report",
        "",
        f"Final output: `{final_path}`",
        f"Final duration: {duration:.1f} seconds" if duration else "Final duration: not probed",
        "",
        "## Fixed compute cost",
        plan.cost_notes.fixed_compute,
        "",
        "## Bursty high-cost step",
        plan.cost_notes.bursty_compute,
        "",
        "## API justification",
        (
            "The target local machine is an RTX 4060 with 8GB VRAM. Wan2.2 video generation is "
            "the only stage routed to an API because the local GPU is below the practical memory "
            "target for this model class. All non-video stages remain local."
        ),
        "",
        "## Marginal cost",
        plan.cost_notes.marginal_cost,
        "",
        "Most stages run cheaply on commodity hardware. The only bursty high-cost step is optional "
        "short video generation, which is isolated and capped.",
        "",
        "## Cutaway status",
    ]
    for job in plan.cutaway_jobs:
        lines.append(f"- {job.id}: {job.status} ({job.output_path or 'no output'})")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
