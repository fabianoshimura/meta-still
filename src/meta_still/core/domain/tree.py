"""Filesystem tree entities.

Pure domain: no I/O, no framework, no knowledge of how the tree was obtained.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cached_property


@dataclass(frozen=True)
class FileNode:
    """A single file discovered during a scan."""

    name: str
    size_bytes: int


@dataclass
class DirectoryNode:
    """A folder and everything below it.

    The aggregate properties are cached, so read them only after the tree is
    fully built. Building is bottom-up, so this is naturally the case.
    """

    name: str
    directories: list[DirectoryNode] = field(default_factory=list)
    files: list[FileNode] = field(default_factory=list)

    @cached_property
    def total_files(self) -> int:
        return len(self.files) + sum(d.total_files for d in self.directories)

    @cached_property
    def total_directories(self) -> int:
        return len(self.directories) + sum(d.total_directories for d in self.directories)

    @cached_property
    def total_bytes(self) -> int:
        own = sum(f.size_bytes for f in self.files)
        return own + sum(d.total_bytes for d in self.directories)


@dataclass(frozen=True)
class TreeScan:
    """A built tree, plus what the walk could not or would not read."""

    tree: DirectoryNode
    errors: list[str] = field(default_factory=list)
    ignored_files: int = 0
    ignored_directories: int = 0


def iter_files(
    node: DirectoryNode, _parents: tuple[str, ...] = ()
) -> Iterator[tuple[tuple[str, ...], FileNode]]:
    """Every file below `node`, with the folder names leading to it.

    The root's own name is not included, so the parts can be joined onto either
    the source root or the output root - which is exactly what mirroring the
    structure requires.
    """
    for file in node.files:
        yield _parents, file
    for directory in node.directories:
        yield from iter_files(directory, _parents + (directory.name,))
