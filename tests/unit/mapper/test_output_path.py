"""Resolving whatever the operator typed into a writable file path."""

from __future__ import annotations

from pathlib import Path

from meta_still.mapper.interfaces.cli import resolve_output

SCANNED = Path(r"D:\ABIMED\MEDIAS\2026_04_27\ABIMED_PGM007_20260427")


def test_existing_folder_gets_a_filename_named_after_the_scan(tmp_path: Path) -> None:
    resolved = resolve_output(str(tmp_path), SCANNED)
    assert resolved == tmp_path / "ABIMED_PGM007_20260427_map.txt"


def test_trailing_separator_is_treated_as_a_folder() -> None:
    resolved = resolve_output(r"C:\reports\\", SCANNED)
    assert resolved.name == "ABIMED_PGM007_20260427_map.txt"


def test_drive_root_falls_back_to_the_drive_letter(tmp_path: Path) -> None:
    resolved = resolve_output(str(tmp_path), Path("D:\\"))
    assert resolved.name == "D_map.txt"


def test_explicit_file_is_left_alone() -> None:
    assert resolve_output(r"C:\reports\day03.txt", SCANNED) == Path(r"C:\reports\day03.txt")


def test_extensionless_file_gets_txt() -> None:
    assert resolve_output(r"C:\reports\day03", SCANNED) == Path(r"C:\reports\day03.txt")
