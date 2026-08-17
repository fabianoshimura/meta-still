"""Build a contact sheet from a finished output folder."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from meta_still.contactsheet.domain.model import ClipEntry, Sheet, Still
from meta_still.contactsheet.infrastructure.output_scanner import (
    PREVIEWS_DIR,
    ScannedClip,
)
from meta_still.core.ports.previews import PreviewMakerPort


@dataclass(frozen=True)
class SheetRequest:
    output_dir: Path
    title: str
    with_previews: bool = True


@dataclass
class BuildContactSheet:
    scanner: Callable[[Path], list[ScannedClip]]
    previews: PreviewMakerPort
    clock: Callable[[], datetime] = datetime.now
    progress: Callable[[str], None] = lambda _message: None

    def execute(self, request: SheetRequest) -> Sheet:
        scanned = self.scanner(request.output_dir)
        self.progress(f"{len(scanned)} clips with thumbnails")

        clips = [self._entry(request, clip) for clip in scanned]
        return Sheet(title=request.title, generated_at=self.clock(), clips=clips)

    def _entry(self, request: SheetRequest, clip: ScannedClip) -> ClipEntry:
        stills = []
        for still in clip.stills:
            full = still.relative_to(request.output_dir)
            preview = full
            if request.with_previews:
                preview = Path(PREVIEWS_DIR) / full.with_suffix(".jpg")
                try:
                    self.previews.make(still, request.output_dir / preview)
                except Exception as exc:  # a bad still must not lose the sheet
                    self.progress(f"  preview failed for {still.name}: {exc}")
                    preview = full
            stills.append(
                Still(href=_url(full), preview=_url(preview), label=still.stem)
            )
        return ClipEntry(group=clip.group, name=clip.name, stills=stills)


def _url(path: Path) -> str:
    """Relative href. Percent-encoded: these names are full of spaces and accents."""
    return quote(path.as_posix())
