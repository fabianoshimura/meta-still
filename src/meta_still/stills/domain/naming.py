"""Naming the generated stills. Pure."""

from __future__ import annotations

from pathlib import Path

from meta_still.core.domain.naming import safe_name


def still_filename(video: Path, index: int, total: int, extension: str = ".png") -> str:
    """`C0021.MP4` still 3 of 5 -> `C0021_thumb_3.png`.

    The index is zero-padded to the width of `total`, so that 12 stills sort as
    01..12 rather than 1, 10, 11, 12, 2. With the default 5 there is nothing to
    pad and the name stays as short as it looks.

    The stem is sanitised with the same rule as the clip's folder, so the two
    agree - `MultiCorder5 ... 10-22-47 .mp4` yields folder `...10-22-47` and
    files `...10-22-47_thumb_1.png`, not one with a stray space and one without.
    """
    width = len(str(total))
    suffix = extension if extension.startswith(".") else f".{extension}"
    return f"{safe_name(video.stem)}_thumb_{index:0{width}d}{suffix}"
