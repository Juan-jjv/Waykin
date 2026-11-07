"""Route geometry and plain-language exposure explanations."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np

from .graph import Graph


def route_geometry(graph: Graph, node_ids: Sequence[int], edge_ids: Sequence[int]) -> list[list[float]]:
    """Return a Leaflet-friendly ``[[lat, lon], ...]`` route polyline."""
    nodes = np.asarray(node_ids, dtype=np.int32)
    edges = np.asarray(edge_ids, dtype=np.int32)
    if len(nodes) != len(edges) + 1:
        raise ValueError("a route must have exactly one more node than edge")
    result: list[list[float]] = []
    for index, edge_id in enumerate(edges):
        coords = np.asarray(graph.edge_coords_latlon[int(edge_id)], dtype=np.float64)
        if nodes[index] == graph.edge_v[edge_id] and nodes[index + 1] == graph.edge_u[edge_id]:
            coords = coords[::-1]
        elif not (nodes[index] == graph.edge_u[edge_id] and nodes[index + 1] == graph.edge_v[edge_id]):
            raise ValueError("edge path is not contiguous with node path")
        points = coords.tolist()
        if result and points and np.allclose(result[-1], points[0], atol=1e-7):
            points = points[1:]
        result.extend([[float(lat), float(lon)] for lat, lon in points])
    if not edges.size:
        node = int(nodes[0])
        return [[float(graph.node_lat[node]), float(graph.node_lon[node])]]
    return result


def _join_coords(first: list[list[float]], second: list[list[float]]) -> list[list[float]]:
    if first and second and np.allclose(first[-1], second[0], atol=1e-7):
        return first + second[1:]
    return first + second


def top_segments(
    graph: Graph,
    edge_ids: Sequence[int],
    exposure_mean: Sequence[float] | np.ndarray,
    k: int = 3,
) -> list[dict[str, Any]]:
    """Return the largest attributed street segments, merging adjacent names."""
    path_edges = np.asarray(edge_ids, dtype=np.int32)
    values = np.asarray(exposure_mean, dtype=np.float64)
    if values.shape != (graph.n_edges,):
        raise ValueError("exposure_mean must have one value per graph edge")
    if k <= 0 or path_edges.size == 0:
        return []
    ranked = sorted(
        (int(edge_id) for edge_id in path_edges if values[edge_id] > 0),
        key=lambda edge_id: (-float(values[edge_id]), edge_id),
    )[:k]
    selected = set(ranked)
    # Recover path direction from adjacent edges so joined geometry follows the
    # route even when an OSM edge is traversed opposite to its stored direction.
    starts: list[int] = []
    if path_edges.size > 1:
        first_u, first_v = int(graph.edge_u[path_edges[0]]), int(graph.edge_v[path_edges[0]])
        next_ends = {int(graph.edge_u[path_edges[1]]), int(graph.edge_v[path_edges[1]])}
        shared = next_ends.intersection({first_u, first_v})
        starts.append(first_v if first_u in shared else first_u)
    elif path_edges.size:
        starts.append(int(graph.edge_u[path_edges[0]]))
    traversal: list[tuple[int, int]] = []
    current = starts[0] if starts else -1
    for edge_id in path_edges:
        u, v = int(graph.edge_u[edge_id]), int(graph.edge_v[edge_id])
        if current == u:
            traversal.append((u, v))
            current = v
        elif current == v:
            traversal.append((v, u))
            current = u
        else:
            traversal.append((u, v))
            current = v
    position = {int(edge_id): index for index, edge_id in enumerate(path_edges)}
    groups: list[dict[str, Any]] = []
    for edge_id in path_edges:
        edge_id = int(edge_id)
        if edge_id not in selected:
            continue
        name = graph.edge_name[edge_id]
        idx = position[edge_id]
        coords = np.asarray(graph.edge_coords_latlon[edge_id], dtype=np.float64)
        if traversal[idx][0] == int(graph.edge_v[edge_id]):
            coords = coords[::-1]
        coords_list = [[float(lat), float(lon)] for lat, lon in coords]
        previous_is_adjacent = bool(groups and position[groups[-1]["edge_ids"][-1]] == idx - 1)
        if groups and previous_is_adjacent and name is not None and groups[-1]["name"] == name:
            groups[-1]["edge_ids"].append(edge_id)
            groups[-1]["attributed"] += float(values[edge_id])
            groups[-1]["geometry"] = _join_coords(groups[-1]["geometry"], coords_list)
        else:
            groups.append({"edge_id": edge_id, "edge_ids": [edge_id], "name": name, "attributed": float(values[edge_id]), "geometry": coords_list})
    groups.sort(key=lambda item: (-item["attributed"], item["edge_id"]))
    return groups[:k]


def explanation_text(label: str, minutes: float, extra_min: float, diff_p50: float | None, p50: float) -> str:
    """Build the API's short explanation: counts only, never a judgment about the route."""
    import math
    from waykin import constants as C

    whole = lambda value: int(math.floor(float(value) + 0.5))
    if label == "fastest":
        return f"Fastest option, {whole(minutes)} min. About {p50:.1f} {C.UNITS_SHORT}."
    if diff_p50 is not None and diff_p50 < 0:
        return (f"+{whole(extra_min)} min vs fastest. About {abs(diff_p50):.1f} fewer reported incidents "
                "attributed to segments along this route (90 days).")
    return f"+{whole(extra_min)} min vs fastest. About the same number of reported incidents."
