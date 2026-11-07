"""Hazard-to-edge mapping (spec A3.7). Phase 3: real implementation by H29."""
from __future__ import annotations

import numpy as np

from waykin.routing.graph import Graph


def hazard_edges(graph: Graph, lat: float, lon: float, radius_m: float) -> np.ndarray:
    raise NotImplementedError("hazard_edges arrives in Phase 3 (H29)")


def point_along_route(graph: Graph, edge_ids: np.ndarray, fraction: float) -> tuple[float, float]:
    raise NotImplementedError("point_along_route arrives in Phase 3 (H29)")
