"""Find the clip folders inside a completed output folder."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

PREVIEWS_DIR = "_previews"


@dataclass(frozen=True)
class ScannedClip:
    group: tuple[str, ...]
    name: str
    stills: list[Path] = field(default_factory=list)


def scan_output(output_dir: Path) -> list[ScannedClip]:
    """Every folder holding PNGs is a clip, named after itself.

    Reading the output folder rather than a run's in-memory result means the
    sheet can be rebuilt at any time - after tweaking the layout, or for a run
    finished last week - without decoding a frame.
    """
    clips: list[ScannedClip] = []

    for directory in sorted(_walk(output_dir)):
        stills = sorted(directory.glob("*.png"))
        if not stills:
            continue
        relative = directory.relative_to(output_dir)
        clips.append(
            ScannedClip(
                group=relative.parts[:-1],
                name=directory.name,
                stills=stills,
            )
        )
    return clips


def _walk(root: Path):
    for entry in root.iterdir():
        if not entry.is_dir():
            continue
        if entry.name == PREVIEWS_DIR:  # our own output is not source material
            continue
        yield entry
        yield from _walk(entry)
