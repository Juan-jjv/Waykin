"""EpsSource (spec A2.3): reads a snapshot a human placed in data/raw/eps/. Never downloads anything.

* Column names come ONLY from eps_columns.yaml, filled in from the real file's headers. Never guessed.
* Every other column (addresses, blocks, descriptions, free text) is dropped immediately after reading.
* Points are kept exactly as published. Never geocoded, never refined, never turned into an address.
* The window is the WINDOW_DAYS (30) days ending at as_of, where as_of is the latest date in the file.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml
from pyproj import Transformer

from waykin import constants as C
from waykin.data.sources.base import DAILY_COLUMNS, DATA_PKG, SOURCE_COLUMNS, category_config

EPS_LABEL = "Edmonton Police Service data snapshot"
SUFFIXES = (".csv", ".xlsx", ".geojson", ".json")
_WKT_POINT = re.compile(r"POINT\s*\(\s*([-0-9.eE+]+)\s+([-0-9.eE+]+)\s*\)", re.IGNORECASE)
_GEOM_LAT, _GEOM_LON = "__geom_lat", "__geom_lon"


class EpsConfigError(RuntimeError):
    """The snapshot or eps_columns.yaml needs a human's attention. Messages never contain coordinates."""


def _location_id(lat: float, lon: float) -> str:
    return "eps-" + hashlib.blake2b(f"{lat:.7f},{lon:.7f}".encode(), digest_size=5).hexdigest()


