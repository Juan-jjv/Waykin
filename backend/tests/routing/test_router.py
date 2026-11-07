import numpy as np
import pytest

from waykin.routing.router import candidate_set
from waykin.routing.testing import make_grid_graph
from waykin.routing.types import NoPathError


def test_zero_exposure_returns_only_fastest():
    graph = make_grid_graph()
    result = candidate_set(graph, np.zeros(graph.n_edges), 0, graph.n_nodes - 1)
    assert result.fastest.label == "fastest"
    assert result.alternatives == []
    assert result.uncapped is None


def test_hotspot_finds_capped_lower_exposure_detour():
    graph = make_grid_graph()
    fastest = candidate_set(graph, np.zeros(graph.n_edges), 0, graph.n_nodes - 1).fastest
    exposure = np.zeros(graph.n_edges)
    exposure[fastest.edge_ids] = 10.0
    result = candidate_set(graph, exposure, 0, graph.n_nodes - 1)
    assert result.lower_exposure is not None
    assert result.lower_exposure.exposure_mean < result.fastest.exposure_mean
    assert result.lower_exposure.minutes <= result.fastest.minutes * 1.25


def test_blocked_edge_is_not_used():
    graph = make_grid_graph()
    fastest = candidate_set(graph, np.zeros(graph.n_edges), 0, graph.n_nodes - 1).fastest
    blocked = np.zeros(graph.n_edges, dtype=bool)
    blocked[fastest.edge_ids[0]] = True
    rerouted = candidate_set(graph, np.zeros(graph.n_edges), 0, graph.n_nodes - 1, blocked)
    assert fastest.edge_ids[0] not in rerouted.fastest.edge_ids


def test_blocking_all_source_exits_raises_no_path():
    graph = make_grid_graph()
    blocked = np.zeros(graph.n_edges, dtype=bool)
    exits = np.flatnonzero((graph.edge_u == 0) | (graph.edge_v == 0))
    blocked[exits] = True
    with pytest.raises(NoPathError):
        candidate_set(graph, np.zeros(graph.n_edges), 0, graph.n_nodes - 1, blocked)


def test_route_edges_are_contiguous():
    graph = make_grid_graph()
    result = candidate_set(graph, np.zeros(graph.n_edges), 0, graph.n_nodes - 1)
    route = result.fastest
    assert len(route.node_ids) == len(route.edge_ids) + 1
    for u, v, edge_id in zip(route.node_ids[:-1], route.node_ids[1:], route.edge_ids):
        assert {int(u), int(v)} == {int(graph.edge_u[edge_id]), int(graph.edge_v[edge_id])}
