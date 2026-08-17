"""The Module A use-case: scan a folder, produce a report.

Knows nothing about the filesystem, the clock or the CLI — all three arrive as
dependencies. This is what makes the module runnable from a CLI today and from
a queue worker later, unchanged.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from meta_still.core.ports.filesystem import FileSystemPort
from meta_still.mapper.domain.report import ScanReport


@dataclass
class ScanFolder:
    filesystem: FileSystemPort
    clock: Callable[[], datetime] = datetime.now

    def execute(self, root: Path) -> ScanReport:
        scan = self.filesystem.build_tree(root)
        return ScanReport(
            root=str(root),
            scanned_at=self.clock(),
            tree=scan.tree,
            errors=scan.errors,
            ignored_files=scan.ignored_files,
            ignored_directories=scan.ignored_directories,
        )
