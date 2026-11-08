"""ExposureBundle (spec B4), loading built artifacts, and the in-memory synthetic bundle every agent's tests use."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd


@dataclass
class ExposureBundle:
    source: Literal["eps", "synthetic"]
    source_label: str
    as_of: date
    window_days: int
    category_preset: str
    categories: list[str]
    radii: list[int]                       # radii actually loaded
    X: dict[int, np.ndarray]               # radius -> (E, N_DRAWS) float32 (memmap when loaded from disk)
    mean: dict[int, np.ndarray]            # radius -> (E,)
    observed: dict[int, np.ndarray]        # radius -> (E,)
    locations: pd.DataFrame                # published only: location_id, lat, lon, count, counts_by_category
    daily: pd.DataFrame | None = None      # location_id, date, category, count; None for builds made before it existed


def load_exposure(build_dir: Path, source: str, radii: list[int], expected_graph_hash: str) -> ExposureBundle:
    """Load `build_dir/<source>/`, written by scripts.data.build_exposure. X is memory-mapped."""
    d = Path(build_dir) / source
    manifest_path = d / "manifest.json"
    if not manifest_path.exists():
        raise FileNotFoundError(f"no exposure build for '{source}': run python -m scripts.data.build_exposure --source {source}")
    m = json.loads(manifest_path.read_text(encoding="utf-8"))
    if m["graph_hash"] != expected_graph_hash:
        raise RuntimeError("exposure built for a different graph; rerun build_exposure")
    radii = [int(r) for r in radii]
    absent = [r for r in radii if r not in m["radii"]]
    if absent:
        raise RuntimeError(f"radii {absent} not built (built: {m['radii']}); rerun build_exposure with --radii")
    return ExposureBundle(
        source=m["source"], source_label=m["source_label"], as_of=date.fromisoformat(m["as_of"]),
        window_days=int(m["window_days"]), category_preset=m["category_preset"], categories=list(m["categories"]),
        radii=radii,
        X={r: np.load(d / f"X_r{r}.npy", mmap_mode="r") for r in radii},
        mean={r: np.load(d / f"mean_r{r}.npy") for r in radii},
        observed={r: np.load(d / f"observed_r{r}.npy") for r in radii},
        locations=pd.read_parquet(d / "locations.parquet"),
        daily=pd.read_parquet(d / "daily.parquet") if (d / "daily.parquet").exists() else None,
    )


def make_synthetic_bundle_for_tests(graph, radii=(100,)) -> ExposureBundle:
    """In-memory, deterministic, no files: the real pipeline on any Graph."""
    from waykin import constants as C
    from waykin.data.pipeline import make_bundle, pivot_locations, recent_locations
    from waykin.data.sources.base import category_config
    from waykin.data.sources.synthetic import SYNTHETIC_AS_OF, SYNTHETIC_LABEL, SyntheticSource

    cfg = category_config()
    bbox = (float(graph.node_lon.min()), float(graph.node_lat.min()), float(graph.node_lon.max()), float(graph.node_lat.max()))
    source = SyntheticSource(Path("."), graph=graph)
    locations = pivot_locations(source.load(bbox, cfg.active))
    daily = source.daily(bbox, cfg.active)
    return make_bundle(locations, graph, radii, source="synthetic", source_label=SYNTHETIC_LABEL, as_of=SYNTHETIC_AS_OF,
                       category_preset=cfg.active_preset, categories=cfg.categories, daily=daily,
                       window_days=C.ROUTE_WINDOW_DAYS,
                       route_locations=recent_locations(locations, daily, SYNTHETIC_AS_OF, C.ROUTE_WINDOW_DAYS))
