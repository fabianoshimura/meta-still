"""Port for reading a filesystem tree.

The seam that lets every use-case be tested against an in-memory tree, with no
drive attached. Adapters live in each module's `infrastructure` package.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from meta_still.core.domain.tree import TreeScan


class FileSystemPort(Protocol):
    def build_tree(self, root: Path) -> TreeScan:
        """Return the tree rooted at `root`, with errors and skip counts.

        Unreadable paths are reported, never raised: a single protected folder
        must not abort the scan of a whole drive.
        """
        ...
