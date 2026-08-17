"""Run Module A standalone:  py -m meta_still.mapper "D:\\" -o map.txt"""

from __future__ import annotations

import sys

from meta_still.mapper.interfaces.cli import main

if __name__ == "__main__":
    sys.exit(main())
