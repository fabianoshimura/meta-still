"""The whole pipeline, on a real temp tree, with no video decoded."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from meta_still.mapper.application.scan_folder import ScanFolder
from meta_still.mapper.infrastructure.os_filesystem import OsFileSystem
from meta_still.orchestrator.application.ingest_folder import IngestFolder, IngestRequest
from meta_still.stills.application.generate_stills import GenerateStills

PNG_HEADER = b"\x89PNG\r\n\x1a\n"


@dataclass
class FakeFrameSource:
    """Writes placeholder PNGs so the resume check has something to find."""

    fail_for: set[str] = field(default_factory=set)
    opened: list[Path] = field(default_factory=list)

    @contextmanager
    def open(self, video: Path) -> Iterator["FakeFrameSource"]:
        self.opened.append(video)
        if video.name in self.fail_for:
            raise OSError(f"moov atom not found: {video.name}")
        yield self

    @property
    def duration_seconds(self) -> float:
        return 60.0

    def save_frame(self, timestamp_seconds: float, destination: Path) -> None:
        destination.write_bytes(PNG_HEADER)


def build_source(root: Path) -> None:
    clip_dir = root / "CAMERAS" / "2026_04_27" / "FX3_B" / "M4ROOT" / "CLIP"
    clip_dir.mkdir(parents=True)
    (clip_dir / "20260427_B3301.MP4").write_bytes(b"x" * 10)
    (clip_dir / "20260427_B3302.MP4").write_bytes(b"x" * 10)
    (clip_dir / "20260427_B3301M01.XML").write_bytes(b"<xml/>")
    # macOS junk that must never become a clip or a folder
    (clip_dir / "._20260427_B3301.MP4").write_bytes(b"junk")
    (clip_dir / ".DS_Store").write_bytes(b"junk")

    audio = root / "AUDIO"
    audio.mkdir()
    (audio / "260427_001_Tr1.WAV").write_bytes(b"x" * 10)


def run(root: Path, out: Path, frames: FakeFrameSource, **kwargs):
    pipeline = IngestFolder(
        scan=ScanFolder(filesystem=OsFileSystem()),
        stills=GenerateStills(frames=frames),
        timer=lambda: 0.0,
    )
    return pipeline.execute(IngestRequest(root=root, output_dir=out, **kwargs))


def test_mirrors_the_tree_and_gives_each_clip_its_own_folder(tmp_path: Path) -> None:
    source, out = tmp_path / "src", tmp_path / "out"
    build_source(source)

    result = run(source, out, FakeFrameSource())

    clip_out = out / "CAMERAS" / "2026_04_27" / "FX3_B" / "M4ROOT" / "CLIP"
    assert sorted(p.name for p in clip_out.iterdir()) == [
        "20260427_B3301",
        "20260427_B3302",
    ]
    assert len(list((clip_out / "20260427_B3301").glob("*.png"))) == 5
    assert len(result.done) == 2


def test_appledouble_and_non_video_files_are_never_processed(tmp_path: Path) -> None:
    source, out = tmp_path / "src", tmp_path / "out"
    build_source(source)
    frames = FakeFrameSource()

    run(source, out, frames)

    names = [p.name for p in frames.opened]
    assert names == ["20260427_B3301.MP4", "20260427_B3302.MP4"]
    assert not (out / "AUDIO").exists()


def test_the_map_is_written_and_reports_what_it_ignored(tmp_path: Path) -> None:
    source, out = tmp_path / "src", tmp_path / "out"
    build_source(source)

    result = run(source, out, FakeFrameSource())

    assert result.map_path == out / "src_map.txt"
    text = result.map_path.read_text(encoding="utf-8")
    assert "Ignored:  2 files" in text
    assert "._20260427_B3301.MP4" not in text


def test_one_bad_clip_does_not_stop_the_run(tmp_path: Path) -> None:
    source, out = tmp_path / "src", tmp_path / "out"
    build_source(source)
    frames = FakeFrameSource(fail_for={"20260427_B3301.MP4"})

    result = run(source, out, frames)

    assert len(result.failures) == 1
    assert len(result.done) == 1
    assert "moov atom not found" in result.failures[0].error


def test_second_run_skips_clips_that_already_have_thumbnails(tmp_path: Path) -> None:
    source, out = tmp_path / "src", tmp_path / "out"
    build_source(source)
    run(source, out, FakeFrameSource())

    frames = FakeFrameSource()
    result = run(source, out, frames)

    assert len(result.skipped) == 2
    assert frames.opened == []


def test_clip_named_with_a_trailing_space_still_gets_its_folder(tmp_path: Path) -> None:
    """The MultiCorder failure: `mkdir("clip ")` silently creates `clip`, and
    every later write to `clip \\...` then fails with ENOENT."""
    source, out = tmp_path / "src", tmp_path / "out"
    source.mkdir(parents=True)
    (source / "MultiCorder5 - Output 1 - 10-22-47 .mp4").write_bytes(b"x" * 10)

    result = run(source, out, FakeFrameSource())

    assert len(result.failures) == 0
    clip_dir = out / "MultiCorder5 - Output 1 - 10-22-47"
    assert clip_dir.is_dir()
    assert len(list(clip_dir.glob("*.png"))) == 5
    assert (clip_dir / "MultiCorder5 - Output 1 - 10-22-47_thumb_1.png").exists()


def test_force_redoes_everything(tmp_path: Path) -> None:
    source, out = tmp_path / "src", tmp_path / "out"
    build_source(source)
    run(source, out, FakeFrameSource())

    frames = FakeFrameSource()
    result = run(source, out, frames, force=True)

    assert len(result.done) == 2
    assert len(frames.opened) == 2
