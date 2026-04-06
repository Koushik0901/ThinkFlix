from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Segment:
    image_path: Path
    audio_path: Path | None
    duration_seconds: float
    output_path: Path


def require_ffmpeg() -> None:
    _ffmpeg_binary()


def render_image_segment(segment: Segment) -> Path:
    command = build_render_image_segment_command(segment)
    _run(command)
    return segment.output_path


def build_render_image_segment_command(segment: Segment) -> list[str]:
    segment.output_path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        "ffmpeg",
        "-y",
        "-loop",
        "1",
        "-t",
        f"{segment.duration_seconds:.3f}",
        "-i",
        str(segment.image_path),
    ]
    if segment.audio_path is not None:
        command.extend(["-i", str(segment.audio_path)])
    else:
        command.extend(["-f", "lavfi", "-i", "anullsrc=channel_layout=mono:sample_rate=48000"])
    command.extend(
        [
            "-vf",
            "scale=1920:1080,format=yuv420p",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-r",
            "30",
        ]
    )
    if segment.audio_path is not None:
        command.extend(
            [
                "-af",
                "aresample=48000,apad",
                "-t",
                f"{segment.duration_seconds:.3f}",
                "-c:a",
                "aac",
                "-b:a",
                "160k",
                "-ar",
                "48000",
                "-ac",
                "1",
            ]
        )
    else:
        command.extend(
            [
                "-t",
                f"{segment.duration_seconds:.3f}",
                "-c:a",
                "aac",
                "-b:a",
                "64k",
                "-ar",
                "48000",
                "-ac",
                "1",
                "-shortest",
            ]
        )
    command.append(str(segment.output_path))
    return command


def concat_segments(segment_paths: list[Path], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    concat_file = output_path.parent / "concat.txt"
    concat_file.write_text(
        "".join(f"file '{path.resolve().as_posix()}'\n" for path in segment_paths),
        encoding="utf-8",
    )
    command = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:v",
        "libx264",
        "-c:a",
        "aac",
        "-ar",
        "48000",
        "-ac",
        "1",
        "-pix_fmt",
        "yuv420p",
        str(output_path),
    ]
    _run(command)
    return output_path


def probe_duration(path: Path) -> float:
    ffprobe = _ffprobe_binary()
    if ffprobe is None:
        return _probe_duration_with_ffmpeg(path)
    command = [
        ffprobe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(path),
    ]
    result = _run(command)
    return float(json.loads(result.stdout)["format"]["duration"])


def build_section_command(segment: Segment) -> list[str]:
    return build_render_image_segment_command(segment)[:-1]


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    if command and command[0] == "ffmpeg":
        command = [_ffmpeg_binary(), *command[1:]]
    return subprocess.run(command, text=True, capture_output=True, check=True)


def _ffmpeg_binary() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Missing FFmpeg. Install FFmpeg on PATH or install the imageio-ffmpeg package."
        ) from exc


def _ffprobe_binary() -> str | None:
    return shutil.which("ffprobe")


def _probe_duration_with_ffmpeg(path: Path) -> float:
    result = subprocess.run(
        [_ffmpeg_binary(), "-hide_banner", "-i", str(path)],
        text=True,
        capture_output=True,
        check=False,
    )
    return _parse_ffmpeg_duration(result.stderr)


def _parse_ffmpeg_duration(stderr: str) -> float:
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", stderr)
    if not match:
        raise RuntimeError("Could not parse duration from FFmpeg output.")
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
