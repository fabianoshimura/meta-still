"""Port for reading frames out of a video file.

Decoding is the expensive, failure-prone part of this project, and the only
part that needs real media to exercise. Keeping it behind a port means the
sampling and naming rules are testable without a single byte of video.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol


class VideoHandle(Protocol):
    """An opened video. Valid only inside its context manager."""

    @property
    def duration_seconds(self) -> float:
        """Raises UnreadableVideo if the file reports no usable duration."""
        ...

    def save_frame(self, timestamp_seconds: float, destination: Path) -> None:
        """Write the frame at `timestamp_seconds` to `destination`."""
        ...


class FrameSourcePort(Protocol):
    def open(self, video: Path) -> AbstractContextManager[VideoHandle]:
        """Open a video, guaranteeing release even if a frame read fails.

        A context manager rather than open/close: a batch that leaks one
        decoder subprocess per bad file runs out of handles long before it runs
        out of clips.
        """
        ...
