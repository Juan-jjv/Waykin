"""SyntheticSource (spec A2.3): clearly labelled demo data at real intersections, byte-for-byte deterministic."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from waykin import constants as C
from waykin.data.sources.base import SOURCE_COLUMNS, category_config

SYNTHETIC_LABEL = "Synthetic data (demo)"
SYNTHETIC_AS_OF = date(2026, 10, 31)
N_HOTSPOTS = 5


def synthetic_counts(node_x: np.ndarray, node_y: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """90-day counts per node: rate_i = 0.05 + Σ_h a_h·exp(-d²/2σ_h²), count ~ Poisson(rate)."""
    hot = rng.choice(len(node_x), size=min(N_HOTSPOTS, len(node_x)), replace=False)
    sigma = rng.uniform(150.0, 400.0, len(hot))
    amp = rng.uniform(2.0, 8.0, len(hot))
    d2 = (node_x[:, None] - node_x[hot][None, :]) ** 2 + (node_y[:, None] - node_y[hot][None, :]) ** 2
    rate = 0.05 + (amp[None, :] * np.exp(-d2 / (2.0 * sigma[None, :] ** 2))).sum(axis=1)
    return rng.poisson(rate)


class SyntheticSource:
    name = "synthetic"
    label = SYNTHETIC_LABEL

    def __init__(self, data_dir: Path, graph=None):
        self.data_dir = Path(data_dir)
        self.graph = graph

    def as_of(self) -> date:
        return SYNTHETIC_AS_OF

    def _nodes(self) -> pd.DataFrame:
        if self.graph is not None:
            g = self.graph
            return pd.DataFrame({"node_id": np.arange(g.n_nodes), "lat": g.node_lat, "lon": g.node_lon,
                                 "x": g.node_x, "y": g.node_y})
        path = self.data_dir / "build" / "graph" / "nodes.parquet"
        if not path.exists():
            raise FileNotFoundError("graph not built: run python -m scripts.routing.build_graph first")
        return pd.read_parquet(path).sort_values("node_id")

    def load(self, bbox, categories: list[str] | None) -> pd.DataFrame:
        cfg = category_config()
        w, s, e, n = bbox
        nodes = self._nodes()
        nodes = nodes[nodes["lat"].between(s, n) & nodes["lon"].between(w, e)].reset_index(drop=True)

        rng = np.random.default_rng([C.SEED, 1])
        counts = synthetic_counts(nodes["x"].to_numpy(float), nodes["y"].to_numpy(float), rng)
        keep = counts >= 1
        nodes, counts = nodes[keep].reset_index(drop=True), counts[keep]

        probs = np.asarray(cfg.synthetic_weights, float)
        split = rng.multinomial(counts, probs / probs.sum())   # (n_locations, n_categories)

        wanted = set(categories) if categories else set(cfg.categories)
        end = self.as_of()
        start = end - timedelta(days=C.WINDOW_DAYS)
        rows = [(f"syn-{int(node.node_id)}", float(node.lat), float(node.lon), cat, int(split[i, k]), start, end)
                for i, node in enumerate(nodes.itertuples(index=False))
                for k, cat in enumerate(cfg.categories)
                if split[i, k] >= 1 and cat in wanted]
        df = pd.DataFrame(rows, columns=SOURCE_COLUMNS)
        df["count"] = df["count"].astype("int64")
        return df
