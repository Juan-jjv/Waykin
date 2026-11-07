"""SyntheticSource (spec A2.3, due H13). Phase 1 stub."""
from datetime import date
from pathlib import Path

from waykin.data.bundle import SYNTHETIC_AS_OF, SYNTHETIC_LABEL


class SyntheticSource:
    name = "synthetic"
    label = SYNTHETIC_LABEL

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)

    def as_of(self) -> date:
        return SYNTHETIC_AS_OF

    def load(self, bbox, categories):
        raise NotImplementedError("SyntheticSource.load arrives in Phase 2 (H13)")
