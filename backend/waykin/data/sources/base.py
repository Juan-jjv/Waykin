"""Source adapters (spec A2.3). Every source returns exactly SOURCE_COLUMNS, one row per (location, category)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal, Protocol

import pandas as pd
import yaml

from waykin.constants import WINDOW_DAYS

SOURCE_COLUMNS = ["location_id", "lat", "lon", "category", "count", "period_start", "period_end"]
DATA_PKG = Path(__file__).resolve().parent.parent


class ExposureSource(Protocol):
    name: Literal["eps", "synthetic"]
    label: str                                   # shown in provenance

    def as_of(self) -> date: ...
    def load(self, bbox: tuple[float, float, float, float], categories: list[str] | None) -> pd.DataFrame: ...


@dataclass(frozen=True)
class CategoryConfig:
    categories: list[str]
    presets: dict[str, list[str]]
    active_preset: str
    synthetic_weights: list[float]
    severity: dict[str, float]

    @property
    def active(self) -> list[str]:
        return list(self.presets[self.active_preset])


@lru_cache(maxsize=1)
def category_config() -> CategoryConfig:
    raw = yaml.safe_load((DATA_PKG / "categories.yaml").read_text(encoding="utf-8"))
    cats = list(raw["categories"])
    weights = list(raw.get("synthetic_weights") or [1.0 / len(cats)] * len(cats))
    if len(weights) != len(cats):
        raise ValueError("synthetic_weights must have one weight per category")
    presets = {name: list(members) for name, members in raw["presets"].items()}
    if raw["active_preset"] not in presets:
        raise ValueError("active_preset must name one of the presets")
    for name, members in presets.items():
        unknown = set(members) - set(cats)
        if unknown:
            raise ValueError(f"preset {name} uses unknown categories: {sorted(unknown)}")
    severity = {c: float(w) for c, w in (raw.get("severity") or {}).items()}
    if set(severity) - set(cats):
        raise ValueError(f"severity uses unknown categories: {sorted(set(severity) - set(cats))}")
    if any(w <= 0 for w in severity.values()):
        raise ValueError("severity weights must be positive")
    return CategoryConfig(cats, presets, raw["active_preset"], weights, severity)


def get_source(name: str, data_dir: Path, graph=None) -> ExposureSource:
    if name == "synthetic":
        from waykin.data.sources.synthetic import SyntheticSource
        return SyntheticSource(data_dir, graph=graph)
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
    for col in ("lat", "lon"):
        if not pd.api.types.is_float_dtype(df[col]) or df[col].isna().any():
            raise ValueError(f"{col} must be a float with no missing values")
    for col in ("location_id", "category"):
        if not df[col].map(lambda v: isinstance(v, str)).all():
            raise ValueError(f"{col} must be a string")
    if not pd.api.types.is_integer_dtype(df["count"]) or (df["count"] < 1).any():
        raise ValueError("count must be an integer >= 1")
    for col in ("period_start", "period_end"):
        if not df[col].map(lambda v: isinstance(v, date)).all():
            raise ValueError(f"{col} must be a date")
    w, s, e, n = bbox
    inside = df["lat"].between(s, n) & df["lon"].between(w, e)
    if not inside.all():
        raise ValueError(f"{int((~inside).sum())} rows fall outside the bbox")
    span = (pd.to_datetime(df["period_end"]) - pd.to_datetime(df["period_start"])).dt.days
    if (abs(span - WINDOW_DAYS) > 1).any():
        raise ValueError(f"every row's period must span {WINDOW_DAYS} days (±1)")
    if df.duplicated(["location_id", "category"]).any():
        raise ValueError("duplicate (location_id, category) rows")
