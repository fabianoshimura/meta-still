"""Composition root for the whole pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from meta_still.core.interfaces.prompt import ask
from meta_still.mapper.application.scan_folder import ScanFolder
from meta_still.mapper.infrastructure.os_filesystem import OsFileSystem
from meta_still.orchestrator.application.ingest_folder import (
    IngestFolder,
    IngestRequest,
)
from meta_still.stills.application.generate_stills import GenerateStills
from meta_still.stills.infrastructure.moviepy_frame_source import MoviePyFrameSource

DEFAULT_COUNT = 5
DEFAULT_MAX_EDGE = 1920


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="meta-still",
        description="Map a folder and generate thumbnails for every video in it.",
    )
    parser.add_argument("path", nargs="?", help="Folder to ingest")
    parser.add_argument("-o", "--out", help="Folder to write the map and thumbnails into")
    parser.add_argument("-n", "--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument(
        "--max-edge",
        type=int,
        default=DEFAULT_MAX_EDGE,
        help="Cap the long side of each still, in pixels. 0 keeps source resolution.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Redo clips whose thumbnails already exist",
    )
    args = parser.parse_args(argv)

    input_path = args.path or ask("Path to the folder to ingest")
    output_path = args.out or ask("Path for the output folder")

    root = Path(input_path).expanduser()
    if not root.is_dir():
        print(f"error: not a folder: {root}")
        return 2

    output_dir = Path(output_path).expanduser()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"error: cannot write to {output_dir}: {exc.strerror or exc}")
        return 2

    pipeline = IngestFolder(
        scan=ScanFolder(filesystem=OsFileSystem()),
        stills=GenerateStills(frames=MoviePyFrameSource(max_edge=args.max_edge or None)),
        progress=print,
    )

    result = pipeline.execute(
        IngestRequest(
            root=root,
            output_dir=output_dir,
            stills_per_clip=args.count,
            force=args.force,
        )
    )

    total_seconds = sum(o.seconds for o in result.outcomes)
    print()
    print(f"Done in {total_seconds / 60:.1f} min - {output_dir.resolve()}")
    print(f"  processed: {len(result.done)}")
    print(f"  skipped:   {len(result.skipped)} (already had thumbnails)")
    print(f"  failed:    {len(result.failures)}")

    for outcome in result.failures:
        print(f"    {outcome.source.name}: {outcome.error}")

    # A run that finished is a success even if some clips were unreadable -
    # those are reported above. Only a run where nothing at all came through
    # is a failed run.
    nothing_worked = result.failures and not result.done and not result.skipped
    return 1 if nothing_worked else 0
