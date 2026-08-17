"""Composition root for Module A.

Parse arguments, build the concrete adapters, call the use-case, write the
output. Deliberately free of logic: anything interesting belongs in domain or
application, where it can be tested without a disk.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from meta_still.core.interfaces.paths import label_for
from meta_still.core.interfaces.prompt import ask
from meta_still.mapper.application.scan_folder import ScanFolder
from meta_still.mapper.domain.renderer import render_report
from meta_still.mapper.infrastructure.os_filesystem import OsFileSystem


def resolve_output(raw: str, root: Path) -> Path:
    """Turn whatever the operator typed into a file path.

    A folder is a natural answer to "where should the map go", so accept it and
    name the file after the folder that was scanned - mapping several drives
    into one place then produces distinct files instead of overwrites.
    """
    output = Path(raw).expanduser()
    if output.is_dir() or raw.endswith(("\\", "/")):
        return output / f"{label_for(root)}_map.txt"
    if not output.suffix:
        return output.with_suffix(".txt")
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="meta-still-mapper",
        description="Map a folder tree and write it to a .txt report.",
    )
    parser.add_argument("path", nargs="?", help=r"Folder or drive to map, e.g. D:\ ")
    parser.add_argument("-o", "--out", help="Output .txt file or folder (default: map.txt)")
    args = parser.parse_args(argv)

    # No arguments: we were launched from the play button, so ask.
    input_path = args.path or ask("Path to the folder to map")
    output_path = args.out or ask("Path for the .txt map file (a folder is fine)", "map.txt")

    root = Path(input_path).expanduser()
    if not root.is_dir():
        print(f"error: not a folder: {root}")
        return 2

    output = resolve_output(output_path, root)
    # Prove we can write before scanning: a drive takes minutes to walk, and
    # discovering the destination is bad only afterwards throws that away.
    try:
        if str(output.parent):
            output.parent.mkdir(parents=True, exist_ok=True)
        output.open("a").close()
    except OSError as exc:
        print(f"error: cannot write to {output}: {exc.strerror or exc}")
        return 2

    report = ScanFolder(filesystem=OsFileSystem()).execute(root)

    try:
        output.write_text(render_report(report), encoding="utf-8")
    except OSError as exc:
        print(f"error: cannot write to {output}: {exc.strerror or exc}")
        return 1

    tree = report.tree
    print(f"Mapped {tree.total_files} files in {tree.total_directories} folders.")
    print(f"Wrote {output.resolve()}")
    if report.errors:
        print(f"{len(report.errors)} path(s) could not be read - listed at the end of the report.")
    return 0
