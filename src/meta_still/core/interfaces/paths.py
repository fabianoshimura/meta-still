"""Path helpers shared by the composition roots."""

from __future__ import annotations

from pathlib import Path


def label_for(root: Path) -> str:
    """A name for the thing being scanned, for naming its artifacts.

    Falls back to the drive letter, because `D:\\` has no final component.
    """
    return root.name or root.drive.rstrip(":\\/") or "volume"
