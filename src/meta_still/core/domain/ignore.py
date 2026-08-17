"""Files and folders that should not exist as far as this project is concerned.

Applied during the scan, so the map, the clip count and the created folders all
agree with each other. The counts of what was skipped are reported rather than
dropped silently - numbers that do not add up are worse than numbers that are
large.
"""

from __future__ import annotations

# AppleDouble resource forks. A Mac touched this material, so nearly every real
# file has a 4 KB "._" twin carrying the same extension - which would otherwise
# be counted as a clip, given a folder, and handed to ffmpeg to fail on.
IGNORED_FILE_PREFIXES = ("._",)

IGNORED_FILE_NAMES = frozenset({".DS_Store", "Thumbs.db", "desktop.ini"})

IGNORED_DIRECTORY_NAMES = frozenset(
    {
        "$RECYCLE.BIN",
        "System Volume Information",
        ".Spotlight-V100",
        ".Trashes",
        ".fseventsd",
        ".TemporaryItems",
    }
)


def is_ignored_file(name: str) -> bool:
    return name.startswith(IGNORED_FILE_PREFIXES) or name in IGNORED_FILE_NAMES


def is_ignored_directory(name: str) -> bool:
    return name in IGNORED_DIRECTORY_NAMES or name.startswith(IGNORED_FILE_PREFIXES)
