"""Build, persist, and load the offline walking graph artifacts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from pyproj import Transformer
from scipy.sparse import csr_matrix
from scipy.spatial import cKDTree
from shapely import from_wkb, to_wkb
from shapely.geometry import LineString
from shapely.strtree import STRtree

from .types import Graph

try:
    from waykin import constants as _constants
except ImportError:
    _constants = None

CRS_METRIC = getattr(_constants, "CRS_METRIC", "EPSG:32612")
DEMO_BBOX = getattr(_constants, "DEMO_BBOX", (-113.56, 53.50, -113.45, 53.57))
MIN_EDGE_MINUTES = getattr(_constants, "MIN_EDGE_MINUTES", 0.001)
WALK_SPEED_M_PER_MIN = getattr(_constants, "WALK_SPEED_M_PER_MIN", 80.0)

ARTIFACT_VERSION = 1


def _oriented_coords(line: LineString, start: tuple[float, float], end: tuple[float, float]) -> list[tuple[float, float]]:
    coords = list(line.coords)
    if not coords:
        return [start, end]
    direct = np.hypot(coords[0][0] - start[0], coords[0][1] - start[1]) + np.hypot(coords[-1][0] - end[0], coords[-1][1] - end[1])
    reverse = np.hypot(coords[-1][0] - start[0], coords[-1][1] - start[1]) + np.hypot(coords[0][0] - end[0], coords[0][1] - end[1])
    return coords if direct <= reverse else coords[::-1]


def graph_from_records(
    node_x: np.ndarray,
    node_y: np.ndarray,
    node_latlon: np.ndarray,
    edge_u: np.ndarray,
    edge_v: np.ndarray,
    edge_length_m: np.ndarray,
    edge_names: tuple[str | None, ...],
    edge_geom_utm: tuple[Any, ...],
    edge_coords_latlon: tuple[np.ndarray, ...],
    demo_bbox: tuple[float, float, float, float],
    graph_hash: str = "",
) -> Graph:
    """Construct a Graph and aligned symmetric CSR from canonical arrays."""
    node_x = np.asarray(node_x, dtype=np.float64)
    node_y = np.asarray(node_y, dtype=np.float64)
    node_latlon = np.asarray(node_latlon, dtype=np.float64).reshape((-1, 2))
    edge_u = np.asarray(edge_u, dtype=np.int32)
    edge_v = np.asarray(edge_v, dtype=np.int32)
    edge_length_m = np.asarray(edge_length_m, dtype=np.float64)
    if not (edge_u.size == edge_v.size == edge_length_m.size == len(edge_names) == len(edge_geom_utm) == len(edge_coords_latlon)):
        raise ValueError("edge arrays must have the same length")
    speed = max(float(WALK_SPEED_M_PER_MIN), 1e-9)
    minutes = np.maximum(edge_length_m / speed, float(MIN_EDGE_MINUTES))
    n_nodes = node_x.size
    rows = np.concatenate((edge_u, edge_v))
    cols = np.concatenate((edge_v, edge_u))
    csr_edges = np.concatenate((np.arange(edge_u.size, dtype=np.int32), np.arange(edge_u.size, dtype=np.int32)))
    csr_data = np.concatenate((minutes, minutes))
    order = np.lexsort((cols, rows))
    rows, cols, csr_edges, csr_data = rows[order], cols[order], csr_edges[order], csr_data[order]
    indptr = np.zeros(n_nodes + 1, dtype=np.int64)
    np.add.at(indptr, rows + 1, 1)
    np.cumsum(indptr, out=indptr)
    matrix = csr_matrix((csr_data, cols, indptr), shape=(n_nodes, n_nodes))
    transformer = Transformer.from_crs("EPSG:4326", CRS_METRIC, always_xy=True)
    tree = cKDTree(np.column_stack((node_x, node_y)))
    return Graph(
        node_ids=np.arange(n_nodes, dtype=np.int32),
        node_x=node_x,
        node_y=node_y,
        node_latlon=node_latlon,
        edge_u=edge_u,
        edge_v=edge_v,
        edge_length_m=edge_length_m,
        edge_minutes=minutes,
        edge_names=edge_names,
        edge_geom_utm=edge_geom_utm,
        edge_coords_latlon=edge_coords_latlon,
        indices=cols.astype(np.int32, copy=False),
        indptr=indptr,
        csr_edge_id=csr_edges.astype(np.int32, copy=False),
        csr_minutes=matrix,
        graph_hash=graph_hash,
        demo_bbox=tuple(map(float, demo_bbox)),
        metric_transformer=transformer,
        node_tree=tree,
        edge_tree=STRtree(list(edge_geom_utm)),
    )


def save_graph(graph: Graph, graph_dir: str | Path) -> dict[str, Any]:
    """Write reproducible Parquet/NPZ artifacts and a validating manifest."""
    target = Path(graph_dir)
    target.mkdir(parents=True, exist_ok=True)
    nodes_path = target / "nodes.parquet"
    edges_path = target / "edges.parquet"
    csr_path = target / "graph_csr.npz"
    node_frame = pd.DataFrame({
        "node_id": graph.node_ids,
        "x": graph.node_x,
        "y": graph.node_y,
        "lat": graph.node_latlon[:, 0],
        "lon": graph.node_latlon[:, 1],
    })
    edge_frame = pd.DataFrame({
        "edge_id": np.arange(graph.n_edges, dtype=np.int32),
        "u": graph.edge_u,
        "v": graph.edge_v,
        "length_m": graph.edge_length_m,
        "minutes": graph.edge_minutes,
        "name": list(graph.edge_names),
        "geometry_wkb": [to_wkb(geom) for geom in graph.edge_geom_utm],
        "coords_latlon": [json.dumps(np.asarray(coords, dtype=float).tolist(), separators=(",", ":")) for coords in graph.edge_coords_latlon],
    })
    node_frame.to_parquet(nodes_path, index=False)
    edge_frame.to_parquet(edges_path, index=False)
    np.savez_compressed(csr_path, indices=graph.indices, indptr=graph.indptr, csr_edge_id=graph.csr_edge_id)
    digest = _artifact_digest((nodes_path, edges_path, csr_path))
    manifest = {
        "artifact_version": ARTIFACT_VERSION,
        "crs_metric": str(CRS_METRIC),
        "demo_bbox": list(graph.demo_bbox),
        "node_count": graph.n_nodes,
        "edge_count": graph.n_edges,
        "graph_hash": digest,
        "files": {"nodes": nodes_path.name, "edges": edges_path.name, "csr": csr_path.name},
    }
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def load_graph(graph_dir: str | Path) -> Graph:
    """Load graph artifacts produced by :func:`save_graph`."""
    root = Path(graph_dir)
    manifest_path = root / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"graph manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("artifact_version") != ARTIFACT_VERSION:
        raise ValueError("unsupported graph artifact version")
    files = manifest["files"]
    paths = [root / files[key] for key in ("nodes", "edges", "csr")]
    resolved_root = root.resolve()
    if any(resolved_root not in path.resolve().parents for path in paths):
        raise ValueError("graph manifest contains a path outside the artifact directory")
    if _artifact_digest(paths) != manifest.get("graph_hash"):
        raise ValueError("graph artifact hash does not match manifest")
    nodes = pd.read_parquet(paths[0]).sort_values("node_id")
    edges = pd.read_parquet(paths[1]).sort_values("edge_id")
    if len(nodes) != manifest["node_count"] or len(edges) != manifest["edge_count"]:
        raise ValueError("graph artifact row counts do not match manifest")
    if not np.array_equal(nodes["node_id"].to_numpy(), np.arange(len(nodes))):
        raise ValueError("graph node ids must be contiguous from zero")
    if not np.array_equal(edges["edge_id"].to_numpy(), np.arange(len(edges))):
        raise ValueError("graph edge ids must be contiguous from zero")
    if (edges[["u", "v"]].to_numpy() < 0).any() or (edges[["u", "v"]].to_numpy() >= len(nodes)).any():
        raise ValueError("graph edge endpoint is outside the node table")
    csr = np.load(paths[2], allow_pickle=False)
    geoms = tuple(from_wkb(value) for value in edges["geometry_wkb"])
    coords = tuple(np.asarray(json.loads(value), dtype=np.float64) for value in edges["coords_latlon"])
    graph = graph_from_records(
        nodes["x"].to_numpy(), nodes["y"].to_numpy(),
        nodes[["lat", "lon"]].to_numpy(), edges["u"].to_numpy(),
        edges["v"].to_numpy(), edges["length_m"].to_numpy(),
        tuple(None if pd.isna(value) else str(value) for value in edges["name"]),
        geoms, coords, tuple(manifest["demo_bbox"]), str(manifest["graph_hash"]),
    )
    saved_indices = csr["indices"].astype(np.int32, copy=False)
    saved_indptr = csr["indptr"].astype(np.int64, copy=False)
    saved_edge_ids = csr["csr_edge_id"].astype(np.int32, copy=False)
    if not (np.array_equal(graph.indices, saved_indices) and np.array_equal(graph.indptr, saved_indptr) and np.array_equal(graph.csr_edge_id, saved_edge_ids)):
        raise ValueError("CSR index artifacts are inconsistent with edge artifacts")
    return graph


def _artifact_digest(paths: tuple[Path, ...] | list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    return digest.hexdigest()


def build_osm_graph(
    bbox: tuple[float, float, float, float] = tuple(DEMO_BBOX),
    *,
    cache_dir: str | Path = "data/build/graph/osm_cache",
) -> Graph:
    """Download and normalize the OSM walk graph for an offline build step."""
    import networkx as nx
    import osmnx as ox
    from pyproj import Transformer

    west, south, east, north = map(float, bbox)
    pad_lat = 300.0 / 111_000.0
    mid_lat = (south + north) / 2.0
    pad_lon = 300.0 / max(111_000.0 * np.cos(np.deg2rad(mid_lat)), 1.0)
    padded = (west - pad_lon, south - pad_lat, east + pad_lon, north + pad_lat)
    cache = Path(cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    ox.settings.use_cache = True
    ox.settings.cache_folder = str(cache)
    # OSMnx 2.x accepts (west, south, east, north); use keyword bbox where
    # available to avoid the old north/south positional signature ambiguity.
    graph = ox.graph_from_bbox(bbox=padded, network_type="walk", simplify=True)
    graph = ox.project_graph(graph, to_crs=CRS_METRIC)
    graph = ox.convert.to_undirected(graph)
    component = max(nx.connected_components(graph), key=len)
    graph = graph.subgraph(component).copy()

    nodes_raw = sorted(graph.nodes, key=lambda value: str(value))
    node_index = {node_id: i for i, node_id in enumerate(nodes_raw)}
    node_x = np.asarray([graph.nodes[node]["x"] for node in nodes_raw], dtype=np.float64)
    node_y = np.asarray([graph.nodes[node]["y"] for node in nodes_raw], dtype=np.float64)
    inverse = Transformer.from_crs(CRS_METRIC, "EPSG:4326", always_xy=True)
    lon, lat = inverse.transform(node_x, node_y)
    node_latlon = np.column_stack((lat, lon))

    selected: dict[tuple[int, int], dict[str, Any]] = {}
    for left, right, attrs in graph.edges(data=True):
        u, v = node_index[left], node_index[right]
        if u == v:
            continue
        key = (min(u, v), max(u, v))
        length = float(attrs.get("length", 0.0))
        if length <= 0:
            length = float(np.hypot(node_x[u] - node_x[v], node_y[u] - node_y[v]))
        if key in selected and float(selected[key]["length"]) <= length:
            continue
        raw_name = attrs.get("name")
        if isinstance(raw_name, (list, tuple)):
            name = " / ".join(str(item) for item in raw_name)
        elif raw_name is None or pd.isna(raw_name):
            name = None
        else:
            name = str(raw_name)
        raw_geom = attrs.get("geometry")
        if raw_geom is None:
            geom = LineString([(node_x[u], node_y[u]), (node_x[v], node_y[v])])
        else:
            geom = LineString(_oriented_coords(raw_geom, (node_x[u], node_y[u]), (node_x[v], node_y[v])))
        if u > v:
            # Make physical edge orientation stable by the reindexed endpoints.
            u, v = v, u
            geom = LineString(list(geom.coords)[::-1])
        selected[key] = {"u": u, "v": v, "length": length, "name": name, "geometry": geom}

    records = [selected[key] for key in sorted(selected)]
    edge_u = np.asarray([item["u"] for item in records], dtype=np.int32)
    edge_v = np.asarray([item["v"] for item in records], dtype=np.int32)
    lengths = np.asarray([item["length"] for item in records], dtype=np.float64)
    geometries = tuple(item["geometry"] for item in records)
    coords_latlon: list[np.ndarray] = []
    for geometry in geometries:
        gx, gy = np.asarray(geometry.coords).T
        glon, glat = inverse.transform(gx, gy)
        coords_latlon.append(np.column_stack((glat, glon)))
    return graph_from_records(
        node_x, node_y, node_latlon, edge_u, edge_v, lengths,
        tuple(item["name"] for item in records), geometries,
        tuple(coords_latlon), tuple(map(float, bbox)),
    )
