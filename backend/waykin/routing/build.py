"""Offline graph build from OpenStreetMap (needs the `build` extra and network access).

Run it through `python -m scripts.routing.build_graph`. Never imported by the server.
"""
from __future__ import annotations

import math
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import shapely
from shapely.geometry import LineString

from waykin import constants as C
from waykin.routing.graph import assemble_graph, utm_to_latlon, write_artifacts


def padded_bbox(bbox=C.DEMO_BBOX, pad_m: float = C.GRAPH_PAD_M) -> tuple[float, float, float, float]:
    w, s, e, n = bbox
    dlat = pad_m / 111_320.0
    dlon = pad_m / (111_320.0 * math.cos(math.radians((s + n) / 2)))
    return (w - dlon, s - dlat, e + dlon, n + dlat)


def _download(ox, bbox):
    w, s, e, n = bbox
    major = int(ox.__version__.split(".")[0])
    if major >= 2:
        return ox.graph_from_bbox(bbox=(w, s, e, n), network_type="walk", simplify=True)
    return ox.graph_from_bbox(n, s, e, w, network_type="walk", simplify=True)  # osmnx 1.x signature


def _undirected_largest(ox, G):
    major = int(ox.__version__.split(".")[0])
    if major >= 2:
        G = ox.convert.to_undirected(G)
        return ox.truncate.largest_component(G, strongly=False)
    G = ox.utils_graph.get_undirected(G)
    return ox.utils_graph.get_largest_component(G, strongly=False)


def build(out_dir: Path, bbox=C.DEMO_BBOX) -> dict:
    import osmnx as ox

    t0 = time.time()
    out_dir = Path(out_dir)
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(out_dir / "osm_cache")
    pbox = padded_bbox(bbox)

    G = _download(ox, pbox)
    G = ox.project_graph(G, to_crs=C.CRS_METRIC)
    G = _undirected_largest(ox, G)

    # Collapse parallel edges (keep the shortest) and drop self-loops.
    best: dict[tuple, tuple] = {}
    for a, b, data in G.edges(data=True):
        if a == b:
            continue
        key = (a, b) if str(a) < str(b) else (b, a)
        length = float(data.get("length", 0.0))
        if key not in best or length < best[key][0]:
            best[key] = (length, a, b, data)

    used = sorted({x for k in best for x in k}, key=str)
    idx = {osm: i for i, osm in enumerate(used)}
    node_x = np.array([G.nodes[o]["x"] for o in used], float)
    node_y = np.array([G.nodes[o]["y"] for o in used], float)
    node_lat, node_lon = (np.asarray(t) for t in utm_to_latlon(node_x, node_y))

    u, v, lengths, names, geoms, coords = [], [], [], [], [], []
    for length, a, b, data in best.values():
        ia, ib = idx[a], idx[b]
        geom = data.get("geometry")
        if geom is None:
            geom = LineString([(node_x[ia], node_y[ia]), (node_x[ib], node_y[ib])])
        # Orient u→v: the first vertex must be at node a.
        first = np.asarray(geom.coords[0])
        if np.hypot(*(first - [node_x[ia], node_y[ia]])) > np.hypot(*(first - [node_x[ib], node_y[ib]])):
            geom = shapely.reverse(geom)
        name = data.get("name")
        if isinstance(name, list):
            name = " / ".join(str(x) for x in name)
        xy = np.asarray(geom.coords)
        lat, lon = utm_to_latlon(xy[:, 0], xy[:, 1])
        u.append(ia), v.append(ib), lengths.append(max(length, geom.length))
        names.append(name if isinstance(name, str) else None)
        geoms.append(geom)
        coords.append(np.column_stack([lat, lon]))

    g = assemble_graph(node_lat, node_lon, node_x, node_y, u, v, lengths, names, geoms, coords, bbox=pbox)
    write_artifacts(g, out_dir, {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "osmnx_version": ox.__version__,
        "demo_bbox": list(bbox), "pad_m": C.GRAPH_PAD_M,
    })
    return {"n_nodes": g.n_nodes, "n_edges": g.n_edges, "graph_hash": g.graph_hash,
            "seconds": round(time.time() - t0, 1)}
