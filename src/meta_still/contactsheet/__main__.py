"""Rebuild a contact sheet:  py -m meta_still.contactsheet"""

from __future__ import annotations

import sys

from meta_still.contactsheet.interfaces.cli import main

if __name__ == "__main__":
    sys.exit(main())
