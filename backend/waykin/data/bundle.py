"""ExposureBundle (spec B4) and the in-memory synthetic bundle every agent's tests use."""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal

import numpy as np
import pandas as pd
import scipy.sparse as sp

from waykin import constants as C
from waykin.data.montecarlo import simulate

SYNTHETIC_LABEL = "Synthetic data (demo)"
SYNTHETIC_AS_OF = date(2026, 10, 31)
TEST_CATEGORIES = ["assault", "robbery", "break_and_enter", "theft_from_vehicle", "theft"]
_TEST_CATEGORY_PROBS = np.array([0.15, 0.05, 0.2, 0.3, 0.3])


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


def load_exposure(build_dir: Path, source: str, radii: list[int], expected_graph_hash: str) -> ExposureBundle:
    raise NotImplementedError("load_exposure arrives in Phase 2 (H21); use make_synthetic_bundle_for_tests")


def _incident_edge_allocation(graph, node_ids: np.ndarray) -> sp.csr_matrix:
    """Crude allocation for tests only: each node's count is split equally over the edges touching it.
    The real build uses allocation.build_allocation (length inside a radius)."""
    rows, cols = [], []
    for i, n in enumerate(node_ids):
        touching = np.flatnonzero((graph.edge_u == n) | (graph.edge_v == n))
        rows.extend([i] * len(touching))
        cols.extend(touching.tolist())
    rows, cols = np.array(rows), np.array(cols)
    deg = np.bincount(rows, minlength=len(node_ids))
    A = sp.csr_matrix((1.0 / deg[rows], (rows, cols)), shape=(len(node_ids), graph.n_edges))
    return A


def make_synthetic_bundle_for_tests(graph, radii=(100,)) -> ExposureBundle:
    """In-memory, deterministic, no files. A few Gaussian hotspots over graph nodes, Poisson counts."""
    rng = np.random.default_rng([C.SEED, 1])
    n_hot = 3
    hot = rng.choice(graph.n_nodes, size=n_hot, replace=False)
    sigma = rng.uniform(150, 300, n_hot)
    amp = rng.uniform(2, 8, n_hot)
    d2 = (graph.node_x[:, None] - graph.node_x[hot][None, :]) ** 2 + (graph.node_y[:, None] - graph.node_y[hot][None, :]) ** 2
    rate = 0.05 + (amp[None, :] * np.exp(-d2 / (2 * sigma[None, :] ** 2))).sum(1)
    counts_all = rng.poisson(rate)

    published = np.flatnonzero(counts_all >= 1)
    prior = np.flatnonzero(counts_all == 0)  # on the test grid every other node is > PRIOR_NODE_MIN_GAP_M away
    by_cat = [rng.multinomial(int(c), _TEST_CATEGORY_PROBS) for c in counts_all[published]]
    locations = pd.DataFrame({
        "location_id": [f"syn-{n}" for n in published],
        "lat": graph.node_lat[published], "lon": graph.node_lon[published],
        "count": counts_all[published].astype(int),
        "counts_by_category": [json.dumps({k: int(v) for k, v in zip(TEST_CATEGORIES, bc) if v}) for bc in by_cat],
    })

    rows = np.concatenate([published, prior])
    counts = np.concatenate([counts_all[published], np.zeros(len(prior))]).astype(float)
    A = _incident_edge_allocation(graph, rows)
    X, mean, observed = {}, {}, {}
    for r in radii:
        X[r] = simulate(A, counts, radius_m=int(r))
        mean[r] = X[r].mean(axis=1)
        observed[r] = np.asarray(A.T @ counts, dtype=np.float32)
    return ExposureBundle(source="synthetic", source_label=SYNTHETIC_LABEL, as_of=SYNTHETIC_AS_OF,
                          window_days=C.WINDOW_DAYS, category_preset="all", categories=list(TEST_CATEGORIES),
                          radii=[int(r) for r in radii], X=X, mean=mean, observed=observed, locations=locations)
