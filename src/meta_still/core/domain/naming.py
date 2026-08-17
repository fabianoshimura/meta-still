"""Turning names found on disk into names we can safely create.

Source names come from cameras, recorders and editors, none of which promise
anything about Windows path rules. MultiCorder, for one, ends every filename
with a space.
"""

from __future__ import annotations

_ILLEGAL = '<>:"/\\|?*'

# Reserved on Windows regardless of extension: CON.mp4 is as invalid as CON.
_RESERVED = frozenset(
    {"CON", "PRN", "AUX", "NUL"}
    | {f"COM{digit}" for digit in range(1, 10)}
    | {f"LPT{digit}" for digit in range(1, 10)}
)


def safe_name(name: str, fallback: str = "unnamed") -> str:
    """Make one path component that Windows will store under the name we ask for.

    Trailing spaces and dots are the dangerous part, and they fail in a way
    that hides itself: Windows strips them from the *last* component of a path
    but not from the middle. So `mkdir("clip ")` quietly creates `clip`,
    `is_dir("clip ")` then answers True, and writing `clip \\thumb.png` fails
    with "No such file or directory" - three calls, three different ideas of
    what the name is.
    """
    cleaned = "".join("_" if char in _ILLEGAL or ord(char) < 32 else char for char in name)
    cleaned = cleaned.rstrip(" .")

    if not cleaned:
        return fallback
    if cleaned.split(".")[0].upper() in _RESERVED:
        return f"{cleaned}_"
    return cleaned
