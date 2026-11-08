"""Shared steps of the exposure build (spec A2.6), used by build_exposure, the test bundle and the holdout."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp

from waykin import constants as C
from waykin.data.allocation import build_allocation
from waykin.data.bundle import ExposureBundle
from waykin.data.montecarlo import simulate
from waykin.data.sources.base import category_config

LOCATION_COLUMNS = ["location_id", "lat", "lon", "count", "counts_by_category"]


def pivot_locations(table: pd.DataFrame) -> pd.DataFrame:
    """One row per published location: total count and a JSON {category: count}. Sorted by location_id."""
    rows = []
    for location_id, g in table.groupby("location_id", sort=True):
        by_category = {str(c): int(n) for c, n in sorted(zip(g["category"], g["count"]))}
        rows.append((location_id, float(g["lat"].iloc[0]), float(g["lon"].iloc[0]), sum(by_category.values()),
                     json.dumps(by_category, sort_keys=True)))
    df = pd.DataFrame(rows, columns=LOCATION_COLUMNS)
    df["count"] = df["count"].astype("int64")
    return df


def recent_locations(locations: pd.DataFrame, daily: pd.DataFrame, as_of: date, days: int) -> pd.DataFrame:
    """Locations counting only the reports from the last `days` days up to as_of (positions from `locations`)."""
    recent = daily[pd.to_datetime(daily["date"]) > pd.Timestamp(as_of - timedelta(days=days))]
    counts = recent.groupby(["location_id", "category"], as_index=False)["count"].sum()
    where = locations[["location_id", "lat", "lon"]]
    return pivot_locations(counts.merge(where, on="location_id", how="inner"))


def row_counts(locations: pd.DataFrame, A: sp.csr_matrix) -> np.ndarray:
    """One count per row of A: published counts, then zeros for the prior nodes."""
    counts = np.zeros(A.shape[0])
    counts[:len(locations)] = locations["count"].to_numpy(float)
    return counts


def build_radius(locations: pd.DataFrame, graph, radius_m: int, n_draws: int = C.N_DRAWS):
    """(A, X, mean, observed, allocation stats) for one radius."""
    A, stats = build_allocation(locations, graph, radius_m, category_config().severity)
    counts = row_counts(locations, A)
    X = simulate(A, counts, n_draws=n_draws, radius_m=int(radius_m))
    mean = X.mean(axis=1, dtype=np.float64).astype(np.float32)
    observed = np.asarray(A.T @ counts, dtype=np.float32)
    return A, X, mean, observed, stats


def save_radius(out_dir: Path, radius_m: int, A: sp.csr_matrix, X, mean, observed) -> None:
    sp.save_npz(out_dir / f"A_r{radius_m}.npz", A)
    np.save(out_dir / f"X_r{radius_m}.npy", X)
    np.save(out_dir / f"mean_r{radius_m}.npy", mean)
    np.save(out_dir / f"observed_r{radius_m}.npy", observed)


def make_bundle(locations: pd.DataFrame, graph, radii, *, source: str, source_label: str, as_of: date,
                category_preset: str, categories: list[str], n_draws: int = C.N_DRAWS,
                daily: pd.DataFrame | None = None, window_days: int = C.WINDOW_DAYS,
                route_locations: pd.DataFrame | None = None) -> ExposureBundle:
    """An in-memory bundle: nothing is written to disk. Routes use `route_locations` when given, else `locations`."""
    built_on = locations if route_locations is None else route_locations
    X, mean, observed = {}, {}, {}
    for r in radii:
        _, X[r], mean[r], observed[r], _ = build_radius(built_on, graph, int(r), n_draws=n_draws)
    return ExposureBundle(source=source, source_label=source_label, as_of=as_of, window_days=window_days,
                          category_preset=category_preset, categories=list(categories), radii=[int(r) for r in radii],
                          X=X, mean=mean, observed=observed, locations=locations, daily=daily)
