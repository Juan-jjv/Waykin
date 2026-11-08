import time
from datetime import timedelta

import numpy as np
import pytest
import scipy.sparse as sp

from waykin import constants as C
from waykin.data.bundle import make_synthetic_bundle_for_tests
from waykin.data.montecarlo import simulate


def small_A():
    # 3 published locations + 1 prior node over 5 edges; rows sum to 1.
    dense = np.array([
        [0.5, 0.5, 0.0, 0.0, 0.0],
        [0.0, 0.2, 0.8, 0.0, 0.0],
        [0.0, 0.0, 0.0, 1.0, 0.0],
        [0.0, 0.0, 0.0, 0.0, 1.0],   # prior node: only it reaches edge 4
    ])
    return sp.csr_matrix(dense), np.array([4.0, 10.0, 1.0, 0.0])


def test_shape_dtype_nonnegative():
    A, c = small_A()
    X = simulate(A, c, n_draws=200)
    assert X.shape == (5, 200) and X.dtype == np.float32
    assert (X >= 0).all()


def test_same_seed_same_result():
    A, c = small_A()
    assert np.array_equal(simulate(A, c, n_draws=50), simulate(A, c, n_draws=50))
    assert not np.array_equal(simulate(A, c, n_draws=50, radius_m=100), simulate(A, c, n_draws=50, radius_m=200))


def test_expected_total_equals_observed_total():
    A, c = small_A()
    X = simulate(A, c, n_draws=4000)
    assert abs(X.sum(0).mean() - c.sum()) / c.sum() < 0.03


def test_unreported_street_is_uncertain_not_zero():
    A, c = small_A()
    X = simulate(A, c, n_draws=500)
    assert X[4].std() > 0 and X[4].mean() > 0
    assert X[4].mean() < X[2].mean()  # but still much lower than a reported street


@pytest.mark.timing
def test_simulate_runtime_at_full_size():
    rng = np.random.default_rng(0)
    L, E, per_row = 6_000, 25_000, 6
    cols = rng.integers(0, E, (L, per_row)).ravel()
    A = sp.csr_matrix((np.full(L * per_row, 1 / per_row), (np.repeat(np.arange(L), per_row), cols)), shape=(L, E))
    t = time.perf_counter()
    simulate(A, rng.poisson(1.0, L).astype(float))
    assert time.perf_counter() - t < 60


def test_synthetic_bundle_is_deterministic(grid):
    b1 = make_synthetic_bundle_for_tests(grid)
    b2 = make_synthetic_bundle_for_tests(grid)
    assert np.array_equal(b1.X[100], b2.X[100])
    assert b1.X[100].shape == (grid.n_edges, 500)
    assert b1.locations["count"].min() >= 1
    assert set(b1.locations.columns) == {"location_id", "lat", "lon", "count", "counts_by_category"}
    d = b1.daily
    recent = d[d["date"] > b1.as_of - timedelta(days=C.ROUTE_WINDOW_DAYS)]["count"].sum()
    assert 0 < recent < b1.locations["count"].sum()
    assert abs(b1.observed[100].sum() - recent) < 1e-3
