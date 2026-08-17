"""Contact sheet building and rendering, without Pillow touching a pixel."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from meta_still.contactsheet.application.build_sheet import BuildContactSheet, SheetRequest
from meta_still.contactsheet.domain.model import ClipEntry, Sheet, Still
from meta_still.contactsheet.domain.renderer import render_sheet
from meta_still.contactsheet.infrastructure.output_scanner import scan_output

WHEN = datetime(2026, 8, 17, 14, 30)


@dataclass
class FakePreviewMaker:
    made: list[tuple[Path, Path]] = field(default_factory=list)
    fail_for: set[str] = field(default_factory=set)

    def make(self, source: Path, destination: Path) -> None:
        if source.name in self.fail_for:
            raise OSError("truncated PNG")
        self.made.append((source, destination))


def build_output(root: Path) -> None:
    clip = root / "CAMERAS" / "2026_04_27" / "FX3_B" / "20260427_B3301"
    clip.mkdir(parents=True)
    for index in (1, 2):
        (clip / f"20260427_B3301_thumb_{index}.png").write_bytes(b"\x89PNG")
    # Spaces and an accent, but no trailing space: safe_name() already removed
    # that upstream, and Windows cannot create such a folder anyway.
    other = root / "Episodio" / "MultiCorder1 - Câmera 4"
    other.mkdir(parents=True)
    (other / "shot_thumb_1.png").write_bytes(b"\x89PNG")
    (root / "ABIMED_map.txt").write_text("not a clip", encoding="utf-8")


# --- scanning -----------------------------------------------------------


def test_finds_every_folder_that_holds_pngs(tmp_path: Path) -> None:
    build_output(tmp_path)

    clips = scan_output(tmp_path)

    assert [c.name for c in clips] == ["20260427_B3301", "MultiCorder1 - Câmera 4"]
    assert clips[0].group == ("CAMERAS", "2026_04_27", "FX3_B")
    assert len(clips[0].stills) == 2


def test_folders_without_pngs_are_not_clips(tmp_path: Path) -> None:
    (tmp_path / "empty").mkdir()

    assert scan_output(tmp_path) == []


def test_the_previews_folder_is_not_rescanned_as_source(tmp_path: Path) -> None:
    previews = tmp_path / "_previews" / "clip"
    previews.mkdir(parents=True)
    (previews / "x.png").write_bytes(b"\x89PNG")

    assert scan_output(tmp_path) == []


# --- building -----------------------------------------------------------


def test_previews_are_requested_for_every_still(tmp_path: Path) -> None:
    build_output(tmp_path)
    previews = FakePreviewMaker()

    sheet = BuildContactSheet(scanner=scan_output, previews=previews).execute(
        SheetRequest(output_dir=tmp_path, title="ABIMED")
    )

    assert len(previews.made) == 3
    assert sheet.total_stills == 3
    assert sheet.clips[0].stills[0].preview.startswith("_previews/")


def test_a_failed_preview_falls_back_to_the_full_png(tmp_path: Path) -> None:
    """One unreadable still must not cost you the whole sheet."""
    build_output(tmp_path)
    previews = FakePreviewMaker(fail_for={"20260427_B3301_thumb_1.png"})

    sheet = BuildContactSheet(scanner=scan_output, previews=previews).execute(
        SheetRequest(output_dir=tmp_path, title="ABIMED")
    )

    first = sheet.clips[0].stills[0]
    assert first.preview == first.href
    assert sheet.total_stills == 3


def test_hrefs_are_percent_encoded(tmp_path: Path) -> None:
    """These names are full of spaces and accents; a raw href would break."""
    build_output(tmp_path)

    sheet = BuildContactSheet(scanner=scan_output, previews=FakePreviewMaker()).execute(
        SheetRequest(output_dir=tmp_path, title="ABIMED", with_previews=False)
    )

    href = sheet.clips[1].stills[0].href
    assert " " not in href
    assert "%20" in href


# --- rendering ----------------------------------------------------------


def sample_sheet() -> Sheet:
    return Sheet(
        title="ABIMED",
        generated_at=WHEN,
        clips=[
            ClipEntry(
                name="20260427_B3301",
                group=("CAMERAS", "2026_04_27", "FX3_B"),
                stills=[Still(href="a.png", preview="p.jpg", label="thumb 1")],
            )
        ],
    )


def test_page_is_self_contained() -> None:
    html = render_sheet(sample_sheet())

    assert "<style>" in html and "<script>" in html
    assert "http://" not in html and "https://" not in html


def test_clips_are_grouped_by_folder() -> None:
    html = render_sheet(sample_sheet())

    assert "CAMERAS / 2026_04_27 / FX3_B" in html
    assert "20260427_B3301" in html


def test_images_are_lazy_so_hundreds_of_stills_stay_usable() -> None:
    assert 'loading="lazy"' in render_sheet(sample_sheet())


def test_clip_names_are_escaped() -> None:
    sheet = Sheet(
        title="x",
        generated_at=WHEN,
        clips=[ClipEntry(name='<img src=x onerror="alert(1)">', group=())],
    )

    html = render_sheet(sheet)

    assert "<img src=x onerror" not in html
    assert "&lt;img" in html


def test_an_empty_output_folder_still_renders() -> None:
    html = render_sheet(Sheet(title="ABIMED", generated_at=WHEN))

    assert "No thumbnails found" in html
