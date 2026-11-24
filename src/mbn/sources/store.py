"""Local access to downloaded portal files: <root>/<organization>/<dataset>/<file>."""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path

from mbn.config import DATASET_URL
from mbn.model.source import Source


class DatasetStore:
    """Finds files and dataset metadata under a downloads folder."""

    def __init__(self, root: str | Path) -> None:
        self.root = str(root)

    def files(self, pattern: str) -> list[str]:
        """Data files matching a glob relative to the root (metadata excluded), sorted."""
        return sorted(
            f for f in glob.glob(os.path.join(self.root, pattern)) if not f.endswith("metadata.json") and "metadata.xlsx" not in f
        )

    def file(self, pattern: str) -> str:
        found = self.files(pattern)
        if not found:
            raise FileNotFoundError(f"no file matches {pattern!r} under {self.root}")
        return found[0]

    def dirs(self, pattern: str) -> list[str]:
        return sorted(glob.glob(os.path.join(self.root, pattern)))

    def source(self, dataset_pattern: str) -> Source:
        """Title, publisher and portal link of the first dataset folder matching the pattern."""
        found = glob.glob(os.path.join(self.root, dataset_pattern, "metadata.json"))
        if not found:
            raise FileNotFoundError(f"no metadata for {dataset_pattern!r} under {self.root}")
        with open(found[0], encoding="utf-8") as f:
            m = json.load(f)
        return Source(
            title=m["title"].strip(),
            org=(m.get("organization") or {}).get("title", "").strip(),
            url=DATASET_URL + m["name"],
        )
