"""Pillow adapter for PreviewMakerPort.

Why previews exist at all: a 160-clip run produces ~800 stills at 1920px, a few
megabytes each. Pointing the page straight at those means the browser decodes
multi-megabyte images while you scroll, and the sheet crawls. A 480px JPEG is
~30 KB, so the whole grid loads instantly - and each one still links out to the
full-resolution PNG.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image


@dataclass
class PillowPreviewMaker:
    max_width: int = 480
    quality: int = 82

    def make(self, source: Path, destination: Path) -> None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(source) as image:
            preview = image.convert("RGB")
            preview.thumbnail(
                (self.max_width, self.max_width * 4), Image.Resampling.LANCZOS
            )
            preview.save(destination, "JPEG", quality=self.quality, optimize=True)
