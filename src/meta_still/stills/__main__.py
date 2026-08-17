"""Run Module C standalone:  py -m meta_still.stills"""

from __future__ import annotations

import sys

from meta_still.stills.interfaces.cli import main

if __name__ == "__main__":
    sys.exit(main())
