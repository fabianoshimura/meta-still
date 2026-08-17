"""Remember the last run's settings.

A tool used on drive after drive should not ask for the same output folder
every time.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

SETTINGS_FILE = Path.home() / ".meta-still" / "ui.json"

DEFAULTS: dict[str, Any] = {
    "source": "",
    "output": "",
    "count": 5,
    "force": False,
    "sheet": True,
}


def load_settings() -> dict[str, Any]:
    settings = dict(DEFAULTS)
    try:
        stored = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return settings  # missing or corrupt: defaults, never a crash on launch
    settings.update({key: stored[key] for key in DEFAULTS if key in stored})
    return settings


def save_settings(settings: dict[str, Any]) -> None:
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    except OSError:
        pass  # remembering is a convenience, not a reason to fail a run