class EpsSource:
    name = "eps"
    label = EPS_LABEL

    def __init__(self, data_dir: Path, mapping_path: Path | None = None):
        self.raw_dir = Path(data_dir) / "raw" / "eps"
        self.mapping_path = Path(mapping_path) if mapping_path else DATA_PKG / "eps_columns.yaml"
        self._table_cache: pd.DataFrame | None = None
        self._as_of: date | None = None

    # ------------------------------------------------------------ reading
    def _snapshot(self) -> Path:
        files = sorted(p for p in self.raw_dir.glob("*") if p.suffix.lower() in SUFFIXES) if self.raw_dir.is_dir() else []
        if not files:
            raise FileNotFoundError("EPS snapshot not found in data/raw/eps; use EXPOSURE_SOURCE=synthetic")
        if len(files) > 1:
            raise EpsConfigError(f"expected one snapshot file in data/raw/eps, found {len(files)}")
        return files[0]

    def _mapping(self) -> dict:
        m = yaml.safe_load(self.mapping_path.read_text(encoding="utf-8")) or {}
        cols = m.get("columns") or {}
        if not cols.get("category") or not cols.get("date"):
            raise EpsConfigError("eps_columns.yaml is not filled in yet: copy the exact category and date headers "
                                 "from the real file")
        if not m.get("category_map"):
            raise EpsConfigError("eps_columns.yaml category_map is empty: map EPS categories to canonical ones")
        unknown = set(m["category_map"].values()) - set(category_config().categories)
        if unknown:
            raise EpsConfigError(f"category_map targets are not in categories.yaml: {sorted(unknown)}")
        return m

    @staticmethod
    def _read(path: Path) -> pd.DataFrame:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            return pd.read_csv(path, encoding="utf-8-sig", low_memory=False)
        if suffix == ".xlsx":
            try:
                return pd.read_excel(path)
            except ImportError as ex:
                raise EpsConfigError("reading .xlsx needs openpyxl (see contract-requests/A2.md); "
                                     "or save the snapshot as .csv") from ex
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        rows = []
        for feature in data.get("features", []):
            props = dict(feature.get("properties") or {})
            geom = feature.get("geometry") or {}
            if geom.get("type") == "Point":
                props[_GEOM_LON], props[_GEOM_LAT] = geom["coordinates"][:2]
            rows.append(props)
        df = pd.DataFrame(rows)
        crs = ((data.get("crs") or {}).get("properties") or {}).get("name")
        if crs and _GEOM_LON in df:     # the portal's export is in web-map metres, not degrees
            to_degrees = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
            df[_GEOM_LON], df[_GEOM_LAT] = to_degrees.transform(df[_GEOM_LON].to_numpy(float), df[_GEOM_LAT].to_numpy(float))
        return df

    def _table(self) -> pd.DataFrame:
        """Read, keep only the mapped columns, normalise. Columns: lat, lon, date, category, count. Cached."""
        if self._table_cache is not None:
            return self._table_cache
        snapshot = self._snapshot()          # a missing file is the more useful message, so check it first
        m = self._mapping()
        cols = m["columns"]
        raw = self._read(snapshot)

        keep = {cols["category"]: "category", cols["date"]: "date"}
        if cols.get("count"):
            keep[cols["count"]] = "count"
        if m.get("point_wkt"):
            keep[m["point_wkt"]] = "wkt"
        elif cols.get("lat") and cols.get("lon"):
            keep[cols["lat"]], keep[cols["lon"]] = "lat", "lon"
        elif _GEOM_LAT in raw.columns:
            keep[_GEOM_LAT], keep[_GEOM_LON] = "lat", "lon"
        else:
            raise EpsConfigError("eps_columns.yaml needs lat and lon, or point_wkt, unless the file is GeoJSON points")
        absent = [c for c in keep if c not in raw.columns]
        if absent:
            raise EpsConfigError(f"columns named in eps_columns.yaml are not in the file: {absent}")
        df = raw[list(keep)].rename(columns=keep)          # every other column is dropped here
        del raw

        if "wkt" in df:
            points = df.pop("wkt").astype(str).str.extract(_WKT_POINT)
            df["lon"], df["lat"] = points[0], points[1]
        # Rounded to the precision of _location_id, so points a hair apart share one location.
        df["lat"] = pd.to_numeric(df["lat"], errors="coerce").astype(float).round(7)
        df["lon"] = pd.to_numeric(df["lon"], errors="coerce").astype(float).round(7)
        df["date"] = pd.to_datetime(df["date"], errors="coerce").dt.date
        df["count"] = pd.to_numeric(df["count"], errors="coerce").fillna(0).astype("int64") if "count" in df else 1
        dated = df["date"].dropna()
        if dated.empty:
            raise EpsConfigError("no readable dates in the EPS snapshot; check the date column in eps_columns.yaml")
        self._as_of = max(dated)
        df["category"] = df["category"].astype(str).map(m["category_map"])  # unmapped categories become NaN
        self._table_cache = df.dropna(subset=["category", "lat", "lon", "date"])
        return self._table_cache

    # ------------------------------------------------------------ contract
    def as_of(self) -> date:
        self._table()
        return self._as_of

    def _reports(self, bbox, categories: list[str] | None, start: date, end: date) -> pd.DataFrame:
        t = self._table()
        w, s, e, n = bbox
        wanted = set(categories) if categories else set(category_config().categories)
        return t[(t["date"] > start) & (t["date"] <= end) & t["lat"].between(s, n) & t["lon"].between(w, e)
                 & t["category"].isin(wanted) & (t["count"] >= 1)]

    def window(self, bbox, categories: list[str] | None, start: date, end: date) -> pd.DataFrame:
        """Reports with start < date ≤ end, aggregated to (location, category), in the source-table shape."""
        t = self._reports(bbox, categories, start, end)
        if t.empty:
            return pd.DataFrame(columns=SOURCE_COLUMNS)
        g = t.groupby(["lat", "lon", "category"], as_index=False)["count"].sum()
        g.insert(0, "location_id", [_location_id(a, b) for a, b in zip(g["lat"], g["lon"])])
        g["period_start"], g["period_end"] = start, end
        g["count"] = g["count"].astype("int64")
        return g[SOURCE_COLUMNS].reset_index(drop=True)

    def load(self, bbox, categories: list[str] | None) -> pd.DataFrame:
        end = self.as_of()
        return self.window(bbox, categories, end - timedelta(days=C.WINDOW_DAYS), end)

    def daily(self, bbox, categories: list[str] | None) -> pd.DataFrame:
        end = self.as_of()
        t = self._reports(bbox, categories, end - timedelta(days=C.WINDOW_DAYS), end)
        if t.empty:
            return pd.DataFrame(columns=DAILY_COLUMNS)
        g = t.groupby(["lat", "lon", "date", "category"], as_index=False)["count"].sum()
        g.insert(0, "location_id", [_location_id(a, b) for a, b in zip(g["lat"], g["lon"])])
        g["count"] = g["count"].astype("int64")
        return g[DAILY_COLUMNS].sort_values(["location_id", "date", "category"]).reset_index(drop=True)
