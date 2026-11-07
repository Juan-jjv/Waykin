"""Source adapters (spec A2.3). Every source returns exactly SOURCE_COLUMNS."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Literal, Protocol

import pandas as pd

from waykin.constants import WINDOW_DAYS

SOURCE_COLUMNS = ["location_id", "lat", "lon", "category", "count", "period_start", "period_end"]


class ExposureSource(Protocol):
    name: Literal["eps", "synthetic"]
    label: str

    def as_of(self) -> date: ...
    def load(self, bbox: tuple[float, float, float, float], categories: list[str] | None) -> pd.DataFrame: ...


def get_source(name: str, data_dir: Path) -> ExposureSource:
    if name == "synthetic":
        from waykin.data.sources.synthetic import SyntheticSource
        return SyntheticSource(data_dir)
    if name == "eps":
        from waykin.data.sources.eps import EpsSource
        return EpsSource(data_dir)
    raise ValueError("EXPOSURE_SOURCE must be 'synthetic' or 'eps'")


def validate_source_table(df: pd.DataFrame, bbox) -> None:
    """Raise ValueError with a short message (never coordinates) if the table breaks the contract."""
    if list(df.columns) != SOURCE_COLUMNS:
        raise ValueError(f"source table must have exactly the columns {SOURCE_COLUMNS}")
    if df.empty:
        return
    if not pd.api.types.is_integer_dtype(df["count"]) or (df["count"] < 1).any():
        raise ValueError("count must be an integer >= 1")
    w, s, e, n = bbox
    inside = df["lat"].between(s, n) & df["lon"].between(w, e)
    if not inside.all():
        raise ValueError(f"{int((~inside).sum())} rows fall outside the bbox")
    span = (pd.to_datetime(df["period_end"]) - pd.to_datetime(df["period_start"])).dt.days
    if (abs(span - WINDOW_DAYS) > 1).any():
        raise ValueError(f"every row's period must span {WINDOW_DAYS} days (±1)")
    if df.duplicated(["location_id", "category"]).any():
        raise ValueError("duplicate (location_id, category) rows")
