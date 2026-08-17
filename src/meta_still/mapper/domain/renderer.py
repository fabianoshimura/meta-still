"""Render a ScanReport as text. Presentation only — no I/O."""

from __future__ import annotations

from meta_still.core.domain.tree import DirectoryNode
from meta_still.mapper.domain.report import ScanReport
from meta_still.mapper.domain.statistics import collect_extensions

_UNITS = ("B", "KB", "MB", "GB", "TB", "PB")


def human_bytes(size: int) -> str:
    """Decimal units, matching how drives and cameras label capacity."""
    value = float(size)
    for unit in _UNITS:
        if value < 1000 or unit == _UNITS[-1]:
            precision = 0 if unit == "B" else 1
            return f"{value:.{precision}f} {unit}"
        value /= 1000
    return f"{size} B"  # unreachable, keeps type checkers happy


def render_report(report: ScanReport) -> str:
    tree = report.tree
    lines = [
        "meta-still - folder map",
        "=" * 60,
        f"Root:     {report.root}",
        f"Scanned:  {report.scanned_at:%Y-%m-%d %H:%M:%S}",
        f"Folders:  {tree.total_directories}",
        f"Files:    {tree.total_files}",
        f"Size:     {human_bytes(tree.total_bytes)}",
        f"Ignored:  {report.ignored_files} files, {report.ignored_directories} folders"
        "  (._* AppleDouble, .DS_Store, system folders)",
        "",
        "TREE",
        "-" * 60,
        f"{report.root}  [{tree.total_files} files, {human_bytes(tree.total_bytes)}]",
    ]
    _render_children(tree, prefix="", lines=lines)

    lines += ["", "EXTENSIONS", "-" * 60]
    for stat in collect_extensions(tree):
        lines.append(f"{stat.extension:<16}{stat.count:>8}   {human_bytes(stat.total_bytes):>12}")

    if report.errors:
        lines += ["", f"UNREADABLE PATHS ({len(report.errors)})", "-" * 60]
        lines += report.errors

    return "\n".join(lines) + "\n"


def _render_children(node: DirectoryNode, prefix: str, lines: list[str]) -> None:
    """Folders first, then files — the shape a human scans for structure."""
    entries: list[tuple[str, bool]] = [
        (f"{d.name}/  [{d.total_files} files, {human_bytes(d.total_bytes)}]", True)
        for d in node.directories
    ]
    entries += [(f"{f.name}  ({human_bytes(f.size_bytes)})", False) for f in node.files]

    for index, (label, is_directory) in enumerate(entries):
        last = index == len(entries) - 1
        lines.append(f"{prefix}{'`-- ' if last else '|-- '}{label}")
        if is_directory:
            child = node.directories[index]
            _render_children(child, prefix + ("    " if last else "|   "), lines)
