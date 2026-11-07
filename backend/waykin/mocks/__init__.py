"""Mock mode (WAYKIN_MOCK=1): JSON fixtures for meta, incidents, routes and a scripted closure.

Route fixture choice, so A1 can test both paths:
    floor(lat * 10_000) even -> routes_recommend.json   (e.g. lat 53.5200)
    floor(lat * 10_000) odd  -> routes_abstain.json     (e.g. lat 53.5201)
`lat` is origin.lat for /routes and position.lat for /routes/reroute. If an active hazard
blocks an edge of the chosen fixture's fastest route, routes_rerouted.json is served instead.
"""

from __future__ import annotations

import json
import math
from functools import cache
from pathlib import Path
from typing import Any

import numpy as np

MOCK_DIR = Path(__file__).resolve().parent
MOCK_N_EDGES = 4000


@cache
def _load(name: str) -> Any:
    return json.loads((MOCK_DIR / f"{name}.json").read_text())


def load(name: str) -> Any:
    """A fresh deep copy of a fixture; callers may mutate it."""
    return json.loads(json.dumps(_load(name)))


def route_fixture_name(lat: float, blocked: set[int]) -> str:
    name = "routes_recommend" if math.floor(lat * 10_000) % 2 == 0 else "routes_abstain"
    fastest = _load(name)["routes"][0]
    if blocked & set(fastest["edge_ids"]):
        return "routes_rerouted"
    return name


@cache
def _edge_midpoints() -> tuple[np.ndarray, np.ndarray]:
    ids, pts = [], []
    for name in ("routes_recommend", "routes_abstain", "routes_rerouted"):
        for r in _load(name)["routes"]:
            g = r["geometry"]
            for k, e in enumerate(r["edge_ids"]):
                ids.append(e)
                pts.append(((g[k][0] + g[k + 1][0]) / 2, (g[k][1] + g[k + 1][1]) / 2))
    ids_a, idx = np.unique(np.asarray(ids, dtype=np.int32), return_index=True)
    return ids_a, np.asarray(pts, dtype=float)[idx]


def mock_hazard_edges(lat: float, lon: float, radius_m: float) -> np.ndarray:
    """Stand-in for routing.hazards.hazard_edges over the fixture routes (edge length ~100 m)."""
    ids, pts = _edge_midpoints()
    dy = (pts[:, 0] - lat) * 111_320.0
    dx = (pts[:, 1] - lon) * 111_320.0 * math.cos(math.radians(lat))
    return ids[np.hypot(dx, dy) <= radius_m + 50.0].astype(np.int32)
