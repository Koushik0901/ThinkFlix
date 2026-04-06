import os

import pytest

from briefing.config import AppConfig
from briefing.models import CutawayJob
from briefing.video import _run_api_cutaway, validate_video_runtime


def test_api_cutaway_requires_fal_key(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("FAL_KEY", raising=False)
    config = AppConfig()
    config.video.mode = "api"
    job = CutawayJob(id="test_cutaway", prompt="abstract model family cutaway", duration_seconds=6)

    with pytest.raises(RuntimeError, match="FAL_KEY"):
        _run_api_cutaway(job, 1, tmp_path, config)


def test_api_cutaway_does_not_write_manifest_without_key(tmp_path, monkeypatch) -> None:
    monkeypatch.delenv("FAL_KEY", raising=False)
    config = AppConfig()
    job = CutawayJob(id="test_cutaway", prompt="abstract model family cutaway", duration_seconds=6)

    with pytest.raises(RuntimeError):
        _run_api_cutaway(job, 1, tmp_path, config)
    assert not os.listdir(tmp_path)


def test_validate_video_runtime_fails_fast_without_fal_key(monkeypatch) -> None:
    monkeypatch.delenv("FAL_KEY", raising=False)
    config = AppConfig()
    config.video.mode = "api"
    with pytest.raises(RuntimeError, match="FAL_KEY"):
        validate_video_runtime(config)
