"""moviepy adapter for FrameSourcePort.

Grabs raw frames and writes them with Pillow rather than using moviepy's
save_frame, which gives us control over format and size. No colour transform is
applied at any step: S-Log3 footage stays log, which is what makes the stills
valid input for the white-balance module.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from moviepy import VideoFileClip
from PIL import Image

from meta_still.core.errors import UnreadableVideo


def _reason(exc: Exception) -> str:
    """moviepy embeds the whole of ffmpeg's stderr in its exception.

    Unabridged that is ~8 lines per bad clip, twice over (progress line and
    end-of-run recap), which buries the run summary. Keep the line that
    actually says what went wrong.
    """
    lines = [line.strip() for line in str(exc).splitlines() if line.strip()]
    if not lines:
        return type(exc).__name__
    errors = [line for line in lines if line.startswith("Error")]
    return errors[-1] if errors else lines[0]


@dataclass
class MoviePyVideoHandle:
    clip: VideoFileClip
    max_edge: int | None

    @property
    def duration_seconds(self) -> float:
        duration = self.clip.duration
        if not duration or duration <= 0:
            raise UnreadableVideo(f"no usable duration reported: {duration!r}")
        return float(duration)

    def save_frame(self, timestamp_seconds: float, destination: Path) -> None:
        frame = self.clip.get_frame(timestamp_seconds)  # RGB uint8 array
        image = Image.fromarray(frame)
        if self.max_edge and max(image.size) > self.max_edge:
            image.thumbnail((self.max_edge, self.max_edge), Image.Resampling.LANCZOS)
        image.save(destination)


@dataclass
class MoviePyFrameSource:
    """max_edge caps the long side; None keeps the source resolution."""

    max_edge: int | None = 1920

    @contextmanager
    def open(self, video: Path) -> Iterator[MoviePyVideoHandle]:
        try:
            clip = VideoFileClip(str(video))
        except Exception as exc:  # moviepy raises a wide variety here
            # No filename prefix: every caller already knows which clip it
            # asked for, and prefixing here prints it twice.
            raise UnreadableVideo(_reason(exc)) from exc

        try:
            yield MoviePyVideoHandle(clip=clip, max_edge=self.max_edge)
        finally:
            clip.close()
