"""Shared internal types for the routing package.

These are deliberately independent from FastAPI/Pydantic response models so
the graph and search code can be used by the offline builder and test helpers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from hashlib import blake2b
from typing import Any, Sequence

import numpy as np
from scipy.sparse import csr_matrix
from scipy.spatial import cKDTree


class RoutingError(ValueError):
    """Base class for errors that the HTTP layer maps to API error codes."""


class OutsideAreaError(RoutingError):
    """A requested coordinate is outside the supported graph area."""

    def __init__(self) -> None:
        super().__init__("outside_area")


class NoPathError(RoutingError):
    """No walkable path exists between the snapped endpoints."""


@dataclass(slots=True)
class Graph:
    """In-memory, reindexed walking graph and its spatial indexes.

    Edge geometries are oriented from ``edge_u[e]`` to ``edge_v[e]``.
    ``csr_edge_id`` maps every directed CSR entry back to its undirected edge.
    """

    node_ids: np.ndarray
    node_x: np.ndarray
    node_y: np.ndarray
    node_latlon: np.ndarray  # shape (n_nodes, 2), columns lat, lon
    edge_u: np.ndarray
    edge_v: np.ndarray
    edge_length_m: np.ndarray
    edge_minutes: np.ndarray
    edge_names: tuple[str | None, ...]
    edge_geom_utm: tuple[Any, ...]
    edge_coords_latlon: tuple[np.ndarray, ...]
    indices: np.ndarray
    indptr: np.ndarray
    csr_edge_id: np.ndarray
    csr_minutes: csr_matrix
    graph_hash: str
    demo_bbox: tuple[float, float, float, float]  # west, south, east, north
    metric_transformer: Any = field(repr=False)
    node_tree: cKDTree = field(repr=False)
    edge_tree: Any = field(repr=False)

    @property
    def n_nodes(self) -> int:
        return int(self.node_x.size)

    @property
    def n_edges(self) -> int:
        return int(self.edge_u.size)

    def snap(self, lat: float, lon: float, max_distance_m: float = 150.0) -> int:
        """Snap a WGS84 point to the nearest graph node, returning its index."""
        west, south, east, north = self.demo_bbox
        if not (south <= lat <= north and west <= lon <= east):
            raise OutsideAreaError()
        x, y = self.metric_transformer.transform(lon, lat)
        distance, node = self.node_tree.query((x, y), k=1)
        if distance > max_distance_m:
            raise OutsideAreaError()
        return int(node)


@dataclass(slots=True)
class RouteCandidate:
    """A unique path and its deterministic summary values."""

    route_id: str
    node_ids: np.ndarray
    edge_ids: np.ndarray
    minutes: float
    distance_m: float
    exposure_mean: float
    label: str = ""


@dataclass(slots=True)
class RouteSet:
    """Fastest, useful alternatives, and the best over-cap alternative."""

    fastest: RouteCandidate
    lower_exposure: RouteCandidate | None
    balanced: RouteCandidate | None
    uncapped: RouteCandidate | None
    candidates: tuple[RouteCandidate, ...]


def route_id(edge_ids: Sequence[int] | np.ndarray) -> str:
    """Stable compact identifier for an ordered edge path."""
    ids = np.asarray(edge_ids, dtype=np.int32)
    return blake2b(ids.tobytes(), digest_size=12).hexdigest()
