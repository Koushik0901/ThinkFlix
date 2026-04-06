from briefing.pipeline import _allocate_section_durations


def test_allocate_section_durations_pads_to_target() -> None:
    durations = _allocate_section_durations([20.0, 30.0, 40.0], target_seconds=120, cutaway_seconds=6)
    assert round(sum(durations) + 6) == 120
    assert durations[0] > 20.0


def test_allocate_section_durations_does_not_shrink_long_audio() -> None:
    assert _allocate_section_durations([200.0], target_seconds=180, cutaway_seconds=0) == [200.0]

