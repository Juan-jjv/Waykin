"""EpsSource (spec A2.3, due H14). Reads a snapshot a human placed in data/raw/eps/. Never downloads.

Phase 1 stub. Before implementing: open the real file and fill eps_columns.yaml from its actual
headers. Never guess field names. Drop address/description columns immediately after reading.
"""
from datetime import date
from pathlib import Path


class EpsSource:
    name = "eps"
    label = "Edmonton Police Service data snapshot"

    def __init__(self, data_dir: Path):
        self.raw_dir = Path(data_dir) / "raw" / "eps"

    def _require_snapshot(self):
        if not self.raw_dir.is_dir() or not any(self.raw_dir.iterdir()):
            raise FileNotFoundError("EPS snapshot not found in data/raw/eps; use EXPOSURE_SOURCE=synthetic")

    def as_of(self) -> date:
        self._require_snapshot()
        raise NotImplementedError("EpsSource arrives in Phase 2 (H14)")

    def load(self, bbox, categories):
        self._require_snapshot()
        raise NotImplementedError("EpsSource arrives in Phase 2 (H14)")
