"""Terminal prompting shared by every module's composition root.

Lives in core because each module needs it and modules must not import each
other - only core.
"""

from __future__ import annotations

# Invisible characters Windows adds to copied paths: the BOM, and the
# directional marks that the file Properties dialog inserts. Both survive a
# plain .strip() and produce an error message with nothing visibly wrong in it.
INVISIBLE = "﻿‎‏‪‫‬‭‮"


def ask(label: str, default: str = "") -> str:
    """Prompt the operator, tolerating pasted paths.

    Windows' "Copy as path" wraps the path in quotes, so strip those too rather
    than making the user delete them by hand every run.
    """
    suffix = f" [{default}]" if default else ""
    answer = input(f"{label}{suffix}: ").strip(INVISIBLE + " \t\r\n").strip("\"'").strip()
    return answer or default
