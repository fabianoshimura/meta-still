"""What a contact sheet is made of.

Paths are stored as URLs relative to the sheet's own location, so the renderer
is pure string work with no filesystem knowledge - and therefore testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class Still:
    href: str  # relative URL to the full-size PNG
    preview: str  # relative URL to the small image shown in the grid
    label: str


@dataclass(frozen=True)
class ClipEntry:
    name: str
    group: tuple[str, ...]  # folder path leading to the clip
    stills: list[Still] = field(default_factory=list)

    @property
    def group_label(self) -> str:
        return " / ".join(self.group) if self.group else "(root)"


@dataclass(frozen=True)
class Sheet:
    title: str
    generated_at: datetime
    clips: list[ClipEntry] = field(default_factory=list)

    @property
    def total_stills(self) -> int:
        return sum(len(clip.stills) for clip in self.clips)

    def grouped(self) -> list[tuple[str, list[ClipEntry]]]:
        """Clips bucketed by folder, in the order they were discovered."""
        groups: dict[str, list[ClipEntry]] = {}
        for clip in self.clips:
            groups.setdefault(clip.group_label, []).append(clip)
        return list(groups.items())
