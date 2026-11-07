"""Snap-aware allocation matrix A (spec A2.4).

Police data places each report at an intersection, so a report could belong to any street around it. Each
location's count is spread over the edges within its catchment radius, in proportion to each edge's length inside
that circle. With severity weights, a location's radius is `radius_m` times the count-weighted mean weight of its
categories, so more severe reports reach more nearby streets. Graph nodes far from every published location become
zero-count prior rows (at `radius_m`), so streets with no reports carry real uncertainty instead of a certain zero.
Each row sums to 1.
"""
from __future__ import annotations

import json
import logging

import numpy as np
import pandas as pd
import scipy.sparse as sp
import shapely
from scipy.spatial import cKDTree

from waykin import constants as C
from waykin.routing.graph import latlon_to_utm

log = logging.getLogger("waykin.data")


def prior_node_ids(x: np.ndarray, y: np.ndarray, graph, min_gap_m: float = C.PRIOR_NODE_MIN_GAP_M) -> np.ndarray:
    """Graph nodes farther than min_gap_m from every published point (given in UTM)."""
    if len(x) == 0:
        return np.arange(graph.n_nodes)
    d, _ = cKDTree(np.column_stack([x, y])).query(np.column_stack([graph.node_x, graph.node_y]))
    return np.flatnonzero(d > min_gap_m)


def catchment_radii(locations: pd.DataFrame, radius_m: float, severity: dict[str, float] | None) -> np.ndarray:
    """One radius per published location: `radius_m` scaled by the count-weighted mean severity of its reports."""
    radii = np.full(len(locations), float(radius_m))
    if not severity or "counts_by_category" not in locations:
        return radii
    for i, raw in enumerate(locations["counts_by_category"]):
        by_category = json.loads(raw) if raw else {}
        total = sum(by_category.values())
        if total > 0:
            weight = sum(n * severity.get(c, 1.0) for c, n in by_category.items()) / total
            radii[i] = float(radius_m) * weight
    return radii


def build_allocation(locations: pd.DataFrame, graph, radius_m: float,
                     severity: dict[str, float] | None = None) -> tuple[sp.csr_matrix, dict]:
    """Rows: `locations` in order, then the prior nodes. Cols: edge_id. Returns (A, stats). Never logs coordinates."""
    n_published = len(locations)
    if n_published:
        x, y = (np.asarray(v, float) for v in latlon_to_utm(locations["lat"].to_numpy(float), locations["lon"].to_numpy(float)))
    else:
        x, y = np.empty(0), np.empty(0)
    prior = prior_node_ids(x, y, graph)
    x, y = np.concatenate([x, graph.node_x[prior]]), np.concatenate([y, graph.node_y[prior]])
    n_rows = len(x)
    radii = np.concatenate([catchment_radii(locations, radius_m, severity), np.full(len(prior), float(radius_m))])

    points = shapely.points(x, y)
    circles = shapely.buffer(points, radii, quad_segs=16)
    row, edge = graph.edge_tree.query(circles, predicate="intersects")
    length = shapely.length(shapely.intersection(graph.edge_geom_utm[edge], circles[row]))
    touching = length > 1e-9
    row, edge, length = row[touching], edge[touching], length[touching]

    missing = np.flatnonzero(np.bincount(row, minlength=n_rows) == 0)
    if len(missing):        # no edge within the radius: the nearest edge takes the whole row
        idx, nearest = graph.edge_tree.query_nearest(points[missing], all_matches=False)
        row = np.concatenate([row, missing[idx]])
        edge = np.concatenate([edge, nearest])
        length = np.concatenate([length, np.ones(len(idx))])

    weights = length / np.bincount(row, weights=length, minlength=n_rows)[row]
    A = sp.csr_matrix((weights, (row, edge)), shape=(n_rows, graph.n_edges))
    A.sum_duplicates()
    A.sort_indices()

    stats = {
        "n_published": n_published,
        "n_prior": len(prior),
        "nnz": int(A.nnz),
        "mean_edges_per_location": round(A.nnz / max(n_rows, 1), 2),
        "fallback_share": round(len(missing) / max(n_rows, 1), 4),
        "mean_radius_m": round(float(radii[:n_published].mean()), 1) if n_published else float(radius_m),
    }
    log.info("allocation r=%sm: %s", int(radius_m), stats)
    return A, stats
