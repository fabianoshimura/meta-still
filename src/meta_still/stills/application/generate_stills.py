"""The Module C use-case: one video in, N stills out."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from meta_still.core.ports.frame_source import FrameSourcePort
from meta_still.stills.domain.naming import still_filename
from meta_still.stills.domain.sampling import evenly_spaced


@dataclass(frozen=True)
class StillsRequest:
    video: Path
    output_dir: Path
    count: int = 5
    extension: str = ".png"


@dataclass(frozen=True)
class GeneratedStill:
    index: int
    timestamp_seconds: float
    path: Path


@dataclass(frozen=True)
class StillsResult:
    video: Path
    duration_seconds: float
    stills: list[GeneratedStill]


@dataclass
class GenerateStills:
    frames: FrameSourcePort

    def execute(self, request: StillsRequest) -> StillsResult:
        stills: list[GeneratedStill] = []

        with self.frames.open(request.video) as handle:
            duration = handle.duration_seconds
            timestamps = evenly_spaced(duration, request.count)

            for index, timestamp in enumerate(timestamps, start=1):
                name = still_filename(request.video, index, request.count, request.extension)
                destination = request.output_dir / name
                handle.save_frame(timestamp, destination)
                stills.append(GeneratedStill(index, timestamp, destination))

        return StillsResult(video=request.video, duration_seconds=duration, stills=stills)
