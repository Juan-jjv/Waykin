"""Deterministic, network-free graph fixtures shared by backend agents."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from pyproj import Transformer
from shapely.geometry import LineString

from .build import CRS_METRIC, graph_from_records, save_graph
from .types import Graph


def make_grid_graph(
    n: int = 6,
    spacing_m: float = 100.0,
    sw_latlon: tuple[float, float] = (53.52, -113.50),
) -> Graph:
    """Build an ``n`` by ``n`` connected grid around a southwest lat/lon."""
    if n < 2:
        raise ValueError("n must be at least 2")
    if not np.isfinite(spacing_m) or spacing_m <= 0:
        raise ValueError("spacing_m must be positive and finite")
    sw_lat, sw_lon = map(float, sw_latlon)
    forward = Transformer.from_crs("EPSG:4326", CRS_METRIC, always_xy=True)
    inverse = Transformer.from_crs(CRS_METRIC, "EPSG:4326", always_xy=True)
    x0, y0 = forward.transform(sw_lon, sw_lat)
    node_x = np.asarray([x0 + col * spacing_m for row in range(n) for col in range(n)], dtype=np.float64)
    node_y = np.asarray([y0 + row * spacing_m for row in range(n) for col in range(n)], dtype=np.float64)
    lon, lat = inverse.transform(node_x, node_y)
    node_latlon = np.column_stack((lat, lon))
    edge_u: list[int] = []
    edge_v: list[int] = []
    lengths: list[float] = []
    names: list[str] = []
    geometries: list[LineString] = []
    coords_latlon: list[np.ndarray] = []
    for row in range(n):
        for col in range(n):
            u = row * n + col
            for nr, nc, name in ((row, col + 1, f"Test Ave {row + 1}"), (row + 1, col, f"Test St {col + 1}")):
                if nr >= n or nc >= n:
                    continue
                v = nr * n + nc
                edge_u.append(u)
                edge_v.append(v)
                lengths.append(float(spacing_m))
                names.append(name)
                geom = LineString([(node_x[u], node_y[u]), (node_x[v], node_y[v])])
                geometries.append(geom)
                glon, glat = inverse.transform(*np.asarray(geom.coords).T)
                coords_latlon.append(np.column_stack((glat, glon)))
    # A small padded bbox keeps fixture snaps valid while matching the production API.
    min_lat, max_lat = float(node_latlon[:, 0].min()), float(node_latlon[:, 0].max())
    min_lon, max_lon = float(node_latlon[:, 1].min()), float(node_latlon[:, 1].max())
    pad_lat = spacing_m * 2 / 111_000
    pad_lon = spacing_m * 2 / max(111_000 * np.cos(np.deg2rad(sw_lat)), 1)
    return graph_from_records(
        node_x, node_y, node_latlon, np.asarray(edge_u), np.asarray(edge_v),
        np.asarray(lengths), tuple(names), tuple(geometries), tuple(coords_latlon),
        (min_lon - pad_lon, min_lat - pad_lat, max_lon + pad_lon, max_lat + pad_lat),
    )


def write_graph_artifacts(graph: Graph, graph_dir: str | Path) -> dict[str, object]:
    """Write fixture artifacts in exactly the production graph format."""
    return save_graph(graph, graph_dir)
