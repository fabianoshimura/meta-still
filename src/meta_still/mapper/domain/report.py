"""The result of one scan — Module A's output contract."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from meta_still.core.domain.tree import DirectoryNode


@dataclass(frozen=True)
class ExtensionStat:
    """How many files of one extension, and how much they weigh."""

    extension: str
    count: int
    total_bytes: int


@dataclass(frozen=True)
class ScanReport:
    root: str
    scanned_at: datetime
    tree: DirectoryNode
    errors: list[str] = field(default_factory=list)
    ignored_files: int = 0
    ignored_directories: int = 0
