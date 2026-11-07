"""Convert point hazards into blocked graph edges and place demo points."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from shapely.geometry import Point

from .graph import Graph, utm_to_latlon


def hazard_edges(graph: Graph, lat: float, lon: float, radius_m: float) -> np.ndarray:
    if not np.isfinite([lat, lon, radius_m]).all() or radius_m < 0:
        raise ValueError("hazard coordinate and radius must be finite; radius must be non-negative")
    x, y = graph.to_utm(float(lat), float(lon))
    point = Point(x, y)
    affected = np.asarray(graph.edge_tree.query(point.buffer(float(radius_m)), predicate="intersects"), dtype=np.int32)
    if affected.size == 0 and graph.n_edges:
        nearest = int(graph.edge_tree.nearest(point))
        if float(graph.edge_geom_utm[nearest].distance(point)) <= 50.0:
            affected = np.asarray([nearest], dtype=np.int32)
    return np.unique(affected).astype(np.int32, copy=False)


def point_along_route(graph: Graph, edge_ids: Sequence[int], fraction: float) -> tuple[float, float]:
    """Return the WGS84 (lat, lon) point at a fraction of the route length."""
    edges = np.asarray(edge_ids, dtype=np.int32)
    if not edges.size:
        raise ValueError("cannot place a point on an empty route")
    if not np.isfinite(fraction):
        raise ValueError("fraction must be finite")
    fraction = float(np.clip(fraction, 0.0, 1.0))
    lengths = np.asarray([graph.edge_geom_utm[int(edge_id)].length for edge_id in edges], dtype=np.float64)
    total = float(lengths.sum())
    if total <= 0:
        raise ValueError("route has no measurable length")

    if edges.size > 1:
        u0, v0 = int(graph.edge_u[edges[0]]), int(graph.edge_v[edges[0]])
        next_ends = {int(graph.edge_u[edges[1]]), int(graph.edge_v[edges[1]])}
        shared = next_ends.intersection({u0, v0})
        current = v0 if u0 in shared else u0
    else:
        current = int(graph.edge_u[edges[0]])
    forwards: list[bool] = []
    for edge_id in edges:
        u, v = int(graph.edge_u[edge_id]), int(graph.edge_v[edge_id])
        if current == u:
            forwards.append(True)
            current = v
        elif current == v:
            forwards.append(False)
            current = u
        else:
            raise ValueError("edge ids do not form a contiguous route")

    remaining = total * fraction
    idx = len(edges) - 1
    distance = float(lengths[-1])
    for i, length in enumerate(lengths):
        if remaining <= length:
            idx, distance = i, remaining
            break
        remaining -= float(length)
    if not forwards[idx]:
        distance = float(lengths[idx]) - distance
    point = graph.edge_geom_utm[int(edges[idx])].interpolate(distance)
    lat, lon = utm_to_latlon(point.x, point.y)
    return float(lat), float(lon)
