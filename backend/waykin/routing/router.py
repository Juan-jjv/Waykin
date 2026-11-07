"""Sparse shortest paths and the λ-sweep candidate set."""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import dijkstra

from waykin import constants as C
from waykin.routing.graph import Graph
from waykin.routing.types import Candidate, CandidateSet, NoPathError, route_id_for
from .pareto import select_options


def shortest_path(
    graph: Graph,
    edge_weights: np.ndarray,
    src: int,
    dst: int,
    blocked: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Run Dijkstra over a fresh CSR data vector and return its node/edge path."""
    weights = np.asarray(edge_weights, dtype=np.float64)
    if weights.shape != (graph.n_edges,) or not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError("edge_weights must be positive, finite, and have one value per edge")
    blocked_mask = np.zeros(graph.n_edges, dtype=bool) if blocked is None else np.asarray(blocked, dtype=bool)
    if blocked_mask.shape != (graph.n_edges,):
        raise ValueError("blocked must have one flag per edge")

    data = weights[graph.csr_edge_id].copy()
    data[blocked_mask[graph.csr_edge_id]] = 0.0
    # Copies: eliminate_zeros() rewrites indices/indptr in place, and the graph's arrays are shared by every request.
    matrix = sp.csr_matrix((data, graph.csr.indices.copy(), graph.csr.indptr.copy()), shape=graph.csr.shape)
    matrix.eliminate_zeros()
    distances, predecessors = dijkstra(matrix, directed=True, indices=src, return_predecessors=True)
    if not np.isfinite(distances[dst]):
        return None

    nodes = [int(dst)]
    current = int(dst)
    while current != src:
        previous = int(predecessors[current])
        if previous < 0 or previous == current:
            return None
        nodes.append(previous)
        current = previous
    node_ids = np.asarray(nodes[::-1], dtype=np.int32)
    edges = np.empty(len(node_ids) - 1, dtype=np.int32)
    for i, (u, v) in enumerate(zip(node_ids[:-1], node_ids[1:])):
        start, end = graph.csr.indptr[u], graph.csr.indptr[u + 1]
        row = graph.csr.indices[start:end]
        offset = int(np.searchsorted(row, v))
        if offset == row.size or row[offset] != v:
            raise RuntimeError("Dijkstra predecessor path is inconsistent with graph CSR")
        edges[i] = graph.csr_edge_id[start + offset]
    return node_ids, edges


def candidate_set(
    graph: Graph,
    exposure: np.ndarray,
    src: int,
    dst: int,
    blocked: np.ndarray | None = None,
) -> CandidateSet:
    """Sweep the configured λ grid and select the capped Pareto alternatives."""
    mean = np.asarray(exposure, dtype=np.float64)
    if mean.shape != (graph.n_edges,) or not np.isfinite(mean).all() or (mean < 0).any():
        raise ValueError("exposure must be finite, non-negative, and have one value per edge")
    found: dict[str, Candidate] = {}
    fastest: Candidate | None = None
    for lam in C.LAMBDA_GRID:
        lam = float(lam)
        result = shortest_path(graph, graph.edge_minutes + lam * mean, src, dst, blocked)
        if result is None:
            if lam == 0.0:
                raise NoPathError("no_path")
            continue
        node_ids, edge_ids = result
        rid = route_id_for(edge_ids)
        candidate = found.get(rid)
        if candidate is None:
            candidate = Candidate(
                label="fastest" if lam == 0 else "lower_exposure",
                route_id=rid,
                edge_ids=edge_ids,
                node_ids=node_ids,
                minutes=float(graph.edge_minutes[edge_ids].sum()),
                distance_m=float(graph.edge_length_m[edge_ids].sum()),
                exposure_mean=float(mean[edge_ids].sum()),
                lam=lam,
            )
            found[rid] = candidate
        if lam == 0.0:
            fastest = candidate
    if fastest is None:
        raise NoPathError("no_path")
    return select_options(list(found.values()), fastest, C.MAX_EXTRA_TIME, C.BALANCED_MIN_REDUCTION)
