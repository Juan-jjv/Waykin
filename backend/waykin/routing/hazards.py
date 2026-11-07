"""Map point hazards to graph edges and place deterministic demo hazards."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from pyproj import Transformer
from shapely.geometry import Point

from .types import Graph


def hazard_edges(graph: Graph, lat: float, lon: float, radius_m: float) -> np.ndarray:
    """Find edges intersecting a metric-radius hazard; return sorted edge ids."""
    if not np.isfinite([lat, lon, radius_m]).all() or radius_m < 0:
        raise ValueError("hazard coordinate and radius must be finite; radius must be non-negative")
    x, y = graph.metric_transformer.transform(float(lon), float(lat))
    point = Point(x, y)
    affected = np.asarray(graph.edge_tree.query(point.buffer(float(radius_m)), predicate="intersects"), dtype=np.int32)
    if affected.size == 0 and graph.n_edges:
        nearest = int(graph.edge_tree.nearest(point))
        if float(graph.edge_geom_utm[nearest].distance(point)) <= 50.0:
            affected = np.asarray([nearest], dtype=np.int32)
    return np.unique(affected).astype(np.int32, copy=False)


def point_along_route(graph: Graph, edge_ids: Sequence[int], fraction: float) -> tuple[float, float]:
    """Return ``(lat, lon)`` at a fraction of total route length."""
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
    # Infer the traversal direction of each undirected edge from its neighbor.
    if edges.size > 1:
        first_u, first_v = int(graph.edge_u[edges[0]]), int(graph.edge_v[edges[0]])
        second_ends = {int(graph.edge_u[edges[1]]), int(graph.edge_v[edges[1]])}
        shared = second_ends.intersection({first_u, first_v})
        current = first_v if first_u in shared else first_u
    else:
        current = int(graph.edge_u[edges[0]])
    forward: list[bool] = []
    for edge_id in edges:
        u, v = int(graph.edge_u[edge_id]), int(graph.edge_v[edge_id])
        if current == u:
            forward.append(True)
            current = v
        elif current == v:
            forward.append(False)
            current = u
        else:
            raise ValueError("edge ids do not form a contiguous route")

    remaining = total * fraction
    selected_index = len(edges) - 1
    distance = float(lengths[-1])
    for index, length in enumerate(lengths):
        if remaining <= length:
            selected_index, distance = index, remaining
            break
        remaining -= float(length)
    selected = int(edges[selected_index])
    if not forward[selected_index]:
        distance = float(lengths[selected_index]) - distance
    point = graph.edge_geom_utm[selected].interpolate(distance)
    inverse = Transformer.from_crs(graph.metric_transformer.target_crs, "EPSG:4326", always_xy=True)
    lon, lat = inverse.transform(point.x, point.y)
    return float(lat), float(lon)
