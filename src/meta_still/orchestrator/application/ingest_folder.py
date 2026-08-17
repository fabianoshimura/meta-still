"""The pipeline: map a folder, then generate stills for every video in it.

The one layer permitted to know about more than one module - composing them is
its entire job. It arranges files on disk directly rather than behind a port,
because arranging files on disk is what it is for.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from meta_still.core.domain.media import is_video
from meta_still.core.domain.naming import safe_name
from meta_still.core.domain.tree import iter_files
from meta_still.core.interfaces.paths import label_for
from meta_still.mapper.application.scan_folder import ScanFolder
from meta_still.mapper.domain.renderer import render_report
from meta_still.orchestrator.domain.planning import PlannedClip, plan_destinations
from meta_still.stills.application.generate_stills import GenerateStills, StillsRequest


@dataclass(frozen=True)
class IngestRequest:
    root: Path
    output_dir: Path
    stills_per_clip: int = 5
    force: bool = False


@dataclass(frozen=True)
class ClipOutcome:
    source: Path
    destination: Path
    stills: int = 0
    skipped: bool = False
    error: str | None = None
    seconds: float = 0.0

    @property
    def failed(self) -> bool:
        return self.error is not None


@dataclass(frozen=True)
class IngestResult:
    map_path: Path
    outcomes: list[ClipOutcome] = field(default_factory=list)
    stopped: bool = False
    total_clips: int = 0

    @property
    def done(self) -> list[ClipOutcome]:
        return [o for o in self.outcomes if not o.failed and not o.skipped]

    @property
    def skipped(self) -> list[ClipOutcome]:
        return [o for o in self.outcomes if o.skipped]

    @property
    def failures(self) -> list[ClipOutcome]:
        return [o for o in self.outcomes if o.failed]


@dataclass
class IngestFolder:
    scan: ScanFolder
    stills: GenerateStills
    progress: Callable[[str], None] = lambda _message: None
    timer: Callable[[], float] = time.monotonic
    # A GUI needs two things a CLI does not: a number to draw a bar with, and
    # a way to stop a 25-minute run without killing the process.
    on_step: Callable[[int, int], None] = lambda _done, _total: None
    should_stop: Callable[[], bool] = lambda: False

    def execute(self, request: IngestRequest) -> IngestResult:
        report = self.scan.execute(request.root)

        map_path = request.output_dir / f"{safe_name(label_for(request.root))}_map.txt"
        map_path.parent.mkdir(parents=True, exist_ok=True)
        map_path.write_text(render_report(report), encoding="utf-8")
        self.progress(f"Mapped {report.tree.total_files} files -> {map_path.name}")

        videos = [
            (parents, file.name)
            for parents, file in iter_files(report.tree)
            if is_video(file.name)
        ]
        self.progress(f"{len(videos)} video files to process")

        plan = plan_destinations(videos, request.output_dir)
        outcomes: list[ClipOutcome] = []
        stopped = False

        for position, clip in enumerate(plan, start=1):
            # Checked between clips, never mid-clip: interrupting a decode
            # would leave a half-written PNG that the resume check would then
            # count as done.
            if self.should_stop():
                stopped = True
                self.progress(f"Stopped after {len(outcomes)} of {len(plan)} clips.")
                break
            outcomes.append(self._process(request, position, len(plan), clip))
            self.on_step(position, len(plan))

        return IngestResult(
            map_path=map_path,
            outcomes=outcomes,
            stopped=stopped,
            total_clips=len(plan),
        )

    def _process(
        self,
        request: IngestRequest,
        position: int,
        total: int,
        clip: PlannedClip,
    ) -> ClipOutcome:
        source = request.root.joinpath(*clip.parents, clip.filename)
        destination = clip.destination
        marker = f"[{position:>4}/{total}] {clip.filename}"

        if not request.force and self._already_done(destination, request.stills_per_clip):
            self.progress(f"{marker}  - already done, skipped")
            return ClipOutcome(source=source, destination=destination, skipped=True)

        started = self.timer()
        try:
            destination.mkdir(parents=True, exist_ok=True)
            result = self.stills.execute(
                StillsRequest(
                    video=source,
                    output_dir=destination,
                    count=request.stills_per_clip,
                )
            )
        except Exception as exc:  # one bad clip must not end a 160-clip run
            elapsed = self.timer() - started
            try:  # succeeds only if empty, so partial output is left for retry
                destination.rmdir()
            except OSError:
                pass
            self.progress(f"{marker}  - FAILED: {exc}")
            return ClipOutcome(
                source=source,
                destination=destination,
                error=str(exc),
                seconds=elapsed,
            )

        elapsed = self.timer() - started
        self.progress(f"{marker}  - {len(result.stills)} stills in {elapsed:.1f}s")
        return ClipOutcome(
            source=source,
            destination=destination,
            stills=len(result.stills),
            seconds=elapsed,
        )

    @staticmethod
    def _already_done(destination: Path, expected: int) -> bool:
        """Resume support: drives get unplugged, and 25 minutes is a long redo."""
        if not destination.is_dir():
            return False
        return len(list(destination.glob("*.png"))) >= expected
