"""Composition root for Module C."""

from __future__ import annotations

import argparse
from pathlib import Path

from meta_still.core.errors import MetaStillError
from meta_still.core.interfaces.prompt import ask
from meta_still.stills.application.generate_stills import GenerateStills, StillsRequest
from meta_still.stills.infrastructure.moviepy_frame_source import MoviePyFrameSource

DEFAULT_COUNT = 5
DEFAULT_MAX_EDGE = 1920


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="meta-still-stills",
        description="Generate N thumbnails from one video file.",
    )
    parser.add_argument("video", nargs="?", help="Video file to sample")
    parser.add_argument("-o", "--out", help="Folder to write the thumbnails into")
    parser.add_argument("-n", "--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument(
        "--max-edge",
        type=int,
        default=DEFAULT_MAX_EDGE,
        help="Cap the long side, in pixels. 0 keeps the source resolution.",
    )
    args = parser.parse_args(argv)

    video_path = args.video or ask("Path to the video file")
    output_path = args.out or ask("Path for the thumbnails folder", ".")

    video = Path(video_path).expanduser()
    if not video.is_file():
        print(f"error: not a file: {video}")
        return 2

    # Prove the destination works before decoding anything: seeking a large
    # clip is slow, and failing afterwards throws that work away.
    output_dir = Path(output_path).expanduser()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"error: cannot write to {output_dir}: {exc.strerror or exc}")
        return 2

    frames = MoviePyFrameSource(max_edge=args.max_edge or None)
    request = StillsRequest(video=video, output_dir=output_dir, count=args.count)

    try:
        result = GenerateStills(frames=frames).execute(request)
    except MetaStillError as exc:
        print(f"error: {exc}")
        return 1

    print(f"{video.name} - {result.duration_seconds:.2f}s")
    for still in result.stills:
        print(f"  {still.index}: t={still.timestamp_seconds:7.2f}s -> {still.path.name}")
    print(f"Wrote {len(result.stills)} thumbnails to {output_dir.resolve()}")
    return 0
