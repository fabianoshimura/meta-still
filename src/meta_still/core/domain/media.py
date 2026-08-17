"""What counts as a video file."""

from __future__ import annotations

from pathlib import PurePath

VIDEO_EXTENSIONS = frozenset(
    {".mp4", ".mov", ".mxf", ".mts", ".m4v", ".avi", ".mkv", ".braw", ".r3d"}
)


def is_video(name: str) -> bool:
    return PurePath(name).suffix.lower() in VIDEO_EXTENSIONS
