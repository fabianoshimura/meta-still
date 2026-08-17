"""Composition root for the contact sheet."""

from __future__ import annotations

import argparse
from pathlib import Path

from meta_still.contactsheet.application.build_sheet import BuildContactSheet, SheetRequest
from meta_still.contactsheet.domain.renderer import render_sheet
from meta_still.contactsheet.infrastructure.output_scanner import scan_output
from meta_still.contactsheet.infrastructure.pillow_previews import PillowPreviewMaker
from meta_still.core.interfaces.paths import label_for
from meta_still.core.interfaces.prompt import ask

SHEET_NAME = "contact_sheet.html"


def build(output_dir: Path, with_previews: bool = True, progress=print) -> Path:
    """Write the sheet into an output folder and return its path.

    Shared by this CLI and the pipeline's composition root, so a full run ends
    with a readable page without duplicating the wiring.
    """
    builder = BuildContactSheet(
        scanner=scan_output,
        previews=PillowPreviewMaker(),
        progress=progress,
    )
    sheet = builder.execute(
        SheetRequest(
            output_dir=output_dir,
            title=label_for(output_dir),
            with_previews=with_previews,
        )
    )
    destination = output_dir / SHEET_NAME
    destination.write_text(render_sheet(sheet), encoding="utf-8")
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="meta-still-sheet",
        description="Build an HTML contact sheet from a finished output folder.",
    )
    parser.add_argument("path", nargs="?", help="Output folder produced by a run")
    parser.add_argument(
        "--no-previews",
        action="store_true",
        help="Link the full PNGs directly instead of generating small previews",
    )
    args = parser.parse_args(argv)

    output_path = args.path or ask("Path to the output folder")
    output_dir = Path(output_path).expanduser()
    if not output_dir.is_dir():
        print(f"error: not a folder: {output_dir}")
        return 2

    destination = build(output_dir, with_previews=not args.no_previews)
    print(f"Wrote {destination.resolve()}")
    return 0
