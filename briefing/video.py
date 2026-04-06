from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import httpx

from briefing.config import AppConfig
from briefing.ffmpeg import Segment, render_image_segment
from briefing.models import CutawayJob
from briefing.slides import render_cutaway_placeholder


def validate_video_runtime(config: AppConfig) -> None:
    if config.video.mode == "api" and not os.getenv("FAL_KEY"):
        raise RuntimeError(
            "FAL_KEY is required for --video-mode api. Set FAL_KEY or rerun with "
            "--no-video-model for the local placeholder fallback."
        )


def prepare_cutaways(jobs: list[CutawayJob], out_dir: Path, config: AppConfig) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    rendered: list[Path] = []
    for index, job in enumerate(jobs, start=1):
        if config.video.mode == "skip":
            job.status = "skipped"
            continue
        if config.video.mode == "wan":
            rendered.append(_run_wan_or_manifest(job, index, out_dir, config))
        elif config.video.mode == "api":
            rendered.append(_run_api_cutaway(job, index, out_dir, config))
        else:
            rendered.append(_render_placeholder_cutaway(job, index, out_dir, config))
    return rendered


def _render_placeholder_cutaway(job: CutawayJob, index: int, out_dir: Path, config: AppConfig) -> Path:
    image_path = out_dir / f"cutaway_{index:02d}.png"
    video_path = out_dir / f"cutaway_{index:02d}.mp4"
    render_cutaway_placeholder(job.prompt, image_path, config.slides)
    render_image_segment(
        Segment(
            image_path=image_path,
            audio_path=None,
            duration_seconds=job.duration_seconds,
            output_path=video_path,
        )
    )
    job.status = "placeholder"
    job.output_path = str(video_path)
    return video_path


def _run_wan_or_manifest(job: CutawayJob, index: int, out_dir: Path, config: AppConfig) -> Path:
    output_path = (out_dir / f"cutaway_{index:02d}.mp4").resolve()
    manifest_path = out_dir / f"wan_job_{index:02d}.json"
    manifest = {
        "job_id": job.id,
        "prompt": job.prompt,
        "expected_output": str(output_path),
        "command": _wan_command(job, output_path, config),
        "note": (
            "Run from the Wan2.2 repository on a 24GB-plus GPU. If it fails, rerun with "
            "--video-mode placeholder to keep the briefing shippable."
        ),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    repo = Path(config.video.wan_repo_path)
    if not repo.exists():
        raise RuntimeError(f"Wan2.2 repo path does not exist: {repo}. Wrote {manifest_path}.")
    subprocess.run(manifest["command"], cwd=repo, check=True)
    if not output_path.exists():
        raise RuntimeError(f"Wan2.2 command completed but did not create {output_path}")
    job.status = "generated"
    job.output_path = str(output_path)
    return output_path


def _wan_command(job: CutawayJob, output_path: Path, config: AppConfig) -> list[str]:
    ckpt_dir = Path(config.video.wan_ckpt_dir).resolve()
    return [
        "python",
        "generate.py",
        "--task",
        config.video.wan_task,
        "--size",
        config.video.wan_size,
        "--ckpt_dir",
        str(ckpt_dir),
        "--offload_model",
        "True",
        "--convert_model_dtype",
        "--t5_cpu",
        "--prompt",
        job.prompt,
        "--save_file",
        str(output_path),
    ]


def _run_api_cutaway(job: CutawayJob, index: int, out_dir: Path, config: AppConfig) -> Path:
    if config.video.api_provider != "fal":
        raise RuntimeError(f"Unsupported video API provider: {config.video.api_provider}")
    validate_video_runtime(config)

    output_path = (out_dir / f"cutaway_{index:02d}.mp4").resolve()
    manifest_path = out_dir / f"api_job_{index:02d}.json"
    manifest_path.write_text(
        json.dumps(
            {
                "job_id": job.id,
                "provider": config.video.api_provider,
                "model": config.video.api_model,
                "prompt": job.prompt,
                "expected_output": str(output_path),
                "justification": (
                    "Wan2.2 video generation does not fit the target RTX 4060 8GB local runtime. "
                    "Only this capped cutaway step is routed to an API; PDF extraction, planning, "
                    "TTS, slides, and FFmpeg assembly remain local."
                ),
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    video_url = _submit_fal_wan_job(job, config)
    with httpx.stream("GET", video_url, timeout=config.video.api_client_timeout_seconds) as response:
        response.raise_for_status()
        with output_path.open("wb") as handle:
            for chunk in response.iter_bytes():
                handle.write(chunk)
    job.status = "generated"
    job.output_path = str(output_path)
    return output_path


def _submit_fal_wan_job(job: CutawayJob, config: AppConfig) -> str:
    import fal_client

    result = fal_client.subscribe(
        config.video.api_model,
        arguments={
            "prompt": job.prompt,
            "resolution": config.video.api_resolution,
            "aspect_ratio": config.video.api_aspect_ratio,
            "num_frames": config.video.api_num_frames,
            "frames_per_second": config.video.api_frames_per_second,
            "num_inference_steps": config.video.api_num_inference_steps,
            "enable_safety_checker": True,
            "enable_output_safety_checker": True,
            "enable_prompt_expansion": False,
            "acceleration": "regular",
        },
        with_logs=True,
    )
    video = result.get("video") if isinstance(result, dict) else None
    url = video.get("url") if isinstance(video, dict) else None
    if not url:
        raise RuntimeError(f"fal.ai response did not include a video URL: {result}")
    return url
