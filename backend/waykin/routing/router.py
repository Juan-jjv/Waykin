"""Shortest paths and the λ-sweep candidate set (spec A3.4). Phase 2: real implementation by H15."""
from __future__ import annotations

import numpy as np

from waykin.routing.graph import Graph
from waykin.routing.types import CandidateSet


def shortest_path(graph: Graph, edge_weights: np.ndarray, src: int, dst: int,
                  blocked: np.ndarray | None) -> tuple[np.ndarray, np.ndarray] | None:
    raise NotImplementedError("shortest_path arrives in Phase 2 (H15)")


def candidate_set(graph: Graph, exposure: np.ndarray, src: int, dst: int,
                  blocked: np.ndarray | None) -> CandidateSet:
    raise NotImplementedError("candidate_set arrives in Phase 2 (H15)")
