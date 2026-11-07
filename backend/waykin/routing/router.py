"""Sparse shortest paths and λ-sweep route candidate generation."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from .pareto import select_options
from .types import Graph, NoPathError, RouteCandidate, RouteSet, route_id

try:  # Constants are owned by the shared backend skeleton (Agent A4).
    from waykin import constants as _constants
except ImportError:  # Keeps the A3-owned package usable before A4 lands.
    _constants = None

MAX_EXTRA_TIME = getattr(_constants, "MAX_EXTRA_TIME", 0.25)
BALANCED_MIN_REDUCTION = getattr(_constants, "BALANCED_MIN_REDUCTION", 0.15)
LAMBDA_GRID = getattr(_constants, "LAMBDA_GRID", (0.0, 0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0))


def shortest_path(
    graph: Graph,
    edge_weights: np.ndarray,
    src: int,
    dst: int,
    blocked: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, float] | None:
    """Run Dijkstra and return node path, edge path, and weighted cost."""
    weights = np.asarray(edge_weights, dtype=np.float64)
    if weights.shape != (graph.n_edges,):
        raise ValueError("edge_weights must have one value per graph edge")
    if not (0 <= src < graph.n_nodes and 0 <= dst < graph.n_nodes):
        raise IndexError("source and destination must be valid node indices")
    if blocked is None:
        blocked_mask = np.zeros(graph.n_edges, dtype=bool)
    else:
        blocked_mask = np.asarray(blocked, dtype=bool)
        if blocked_mask.shape != (graph.n_edges,):
            raise ValueError("blocked must have one flag per graph edge")

    csr_weights = weights[graph.csr_edge_id].copy()
    if blocked_mask.any():
        csr_weights[blocked_mask[graph.csr_edge_id]] = 0.0
    matrix = csr_matrix((csr_weights, graph.indices, graph.indptr), shape=(graph.n_nodes, graph.n_nodes))
    matrix.eliminate_zeros()
    distances, predecessors = dijkstra(matrix, directed=True, indices=src, return_predecessors=True)
    total_cost = float(distances[dst])
    if not np.isfinite(total_cost):
        return None

    reverse_nodes = [int(dst)]
    cursor = int(dst)
    while cursor != src:
        previous = int(predecessors[cursor])
        if previous < 0 or previous == cursor:
            return None
        reverse_nodes.append(previous)
        cursor = previous
    node_ids = np.asarray(reverse_nodes[::-1], dtype=np.int32)
    edge_ids = np.empty(max(0, node_ids.size - 1), dtype=np.int32)
    for index, (left, right) in enumerate(zip(node_ids[:-1], node_ids[1:])):
        start, end = graph.indptr[left], graph.indptr[left + 1]
        row = graph.indices[start:end]
        offset = int(np.searchsorted(row, right))
        if offset >= row.size or int(row[offset]) != int(right):
            raise RuntimeError("predecessor path is inconsistent with graph CSR")
        edge_ids[index] = graph.csr_edge_id[start + offset]
    return node_ids, edge_ids, total_cost


def candidate_set(
    graph: Graph,
    exposure: Sequence[float] | np.ndarray,
    src: int,
    dst: int,
    blocked: np.ndarray | None = None,
    *,
    lambda_grid: Sequence[float] = LAMBDA_GRID,
    max_extra_time: float = MAX_EXTRA_TIME,
    balanced_min_reduction: float = BALANCED_MIN_REDUCTION,
) -> RouteSet:
    """Sweep route-time/exposure tradeoffs and select Pareto candidates."""
    means = np.asarray(exposure, dtype=np.float64)
    if means.shape != (graph.n_edges,):
        raise ValueError("exposure must have one value per graph edge")
    if not np.all(np.isfinite(means)) or np.any(means < 0):
        raise ValueError("exposure values must be finite and non-negative")
    if not lambda_grid or float(lambda_grid[0]) != 0.0:
        raise ValueError("lambda_grid must start with 0.0 so fastest is explicit")

    found: dict[str, RouteCandidate] = {}
    fastest: RouteCandidate | None = None
    for lam in lambda_grid:
        lam = float(lam)
        if not np.isfinite(lam) or lam < 0:
            raise ValueError("lambda values must be finite and non-negative")
        weights = graph.edge_minutes + lam * means
        result = shortest_path(graph, weights, src, dst, blocked)
        if result is None:
            if lam == 0.0:
                raise NoPathError("no_path")
            continue
        node_ids, edge_ids, _ = result
        rid = route_id(edge_ids)
        if rid not in found:
            found[rid] = RouteCandidate(
                route_id=rid,
                node_ids=node_ids,
                edge_ids=edge_ids,
                minutes=float(graph.edge_minutes[edge_ids].sum()),
                distance_m=float(graph.edge_length_m[edge_ids].sum()),
                exposure_mean=float(means[edge_ids].sum()),
            )
        if lam == 0.0:
            fastest = found[rid]

    if fastest is None:
        raise NoPathError("no_path")
    return select_options(found.values(), fastest, max_extra_time, balanced_min_reduction)
