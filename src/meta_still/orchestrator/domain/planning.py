"""Deciding where each clip's thumbnails go. Pure."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from meta_still.core.domain.naming import safe_name
from meta_still.core.domain.structure import collapse_structural


@dataclass(frozen=True)
class PlannedClip:
    parents: tuple[str, ...]
    filename: str
    destination: Path


def plan_destinations(
    videos: list[tuple[tuple[str, ...], str]], output_dir: Path
) -> list[PlannedClip]:
    """Map each video to its output folder, collapsing card plumbing.

    Collapsing can make two clips claim one folder - `CLIP/C2046.MP4` and
    `SUB/C2046.MP4` both want `FX3_C/C2046`, and the second would silently
    overwrite the first's thumbnails. So the collapsed paths are counted first,
    and any clip whose folder is contested keeps its full path instead. Only
    the colliding clips pay for it, and the result depends solely on the input,
    so a resumed run plans identically.
    """
    keys = [_key(parents, filename) for parents, filename in videos]
    contested = Counter(keys)

    planned: list[PlannedClip] = []
    for (parents, filename), key in zip(videos, keys):
        parts = parents if contested[key] > 1 else collapse_structural(parents)
        planned.append(
            PlannedClip(
                parents=parents,
                filename=filename,
                destination=output_dir.joinpath(
                    *(safe_name(part) for part in parts),
                    safe_name(Path(filename).stem),
                ),
            )
        )
    return planned


def _key(parents: tuple[str, ...], filename: str) -> tuple[str, ...]:
    collapsed = tuple(safe_name(part) for part in collapse_structural(parents))
    return collapsed + (safe_name(Path(filename).stem),)
