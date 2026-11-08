"""Walking and driving on one graph: per-mode minutes, one-way streets, mode-only edges and snapping."""
import numpy as np
import pytest

from waykin.routing.router import candidate_set
from waykin.routing.testing import make_grid_graph
from waykin.routing.types import ModeUnavailableError, NoPathError


def _edge(g, a, b):
    return int(np.flatnonzero(((g.edge_u == a) & (g.edge_v == b)) | ((g.edge_u == b) & (g.edge_v == a)))[0])


def test_walk_only_graph_has_no_drive_mode():
    g = make_grid_graph(4)
    assert g.modes == ["walk"]
    with pytest.raises(ModeUnavailableError):
        g.snap(float(g.node_lat[0]), float(g.node_lon[0]), "drive")


def test_drive_uses_drive_minutes():
    g = make_grid_graph(6, drive_kmh=36.0)          # 600 m/min vs walking 80 m/min
    assert g.modes == ["walk", "drive"]
    zero = np.zeros(g.n_edges)
    walk = candidate_set(g, zero, 0, g.n_nodes - 1, mode="walk").fastest
    drive = candidate_set(g, zero, 0, g.n_nodes - 1, mode="drive").fastest
    assert walk.distance_m == drive.distance_m == 1000.0
    assert walk.minutes == pytest.approx(1000 / 80)
    assert drive.minutes == pytest.approx(1000 / 600)


def test_one_way_street_is_walked_both_ways_but_driven_one_way():
    g = make_grid_graph(4, drive_kmh=40.0)
    row0 = [_edge(g, c, c + 1) for c in range(3)]   # bottom row, stored west→east
    g.edge_drive_rev[row0] = False                  # one-way eastbound
    zero = np.zeros(g.n_edges)
    walk = candidate_set(g, zero, 3, 0, mode="walk").fastest
    drive = candidate_set(g, zero, 3, 0, mode="drive").fastest
    assert set(walk.edge_ids) == set(row0)
    assert not set(drive.edge_ids) & set(row0)
    assert drive.distance_m == 500.0                # up, three blocks west, down
    east = candidate_set(g, zero, 0, 3, mode="drive").fastest
    assert set(east.edge_ids) == set(row0)


def test_mode_only_edges():
    g = make_grid_graph(4, drive_kmh=40.0)
    path = [_edge(g, c, c + 1) for c in range(3)]
    g.edge_walk[path[1]] = False                    # a motorway-style piece: cars only
    g.edge_drive_fwd[path[0]] = g.edge_drive_rev[path[0]] = False   # a footpath: people only
    zero = np.zeros(g.n_edges)
    walk = candidate_set(g, zero, 0, 3, mode="walk").fastest
    drive = candidate_set(g, zero, 0, 3, mode="drive").fastest
    assert path[1] not in walk.edge_ids and walk.distance_m == 500.0     # around the cars-only block
    assert path[0] not in drive.edge_ids and drive.distance_m == 500.0   # around the footpath


def test_drive_snaps_into_the_strongly_connected_network():
    g = make_grid_graph(4, drive_kmh=40.0)
    # Node 0 can only be entered by car (both its streets are one-way into it), so it's a trap: never snap there.
    into0 = [_edge(g, 0, 1), _edge(g, 0, 4)]
    g.edge_drive_fwd[into0] = False                 # stored 0→1 and 0→4: forbid leaving 0
    node, _ = g.snap(float(g.node_lat[0]), float(g.node_lon[0]), "drive")
    assert node != 0
    walk_node, _ = g.snap(float(g.node_lat[0]), float(g.node_lon[0]), "walk")
    assert walk_node == 0


def test_blocked_closure_applies_to_driving():
    g = make_grid_graph(3, drive_kmh=40.0)
    blocked = np.zeros(g.n_edges, dtype=bool)
    blocked[[_edge(g, 0, 1), _edge(g, 0, 3)]] = True
    with pytest.raises(NoPathError):
        candidate_set(g, np.zeros(g.n_edges), 0, 8, blocked, mode="drive")
