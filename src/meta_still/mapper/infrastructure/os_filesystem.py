"""Real filesystem adapter for FileSystemPort."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from meta_still.core.domain.ignore import is_ignored_directory, is_ignored_file
from meta_still.core.domain.tree import DirectoryNode, FileNode, TreeScan


@dataclass
class _Tally:
    errors: list[str] = field(default_factory=list)
    ignored_files: int = 0
    ignored_directories: int = 0


class OsFileSystem:
    """Walks the real filesystem with os.scandir.

    Symlinks and junctions are recorded but never followed: external drives
    contain loops often enough that following them is a hang, not a feature.
    """

    def build_tree(self, root: Path) -> TreeScan:
        tally = _Tally()
        tree = self._scan(root, name=str(root), tally=tally)
        return TreeScan(
            tree=tree,
            errors=tally.errors,
            ignored_files=tally.ignored_files,
            ignored_directories=tally.ignored_directories,
        )

    def _scan(self, path: Path, name: str, tally: _Tally) -> DirectoryNode:
        node = DirectoryNode(name=name)
        try:
            with os.scandir(path) as scan:
                entries = sorted(scan, key=lambda e: e.name.lower())
        except OSError as exc:
            tally.errors.append(f"{path}: {exc.strerror or exc}")
            return node

        for entry in entries:
            try:
                if entry.is_dir(follow_symlinks=False):
                    if is_ignored_directory(entry.name):
                        tally.ignored_directories += 1
                        continue
                    node.directories.append(self._scan(Path(entry.path), entry.name, tally))
                elif entry.is_file(follow_symlinks=False):
                    if is_ignored_file(entry.name):
                        tally.ignored_files += 1
                        continue
                    size = entry.stat(follow_symlinks=False).st_size
                    node.files.append(FileNode(name=entry.name, size_bytes=size))
            except OSError as exc:
                tally.errors.append(f"{entry.path}: {exc.strerror or exc}")

        return node
