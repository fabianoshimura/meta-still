"""Renderer and statistics tests — an in-memory tree, no drive attached.

This is the payoff of FileSystemPort: the interesting logic is exercised
without any I/O at all.
"""

from __future__ import annotations

from datetime import datetime

from meta_still.core.domain.tree import DirectoryNode, FileNode
from meta_still.mapper.domain.renderer import human_bytes, render_report
from meta_still.mapper.domain.report import ScanReport
from meta_still.mapper.domain.statistics import collect_extensions


def build_tree() -> DirectoryNode:
    clip = DirectoryNode(
        name="Clip",
        files=[
            FileNode("C0001.MXF", 4_000_000_000),
            FileNode("C0001M01.XML", 12_000),
        ],
    )
    return DirectoryNode(
        name="ROOT",
        directories=[DirectoryNode(name="FX6_A", directories=[clip])],
        files=[FileNode("readme.txt", 100)],
    )


def test_totals_aggregate_recursively() -> None:
    tree = build_tree()
    assert tree.total_files == 3
    assert tree.total_directories == 2
    assert tree.total_bytes == 4_000_012_100


def test_extensions_are_grouped_and_sorted_by_weight() -> None:
    stats = collect_extensions(build_tree())
    assert [s.extension for s in stats] == [".MXF", ".XML", ".TXT"]
    assert stats[0].count == 1
    assert stats[0].total_bytes == 4_000_000_000


def test_report_contains_tree_and_extension_table() -> None:
    report = ScanReport(
        root=r"D:\\",
        scanned_at=datetime(2026, 8, 17, 14, 3, 11),
        tree=build_tree(),
        errors=[],
    )
    text = render_report(report)

    assert "FX6_A/" in text
    assert "C0001.MXF" in text
    assert "EXTENSIONS" in text
    assert "2026-08-17 14:03:11" in text


def test_unreadable_paths_are_reported_not_raised() -> None:
    report = ScanReport(
        root=r"D:\\",
        scanned_at=datetime(2026, 8, 17),
        tree=build_tree(),
        errors=[r"D:\System Volume Information: Access is denied"],
    )
    assert "UNREADABLE PATHS (1)" in render_report(report)


def test_human_bytes_uses_decimal_units() -> None:
    assert human_bytes(0) == "0 B"
    assert human_bytes(999) == "999 B"
    assert human_bytes(1_000) == "1.0 KB"
    assert human_bytes(4_000_000_000) == "4.0 GB"
