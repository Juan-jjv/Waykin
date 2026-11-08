"""The in-memory street graph (spec B4) and loading it from data/build/graph/.

One undirected graph serves both travel modes, so exposure, hazards and closures share edge ids. Each edge says
whether people may walk it and whether cars may drive it along (u→v) or against (v→u) its stored direction.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components
import shapely
from pyproj import Transformer
from scipy.spatial import cKDTree

from waykin import constants as C
from waykin.routing.types import ModeUnavailableError, OutsideAreaError, TravelMode

MODES: tuple[TravelMode, ...] = ("walk", "drive")


@lru_cache(maxsize=1)
def _to_utm() -> Transformer:
    return Transformer.from_crs("EPSG:4326", C.CRS_METRIC, always_xy=True)


@lru_cache(maxsize=1)
def _to_wgs() -> Transformer:
    return Transformer.from_crs(C.CRS_METRIC, "EPSG:4326", always_xy=True)


def latlon_to_utm(lat, lon):
    return _to_utm().transform(lon, lat)


def utm_to_latlon(x, y):
    lon, lat = _to_wgs().transform(x, y)
    return lat, lon


def graph_hash(edge_u: np.ndarray, edge_v: np.ndarray, edge_length_m: np.ndarray) -> str:
    h = hashlib.sha256()
    for a in (edge_u.astype(np.int32), edge_v.astype(np.int32), edge_length_m.astype(np.float64)):
        h.update(np.ascontiguousarray(a).tobytes())
    return h.hexdigest()[:16]


def build_csr(n_nodes: int, edge_u: np.ndarray, edge_v: np.ndarray, edge_minutes: np.ndarray):
    """Symmetric CSR of minutes with a parallel edge_id array, indices sorted within each row."""
    e = np.arange(len(edge_u), dtype=np.int32)
    rows = np.concatenate([edge_u, edge_v]).astype(np.int32)
    cols = np.concatenate([edge_v, edge_u]).astype(np.int32)
    eid = np.concatenate([e, e])
    order = np.lexsort((cols, rows))
    rows, cols, eid = rows[order], cols[order], eid[order]
    data = np.maximum(edge_minutes[eid], C.MIN_EDGE_MINUTES).astype(np.float64)
    indptr = np.zeros(n_nodes + 1, dtype=np.int32)
    np.add.at(indptr, rows + 1, 1)
    indptr = np.cumsum(indptr).astype(np.int32)
    csr = sp.csr_matrix((data, cols, indptr), shape=(n_nodes, n_nodes))
    return csr, eid.astype(np.int32)


@dataclass
class ModeView:
    """What one travel mode may use: per-edge minutes, which CSR entries (directed steps) are allowed, and the nodes
    of the mode's largest connected component (strongly connected for driving, so every snapped pair has a route)."""
    mode: TravelMode
    edge_minutes: np.ndarray
    entry_ok: np.ndarray
    nodes: np.ndarray
    tree: cKDTree | None


