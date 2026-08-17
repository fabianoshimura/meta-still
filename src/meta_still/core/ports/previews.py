"""Port for making a small version of an image."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol


class PreviewMakerPort(Protocol):
    def make(self, source: Path, destination: Path) -> None:
        """Write a small preview of `source` at `destination`.

        Kept behind a port so building a sheet can be tested without Pillow
        touching a single pixel.
        """
        ...
