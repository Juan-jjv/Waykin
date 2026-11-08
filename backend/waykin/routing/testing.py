"""Test helpers used by every agent's tests. No network access."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import shapely

from waykin.routing.graph import Graph, assemble_graph, latlon_to_utm, utm_to_latlon, write_artifacts


def make_grid_graph(n: int = 12, spacing_m: float = 100.0, sw_latlon=(53.515, -113.525), drive_kmh: float | None = None) -> Graph:
    """An n×n grid of streets `spacing_m` apart, south-west corner at `sw_latlon`.

    Every street is walkable; with `drive_kmh` every street is also drivable both ways at that speed.

    Rows are "Test Ave 1..n" (west-east), columns are "Test St 1..n" (south-north).
    Node id = row * n + col.
    """
    x0, y0 = latlon_to_utm(*sw_latlon)
    cols, rows = np.meshgrid(np.arange(n), np.arange(n))
    node_x = (x0 + cols.ravel() * spacing_m).astype(float)
    node_y = (y0 + rows.ravel() * spacing_m).astype(float)
    node_lat, node_lon = utm_to_latlon(node_x, node_y)
    node_lat, node_lon = np.asarray(node_lat), np.asarray(node_lon)

    u, v, names = [], [], []
    for r in range(n):
        for c in range(n):
            a = r * n + c
            if c + 1 < n:
                u.append(a), v.append(a + 1), names.append(f"Test Ave {r + 1}")
            if r + 1 < n:
                u.append(a), v.append(a + n), names.append(f"Test St {c + 1}")
    u, v = np.array(u, dtype=np.int32), np.array(v, dtype=np.int32)
    geoms = shapely.linestrings(np.stack([np.column_stack([node_x[u], node_y[u]]),
                                          np.column_stack([node_x[v], node_y[v]])], axis=1))
    coords = [np.array([[node_lat[a], node_lon[a]], [node_lat[b], node_lon[b]]]) for a, b in zip(u, v)]
    lengths = np.full(len(u), float(spacing_m))
    bbox = (float(node_lon.min()), float(node_lat.min()), float(node_lon.max()), float(node_lat.max()))
    drive = {}
    if drive_kmh is not None:
        drive = {"edge_drive_fwd": np.ones(len(u), bool), "edge_drive_rev": np.ones(len(u), bool),
                 "edge_drive_kmh": np.full(len(u), float(drive_kmh))}
    return assemble_graph(node_lat, node_lon, node_x, node_y, u, v, lengths, names, geoms, coords, bbox=bbox, **drive)


def write_graph_artifacts(graph: Graph, out_dir: Path) -> None:
    """Write the same files as the real build, so other build scripts can run in CI."""
    write_artifacts(graph, out_dir, {"built_at": "test", "osmnx_version": None})
