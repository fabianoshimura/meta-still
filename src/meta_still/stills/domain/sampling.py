"""Choosing which moments of a clip to capture. Pure arithmetic."""

from __future__ import annotations

from meta_still.core.errors import UnreadableVideo


def evenly_spaced(duration_seconds: float, count: int) -> list[float]:
    """Timestamps for `count` stills, avoiding both ends of the clip.

    The clip is split into `count + 1` segments and sampled at the interior
    boundaries. Sampling at i/count instead would put the first still on frame
    zero, which on camera rushes is a slate, a lens cap or black far more often
    than it is a useful image - and the last still on the tail, where the
    operator is usually already walking towards the camera.
    """
    if count < 1:
        raise ValueError("count must be at least 1")
    if duration_seconds <= 0:
        raise UnreadableVideo(f"duration is not usable: {duration_seconds}")

    step = duration_seconds / (count + 1)
    return [step * (index + 1) for index in range(count)]
