"""Seeded random trips for the offline measurements (spec A2.8)."""
from __future__ import annotations

import numpy as np

from waykin import constants as C


def sample_trips(graph, n: int, seed_tag: int = 4, min_m: float = 800.0, max_m: float = 3000.0,
                 bbox=C.DEMO_BBOX, max_tries: int = 200_000) -> list[tuple[int, int]]:
    """Node pairs inside bbox whose straight-line distance is in [min_m, max_m]. Deterministic."""
    w, s, e, north = bbox
    inside = np.flatnonzero((graph.node_lat >= s) & (graph.node_lat <= north) & (graph.node_lon >= w) & (graph.node_lon <= e))
    if len(inside) < 2:
        return []
    rng = np.random.default_rng([C.SEED, seed_tag])
    trips: list[tuple[int, int]] = []
    for _ in range(max_tries):
        if len(trips) == n:
            break
        a, b = rng.choice(inside, size=2, replace=False)
        if min_m <= float(np.hypot(graph.node_x[a] - graph.node_x[b], graph.node_y[a] - graph.node_y[b])) <= max_m:
            trips.append((int(a), int(b)))
    return trips
