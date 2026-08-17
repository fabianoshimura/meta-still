"""The project entry point:  py -m meta_still

Maps a folder to a .txt tree, then mirrors that structure into the output
folder, giving every video its own folder of thumbnails.
"""

from __future__ import annotations

import sys

from meta_still.orchestrator.interfaces.cli import main

if __name__ == "__main__":
    sys.exit(main())
