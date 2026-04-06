from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np
import soundfile as sf

from briefing.config import AudioSettings


def synthesize_narration(text: str, output_path: Path, settings: AudioSettings) -> float:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        return _synthesize_with_kokoro(text, output_path, settings)
    except Exception:
        return _synthesize_placeholder(text, output_path, settings)


def wav_duration_seconds(path: Path) -> float:
    with wave.open(str(path), "rb") as handle:
        return handle.getnframes() / float(handle.getframerate())


def _synthesize_with_kokoro(text: str, output_path: Path, settings: AudioSettings) -> float:
    from kokoro import KPipeline

    pipeline = KPipeline(lang_code=settings.language_code)
    chunks: list[np.ndarray] = []
    for _, _, audio in pipeline(text, voice=settings.voice):
        chunks.append(np.asarray(audio, dtype=np.float32))
    if not chunks:
        raise RuntimeError("Kokoro produced no audio")
    audio = np.concatenate(chunks)
    sf.write(output_path, audio, settings.sample_rate)
    return wav_duration_seconds(output_path)


def _synthesize_placeholder(text: str, output_path: Path, settings: AudioSettings) -> float:
    words = max(1, len(text.split()))
    duration = max(2.5, words / settings.fallback_words_per_minute * 60.0)
    sample_rate = settings.sample_rate
    total_samples = int(duration * sample_rate)
    with wave.open(str(output_path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        for sample in range(total_samples):
            envelope = 0.25 if sample % (sample_rate // 2) < sample_rate // 4 else 0.08
            value = int(32767 * envelope * math.sin(2 * math.pi * 220 * sample / sample_rate))
            handle.writeframesraw(value.to_bytes(2, byteorder="little", signed=True))
    return wav_duration_seconds(output_path)

