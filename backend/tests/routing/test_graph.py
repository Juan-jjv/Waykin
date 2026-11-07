import numpy as np
import pytest

from waykin import constants as C
from waykin.routing.graph import load_graph
from waykin.routing.testing import make_grid_graph, write_graph_artifacts
from waykin.routing.types import OutsideAreaError


def test_grid_shape(grid):
    n = 12
    assert grid.n_nodes == n * n
    assert grid.n_edges == 2 * n * (n - 1)
    assert np.allclose(grid.edge_length_m, 100.0)
    assert np.allclose(grid.edge_minutes, 100.0 / C.WALK_SPEED_M_PER_MIN)
    assert "Test Ave 1" in grid.edge_name and "Test St 1" in grid.edge_name


def test_grid_inside_demo_bbox(grid):
    w, s, e, n = C.DEMO_BBOX
    assert (grid.node_lat >= s).all() and (grid.node_lat <= n).all()
    assert (grid.node_lon >= w).all() and (grid.node_lon <= e).all()


def test_csr_is_symmetric_and_edge_ids_align(grid):
    csr = grid.csr
    assert (csr - csr.T).count_nonzero() == 0
    assert csr.nnz == 2 * grid.n_edges
    for row in (0, 13, grid.n_nodes - 1):
        cols = csr.indices[csr.indptr[row]:csr.indptr[row + 1]]
        assert (np.diff(cols) > 0).all()  # sorted within each row
        for k in range(csr.indptr[row], csr.indptr[row + 1]):
            e = grid.csr_edge_id[k]
            assert {grid.edge_u[e], grid.edge_v[e]} == {row, csr.indices[k]}


def test_edge_geometry_oriented_u_to_v(grid):
    for e in range(0, grid.n_edges, 17):
        first = np.asarray(grid.edge_geom_utm[e].coords[0])
        assert np.allclose(first, [grid.node_x[grid.edge_u[e]], grid.node_y[grid.edge_u[e]]])
        assert np.allclose(grid.edge_coords_latlon[e][0], [grid.node_lat[grid.edge_u[e]], grid.node_lon[grid.edge_u[e]]])


def test_snap_finds_nearest_node(grid):
    node, d = grid.snap(float(grid.node_lat[30]) + 0.0001, float(grid.node_lon[30]))
    assert node == 30 and d < 20


def test_snap_rejects_points_outside(grid):
    with pytest.raises(OutsideAreaError) as exc:
        grid.snap(53.60, -113.50)
    assert "53.6" not in str(exc.value)  # never echo coordinates
    with pytest.raises(OutsideAreaError):
        grid.snap(53.5295, -113.481)  # inside the bbox but far from the small grid


def test_artifacts_round_trip(tmp_path, grid):
    write_graph_artifacts(grid, tmp_path)
    g2 = load_graph(tmp_path)
    assert g2.graph_hash == grid.graph_hash
    assert g2.n_edges == grid.n_edges
    assert g2.edge_name == grid.edge_name
    assert np.allclose(g2.edge_coords_latlon[5], grid.edge_coords_latlon[5])
    assert (g2.csr_edge_id == grid.csr_edge_id).all()


def test_grid_is_deterministic():
    assert make_grid_graph().graph_hash == make_grid_graph().graph_hash