@dataclass
class Graph:
    n_nodes: int
    n_edges: int
    graph_hash: str
    csr: sp.csr_matrix
    csr_edge_id: np.ndarray
    node_lat: np.ndarray
    node_lon: np.ndarray
    node_x: np.ndarray
    node_y: np.ndarray
    edge_u: np.ndarray
    edge_v: np.ndarray
    edge_length_m: np.ndarray
    edge_minutes: np.ndarray
    edge_name: list
    edge_coords_latlon: list
    edge_geom_utm: np.ndarray
    edge_tree: shapely.STRtree = field(repr=False)
    bbox: tuple = C.DEMO_BBOX
    edge_walk: np.ndarray | None = None
    edge_drive_fwd: np.ndarray | None = None
    edge_drive_rev: np.ndarray | None = None
    edge_drive_kmh: np.ndarray | None = None
    edge_drive_minutes: np.ndarray | None = None
    _modes: dict = field(default_factory=dict, repr=False)

    @property
    def modes(self) -> list[TravelMode]:
        """The travel modes this graph can route."""
        return [m for m in MODES if self.mode(m).nodes.size > 0]

    def mode(self, mode: TravelMode) -> ModeView:
        if mode not in MODES:
            raise ModeUnavailableError("unknown travel mode")
        if mode not in self._modes:
            self._modes[mode] = self._build_mode(mode)
        return self._modes[mode]

    def _build_mode(self, mode: TravelMode) -> ModeView:
        eid = self.csr_edge_id
        rows = np.repeat(np.arange(self.n_nodes, dtype=np.int32), np.diff(self.csr.indptr))
        cols = self.csr.indices
        if mode == "walk":
            ok = self.edge_walk[eid].copy()
            minutes = self.edge_minutes
        else:
            forward = rows == self.edge_u[eid]
            ok = np.where(forward, self.edge_drive_fwd[eid], self.edge_drive_rev[eid])
            minutes = self.edge_drive_minutes
        if not ok.any():
            return ModeView(mode, minutes, ok, np.empty(0, dtype=np.int32), None)
        allowed = sp.csr_matrix((np.ones(int(ok.sum())), (rows[ok], cols[ok])), shape=self.csr.shape)
        _, labels = connected_components(allowed, directed=True, connection="strong" if mode == "drive" else "weak")
        has_edge = np.zeros(self.n_nodes, dtype=bool)
        has_edge[rows[ok]] = True
        sizes = np.bincount(labels[has_edge], minlength=labels.max() + 1)
        keep = labels == int(sizes.argmax())
        ok &= keep[rows] & keep[cols]
        nodes = np.flatnonzero(keep).astype(np.int32)
        return ModeView(mode, minutes, ok, nodes, cKDTree(np.column_stack([self.node_x[nodes], self.node_y[nodes]])))

    def to_utm(self, lat: float, lon: float) -> tuple[float, float]:
        x, y = latlon_to_utm(lat, lon)
        return float(x), float(y)

    def snap(self, lat: float, lon: float, mode: TravelMode = "walk") -> tuple[int, float]:
        """(node_id, distance_m) on the given mode's network. Never puts coordinates in the exception message."""
        w, s, e, n = self.bbox
        if not (s <= lat <= n and w <= lon <= e):
            raise OutsideAreaError("point is outside the demo area")
        view = self.mode(mode)
        if view.tree is None:
            raise ModeUnavailableError(f"{mode} routing is not available on this graph")
        d, i = view.tree.query(self.to_utm(lat, lon))
        if d > C.SNAP_MAX_M:
            raise OutsideAreaError(f"point is too far from the {mode} network")
        return int(view.nodes[i]), float(d)


def assemble_graph(node_lat, node_lon, node_x, node_y, edge_u, edge_v, edge_length_m, edge_name,
                   edge_geom_utm, edge_coords_latlon, bbox=C.DEMO_BBOX, edge_walk=None, edge_drive_fwd=None,
                   edge_drive_rev=None, edge_drive_kmh=None) -> Graph:
    """Build a Graph from arrays (shared by the real loader and the grid test graph).

    Without mode arrays (an older build) every edge is walkable and none drivable."""
    edge_u = np.asarray(edge_u, dtype=np.int32)
    edge_v = np.asarray(edge_v, dtype=np.int32)
    edge_length_m = np.asarray(edge_length_m, dtype=np.float64)
    n_edges = len(edge_u)
    edge_walk = np.ones(n_edges, bool) if edge_walk is None else np.asarray(edge_walk, dtype=bool)
    edge_drive_fwd = np.zeros(n_edges, bool) if edge_drive_fwd is None else np.asarray(edge_drive_fwd, dtype=bool)
    edge_drive_rev = np.zeros(n_edges, bool) if edge_drive_rev is None else np.asarray(edge_drive_rev, dtype=bool)
    edge_drive_kmh = (np.full(n_edges, C.DRIVE_FALLBACK_KMH) if edge_drive_kmh is None
                      else np.asarray(edge_drive_kmh, dtype=np.float64))
    edge_minutes = np.maximum(edge_length_m / C.WALK_SPEED_M_PER_MIN, C.MIN_EDGE_MINUTES)
    edge_drive_minutes = np.maximum(edge_length_m / (edge_drive_kmh * 1000.0 / 60.0), C.MIN_EDGE_MINUTES)
    n_nodes = len(node_lat)
    csr, csr_edge_id = build_csr(n_nodes, edge_u, edge_v, edge_minutes)
    geoms = np.asarray(edge_geom_utm, dtype=object)
    return Graph(
        n_nodes=n_nodes, n_edges=len(edge_u), graph_hash=graph_hash(edge_u, edge_v, edge_length_m),
        csr=csr, csr_edge_id=csr_edge_id,
        node_lat=np.asarray(node_lat, float), node_lon=np.asarray(node_lon, float),
        node_x=np.asarray(node_x, float), node_y=np.asarray(node_y, float),
        edge_u=edge_u, edge_v=edge_v, edge_length_m=edge_length_m, edge_minutes=edge_minutes,
        edge_name=list(edge_name), edge_coords_latlon=[np.asarray(c, float) for c in edge_coords_latlon],
        edge_geom_utm=geoms, edge_tree=shapely.STRtree(geoms), bbox=tuple(bbox),
        edge_walk=edge_walk, edge_drive_fwd=edge_drive_fwd, edge_drive_rev=edge_drive_rev,
        edge_drive_kmh=edge_drive_kmh, edge_drive_minutes=edge_drive_minutes,
    )


