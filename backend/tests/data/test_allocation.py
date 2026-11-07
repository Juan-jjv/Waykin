import json

import numpy as np
import pandas as pd

from waykin.data.allocation import build_allocation, catchment_radii, prior_node_ids
from waykin.routing.graph import latlon_to_utm, utm_to_latlon


def at_xy(x, y):
    lat, lon = utm_to_latlon(x, y)
    return pd.DataFrame({"lat": [float(lat)], "lon": [float(lon)]})


def edge_between(g, a, b):
    return int(np.flatnonzero(((g.edge_u == a) & (g.edge_v == b)) | ((g.edge_u == b) & (g.edge_v == a)))[0])


def test_rows_sum_to_one(grid):
    locs = pd.DataFrame({"lat": grid.node_lat[::7], "lon": grid.node_lon[::7]})
    A, stats = build_allocation(locs, grid, 100)
    assert np.allclose(np.asarray(A.sum(axis=1)).ravel(), 1.0, atol=1e-6)
    assert A.shape == (stats["n_published"] + stats["n_prior"], grid.n_edges)
    assert stats["n_published"] == len(locs) and stats["n_prior"] > 0


def test_point_at_edge_midpoint_hits_only_that_edge(grid):
    e = edge_between(grid, 0, 1)
    A, _ = build_allocation(at_xy((grid.node_x[0] + grid.node_x[1]) / 2, grid.node_y[0]), grid, 50)
    assert A[0, e] == 1.0 or np.isclose(A[0, e], 1.0)


def test_intersection_spreads_by_length_over_its_streets(grid):
    n = 13   # interior node of the 12-wide grid: four streets meet here
    A, _ = build_allocation(pd.DataFrame({"lat": [grid.node_lat[n]], "lon": [grid.node_lon[n]]}), grid, 50)
    row = A[0].toarray().ravel()
    assert (row > 0).sum() == 4 and np.allclose(row[row > 0], 0.25)


def test_point_outside_every_circle_falls_back_to_nearest_edge(grid):
    e = edge_between(grid, 0, 1)
    locs = at_xy((grid.node_x[0] + grid.node_x[1]) / 2, grid.node_y[0] - 80)
    A, stats = build_allocation(locs, grid, 50)
    assert np.isclose(A[0, e], 1.0) and A[0].nnz == 1 and stats["fallback_share"] > 0


def test_prior_nodes_are_only_nodes_away_from_published_points(grid):
    x, y = latlon_to_utm(grid.node_lat[:1], grid.node_lon[:1])
    ids = prior_node_ids(np.asarray(x), np.asarray(y), grid)
    assert 0 not in ids and len(ids) == grid.n_nodes - 1


def test_severe_reports_reach_more_streets(grid):
    n = 13
    def at_node(by_category):
        return pd.DataFrame({"lat": [grid.node_lat[n]], "lon": [grid.node_lon[n]],
                             "counts_by_category": [json.dumps(by_category)]})
    severity = {"homicide": 2.0, "theft": 0.75}
    severe, s_stats = build_allocation(at_node({"homicide": 1}), grid, 100, severity)
    minor, m_stats = build_allocation(at_node({"theft": 1}), grid, 100, severity)
    assert severe[0].nnz > minor[0].nnz
    assert s_stats["mean_radius_m"] == 200.0 and m_stats["mean_radius_m"] == 75.0
    mixed = catchment_radii(at_node({"homicide": 1, "theft": 3}), 100, severity)
    assert np.isclose(mixed[0], 100 * (2.0 + 3 * 0.75) / 4)


def test_no_published_points_makes_every_node_a_prior_row(grid):
    A, stats = build_allocation(pd.DataFrame({"lat": [], "lon": []}), grid, 100)
    assert stats["n_prior"] == grid.n_nodes and A.shape[0] == grid.n_nodes
