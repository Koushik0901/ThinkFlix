from pathlib import Path

from briefing.ffmpeg import Segment, _parse_ffmpeg_duration, build_render_image_segment_command, build_section_command


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
    assert "aresample=48000,apad" in command
    assert "-ar" in command
    assert "48000" in command


def test_image_segment_without_audio_adds_silent_audio_stream() -> None:
    command = build_render_image_segment_command(
        Segment(
            image_path=Path("slide.png"),
            audio_path=None,
            duration_seconds=6,
            output_path=Path("out.mp4"),
        )
    )

    assert "anullsrc=channel_layout=mono:sample_rate=48000" in command
    assert "-an" not in command
    assert "-shortest" in command


def test_parse_ffmpeg_duration() -> None:
    assert _parse_ffmpeg_duration("Duration: 00:03:42.25, start: 0.000000") == 222.25
