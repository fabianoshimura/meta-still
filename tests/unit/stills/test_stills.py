"""Module C logic, exercised without decoding a single frame."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from meta_still.core.errors import UnreadableVideo
from meta_still.stills.application.generate_stills import GenerateStills, StillsRequest
from meta_still.stills.domain.naming import still_filename
from meta_still.stills.domain.sampling import evenly_spaced

VIDEO = Path(r"D:\CAMERAS\2026_04_27\FX3_B\M4ROOT\CLIP\20260427_B3301.MP4")


# --- sampling -----------------------------------------------------------


def test_five_stills_are_evenly_spaced_inside_the_clip() -> None:
    assert evenly_spaced(60.0, 5) == [10.0, 20.0, 30.0, 40.0, 50.0]


def test_never_samples_the_first_or_last_frame() -> None:
    duration = 123.45
    timestamps = evenly_spaced(duration, 5)
    assert timestamps[0] > 0
    assert timestamps[-1] < duration


def test_single_still_lands_mid_clip() -> None:
    assert evenly_spaced(10.0, 1) == [5.0]


@pytest.mark.parametrize("duration", [0.0, -1.0])
def test_unusable_duration_is_rejected(duration: float) -> None:
    with pytest.raises(UnreadableVideo):
        evenly_spaced(duration, 5)


def test_count_must_be_positive() -> None:
    with pytest.raises(ValueError):
        evenly_spaced(60.0, 0)


# --- naming -------------------------------------------------------------


def test_filename_keeps_the_clip_name() -> None:
    assert still_filename(VIDEO, 3, 5) == "20260427_B3301_thumb_3.png"


def test_index_is_padded_so_many_stills_sort_correctly() -> None:
    names = [still_filename(VIDEO, i, 12) for i in (1, 2, 10, 12)]
    assert names == [
        "20260427_B3301_thumb_01.png",
        "20260427_B3301_thumb_02.png",
        "20260427_B3301_thumb_10.png",
        "20260427_B3301_thumb_12.png",
    ]
    assert sorted(names) == names


# --- use-case, against a fake frame source ------------------------------


@dataclass
class FakeFrameSource:
    duration: float = 60.0
    fail_on_frame: int | None = None
    saved: list[tuple[float, Path]] = field(default_factory=list)
    closed: bool = False

    @contextmanager
    def open(self, video: Path) -> Iterator["FakeFrameSource"]:
        try:
            yield self
        finally:
            self.closed = True

    @property
    def duration_seconds(self) -> float:
        return self.duration

    def save_frame(self, timestamp_seconds: float, destination: Path) -> None:
        if self.fail_on_frame is not None and len(self.saved) == self.fail_on_frame:
            raise OSError("disk went away")
        self.saved.append((timestamp_seconds, destination))


def test_generates_the_requested_number_of_stills(tmp_path: Path) -> None:
    frames = FakeFrameSource(duration=60.0)
    request = StillsRequest(video=VIDEO, output_dir=tmp_path, count=5)

    result = GenerateStills(frames=frames).execute(request)

    assert len(result.stills) == 5
    assert result.duration_seconds == 60.0
    assert [t for t, _ in frames.saved] == [10.0, 20.0, 30.0, 40.0, 50.0]
    assert result.stills[0].path == tmp_path / "20260427_B3301_thumb_1.png"


def test_video_is_released_even_when_a_frame_fails(tmp_path: Path) -> None:
    """The batch-killer: a leaked decoder per bad clip exhausts file handles."""
    frames = FakeFrameSource(fail_on_frame=2)
    request = StillsRequest(video=VIDEO, output_dir=tmp_path, count=5)

    with pytest.raises(OSError):
        GenerateStills(frames=frames).execute(request)

    assert frames.closed
