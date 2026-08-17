"""Camera-card folders that carry no meaning worth mirroring.

A Sony card writes `FX3_B/M4ROOT/CLIP/C2663.MP4`. `M4ROOT` and `CLIP` are
fixed plumbing the camera creates on every card - they say nothing about the
shoot, and reproducing them in the output buries the clip two levels deeper for
no gain. The camera folder and the clip name are the parts a human navigates by.

Deliberately excluded, despite being real card folders elsewhere:
`VIDEO`, `AUDIO`, `CONTENTS` (Panasonic P2). They are ordinary folder names
that appear in hand-made structures too - this drive has a `CAMERAS/<date>/AUDIO/`
that means something. Collapsing on a generic name risks silently merging
folders a person created on purpose.
"""

from __future__ import annotations

STRUCTURAL_FOLDERS = frozenset(
    {
        # Sony XAVC-S / FX3 / FX6
        "M4ROOT",
        "CLIP",
        "SUB",
        # Sony XDCAM
        "XDROOT",
        # AVCHD and consumer cards
        "DCIM",
        "AVCHD",
        "BDMV",
        "STREAM",
    }
)


def collapse_structural(parents: tuple[str, ...]) -> tuple[str, ...]:
    """Drop card plumbing from a path, keeping every meaningful folder.

    `("CAMERAS", "2026_04_27", "FX3_B", "M4ROOT", "CLIP")`
    -> `("CAMERAS", "2026_04_27", "FX3_B")`
    """
    return tuple(part for part in parents if part.upper() not in STRUCTURAL_FOLDERS)
