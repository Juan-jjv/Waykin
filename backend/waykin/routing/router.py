"""Sparse shortest paths and the λ-sweep candidate set."""

from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import dijkstra

from waykin import constants as C
from waykin.routing.graph import Graph
from waykin.routing.types import Candidate, CandidateSet, NoPathError, TravelMode, route_id_for
from .pareto import select_options


def shortest_path(
    graph: Graph,
    edge_weights: np.ndarray,
    src: int,
    dst: int,
    blocked: np.ndarray | None = None,
    entry_ok: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Run Dijkstra over a fresh CSR data vector and return its node/edge path.

    `entry_ok` (one flag per CSR entry, from Graph.mode) removes the directed steps the travel mode can't take."""
    weights = np.asarray(edge_weights, dtype=np.float64)
    if weights.shape != (graph.n_edges,) or not np.isfinite(weights).all() or (weights <= 0).any():
        raise ValueError("edge_weights must be positive, finite, and have one value per edge")
    blocked_mask = np.zeros(graph.n_edges, dtype=bool) if blocked is None else np.asarray(blocked, dtype=bool)
    if blocked_mask.shape != (graph.n_edges,):
        raise ValueError("blocked must have one flag per edge")

    data = weights[graph.csr_edge_id].copy()
    data[blocked_mask[graph.csr_edge_id]] = 0.0
    if entry_ok is not None:
        data[~np.asarray(entry_ok, dtype=bool)] = 0.0
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
    mode: TravelMode = "walk",
    avoid: np.ndarray | None = None,
) -> CandidateSet:
    """Sweep the configured λ grid and select the capped Pareto alternatives for one travel mode.

    With `avoid` (metres of each edge inside no-go zones) a second sweep adds AVOID_MINUTES_PER_M per metre, so the
    lower-exposure route keeps out of the zones whenever the time cap allows. If no zone-free route fits the cap, a
    sweep over smaller penalties finds the routes that spend the least time in them."""
    mean = np.asarray(exposure, dtype=np.float64)
    if mean.shape != (graph.n_edges,) or not np.isfinite(mean).all() or (mean < 0).any():
        raise ValueError("exposure must be finite, non-negative, and have one value per edge")
    zone = np.zeros(graph.n_edges) if avoid is None else np.asarray(avoid, dtype=np.float64)
    view = graph.mode(mode)
    minutes = view.edge_minutes
    found: dict[str, Candidate] = {}
    fastest: Candidate | None = None

    def run(lam: float, mu: float) -> Candidate | None:
        result = shortest_path(graph, minutes + lam * mean + mu * zone, src, dst, blocked, view.entry_ok)
        if result is None:
            return None
        node_ids, edge_ids = result
        rid = route_id_for(edge_ids)
        if rid not in found:
            found[rid] = Candidate(
                label="fastest" if lam == 0 and mu == 0 else "lower_exposure",
                route_id=rid,
                edge_ids=edge_ids,
                node_ids=node_ids,
                minutes=float(minutes[edge_ids].sum()),
                distance_m=float(graph.edge_length_m[edge_ids].sum()),
                exposure_mean=float(mean[edge_ids].sum()),
                lam=lam,
                avoid_m=float(zone[edge_ids].sum()),
            )
        return found[rid]

    for lam in C.LAMBDA_GRID:
        candidate = run(float(lam), 0.0)
        if lam == 0.0:
            if candidate is None:
                raise NoPathError("no_path")
            fastest = candidate
    if fastest is None:
        raise NoPathError("no_path")

    if fastest.avoid_m > 0:
        cap = fastest.minutes * (1.0 + C.MAX_EXTRA_TIME)
        clear = [c for c in (run(float(lam), C.AVOID_MINUTES_PER_M) for lam in C.LAMBDA_GRID) if c is not None]
        if not any(c.minutes <= cap + 1e-9 for c in clear):
            # The zone-free detours are too long: trade time for less time in the zones, as far as the cap allows.
            for mu in np.geomspace(0.002, C.AVOID_MINUTES_PER_M, 10):
                for lam in (0.0, 1.0):
                    run(lam, float(mu))
    return select_options(list(found.values()), fastest, C.MAX_EXTRA_TIME)
