"""Cancelling a run, and the progress numbers a bar is drawn from."""

from __future__ import annotations

from pathlib import Path

from meta_still.mapper.application.scan_folder import ScanFolder
from meta_still.mapper.infrastructure.os_filesystem import OsFileSystem
from meta_still.orchestrator.application.ingest_folder import IngestFolder, IngestRequest
from meta_still.stills.application.generate_stills import GenerateStills
from tests.unit.orchestrator.test_ingest import FakeFrameSource


def build_source(root: Path, clips: int) -> None:
    root.mkdir(parents=True)
    for index in range(clips):
        (root / f"C{index:04d}.MP4").write_bytes(b"x" * 10)


def pipeline(frames, **kwargs) -> IngestFolder:
    return IngestFolder(
        scan=ScanFolder(filesystem=OsFileSystem()),
        stills=GenerateStills(frames=frames),
        timer=lambda: 0.0,
        **kwargs,
    )


def test_steps_are_reported_for_every_clip(tmp_path: Path) -> None:
    source, out = tmp_path / "src", tmp_path / "out"
    build_source(source, 3)
    steps: list[tuple[int, int]] = []

    pipeline(FakeFrameSource(), on_step=lambda done, total: steps.append((done, total))).execute(
        IngestRequest(root=source, output_dir=out)
    )

    assert steps == [(1, 3), (2, 3), (3, 3)]


def test_cancelling_stops_the_run_and_keeps_what_was_done(tmp_path: Path) -> None:
    source, out = tmp_path / "src", tmp_path / "out"
    build_source(source, 5)
    frames = FakeFrameSource()
    done = 0

    def stop_after_two() -> bool:
        return done >= 2

    def count(_done: int, _total: int) -> None:
        nonlocal done
        done = _done

    result = pipeline(frames, on_step=count, should_stop=stop_after_two).execute(
        IngestRequest(root=source, output_dir=out)
    )

    assert result.stopped
    assert result.total_clips == 5
    assert len(result.done) == 2
    assert len(frames.opened) == 2


def test_a_cancelled_clip_is_never_left_half_written(tmp_path: Path) -> None:
    """The stop is checked between clips, so any folder that exists is complete."""
    source, out = tmp_path / "src", tmp_path / "out"
    build_source(source, 4)
    done = 0

    result = pipeline(
        FakeFrameSource(),
        on_step=lambda d, _t: globals().__setitem__("_ignored", d),
        should_stop=lambda: done >= 1,
    ).execute(IngestRequest(root=source, output_dir=out))

    for outcome in result.done:
        assert len(list(outcome.destination.glob("*.png"))) == 5
