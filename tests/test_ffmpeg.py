from pathlib import Path

from briefing.ffmpeg import Segment, _parse_ffmpeg_duration, build_section_command


def test_build_section_command_is_ffmpeg_first() -> None:
    command = build_section_command(
        Segment(
            image_path=Path("slide.png"),
            audio_path=Path("audio.wav"),
            duration_seconds=12.3456,
            output_path=Path("out.mp4"),
        )
    )
    assert command[:2] == ["ffmpeg", "-y"]
    assert "-loop" in command
    assert "12.346" in command
    assert "scale=1920:1080,format=yuv420p" in command


def test_parse_ffmpeg_duration() -> None:
    assert _parse_ffmpeg_duration("Duration: 00:03:42.25, start: 0.000000") == 222.25
