import wave

from briefing.audio import _synthesize_placeholder
from briefing.config import AudioSettings


def test_placeholder_audio_duration_scales_with_words(tmp_path) -> None:
    path = tmp_path / "audio.wav"
    duration = _synthesize_placeholder("word " * 120, path, AudioSettings())
    with wave.open(str(path), "rb") as handle:
        assert handle.getframerate() == 24000
    assert duration > 20

