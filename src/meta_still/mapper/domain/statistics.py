"""Aggregations over a scanned tree. Pure functions, trivially testable."""

from __future__ import annotations

from pathlib import PurePath

from meta_still.core.domain.tree import DirectoryNode
from meta_still.mapper.domain.report import ExtensionStat

NO_EXTENSION = "(none)"


def collect_extensions(root: DirectoryNode) -> list[ExtensionStat]:
    """Count files and bytes per extension, heaviest first.

    This is the table we read to decide which extensions matter — which
    classification and camera rules get built from, in the next iteration.
    """
    totals: dict[str, list[int]] = {}

    def walk(node: DirectoryNode) -> None:
        for file in node.files:
            extension = PurePath(file.name).suffix.upper() or NO_EXTENSION
            slot = totals.setdefault(extension, [0, 0])
            slot[0] += 1
            slot[1] += file.size_bytes
        for directory in node.directories:
            walk(directory)

    walk(root)

    return sorted(
        (ExtensionStat(ext, count, size) for ext, (count, size) in totals.items()),
        key=lambda stat: (-stat.total_bytes, stat.extension),
    )