_MODE_COLUMNS = {"edge_walk": "walk", "edge_drive_fwd": "drive_fwd", "edge_drive_rev": "drive_rev",
                 "edge_drive_kmh": "drive_kmh"}


def load_graph(build_dir: Path) -> Graph:
    """Load the artifacts written by build_graph.py (or testing.write_graph_artifacts)."""
    gdir = Path(build_dir)
    if (gdir / "graph").is_dir():
        gdir = gdir / "graph"
    manifest = json.loads((gdir / "manifest.json").read_text())
    nodes = pd.read_parquet(gdir / "nodes.parquet").sort_values("node_id")
    edges = pd.read_parquet(gdir / "edges.parquet").sort_values("edge_id")
    g = assemble_graph(
        nodes["lat"].to_numpy(), nodes["lon"].to_numpy(), nodes["x"].to_numpy(), nodes["y"].to_numpy(),
        edges["u"].to_numpy(), edges["v"].to_numpy(), edges["length_m"].to_numpy(),
        [n if isinstance(n, str) else None for n in edges["name"]],
        shapely.from_wkb(edges["geom_wkb"].to_numpy()),
        [np.asarray(list(c), float).reshape(-1, 2) for c in edges["coords_latlon"]],
        bbox=manifest.get("bbox", C.DEMO_BBOX),
        **{name: edges[col].to_numpy() for name, col in _MODE_COLUMNS.items() if col in edges},
    )
    if g.graph_hash != manifest["graph_hash"]:
        raise RuntimeError("graph artifacts are inconsistent with their manifest; rerun build_graph")
    return g


def write_artifacts(graph: Graph, out_dir: Path, extra_manifest: dict | None = None) -> None:
    """Write the B4 graph artifacts: manifest.json, nodes.parquet, edges.parquet, csr.npz."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({
        "node_id": np.arange(graph.n_nodes, dtype=np.int32),
        "lat": graph.node_lat, "lon": graph.node_lon, "x": graph.node_x, "y": graph.node_y,
    }).to_parquet(out / "nodes.parquet", index=False)
    pd.DataFrame({
        "edge_id": np.arange(graph.n_edges, dtype=np.int32),
        "u": graph.edge_u, "v": graph.edge_v,
        "length_m": graph.edge_length_m, "minutes": graph.edge_minutes,
        "name": pd.Series(graph.edge_name, dtype="object"),
        "geom_wkb": shapely.to_wkb(graph.edge_geom_utm),
        "coords_latlon": [c.tolist() for c in graph.edge_coords_latlon],
        **{col: getattr(graph, name) for name, col in _MODE_COLUMNS.items()},
    }).to_parquet(out / "edges.parquet", index=False)
    np.savez(out / "csr.npz", indptr=graph.csr.indptr, indices=graph.csr.indices,
             data=graph.csr.data, edge_id=graph.csr_edge_id)
    manifest = {"graph_hash": graph.graph_hash, "bbox": list(graph.bbox), "crs": C.CRS_METRIC,
                "n_nodes": graph.n_nodes, "n_edges": graph.n_edges, "modes": graph.modes}
    manifest.update(extra_manifest or {})
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
