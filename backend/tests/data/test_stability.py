"""Every abstain reason, with hand-built X (no graph needed)."""
import time

import numpy as np
import pytest

from waykin.data.bundle import ExposureBundle
from waykin.data.stability import _decide, assess

N = 500


def bundle(X, observed=None, radii=(100,)):
    E = X.shape[0]
    obs = np.full(E, 5.0) if observed is None else observed
    return ExposureBundle(source="synthetic", source_label="t", as_of=None, window_days=90, category_preset="all",
                          categories=[], radii=list(radii), X={r: X for r in radii},
                          mean={r: X.mean(1) for r in radii}, observed={r: obs for r in radii}, locations=None)


def X_with(edge_means, spread=0.05, seed=0):
    rng = np.random.default_rng(seed)
    m = np.asarray(edge_means, float)[:, None]
    return np.clip(m * (1 + spread * rng.standard_normal((len(edge_means), N))), 0, None).astype(np.float32)


def test_recommend_when_clearly_lower_every_draw(make_cs):
    X = X_with([10, 10, 1, 1])                     # fastest uses 0,1 (≈20); alternative uses 2,3 (≈2)
    a = assess(make_cs(alts=[("lower_exposure", (2, 3), 11.0)]), bundle(X), 100)
    assert a.status == "recommend" and a.reason is None
    assert a.recommended_route_id != make_cs().fastest.route_id
    alt = [s for s in a.stats.values() if s.draws_better is not None][0]
    assert alt.draws_better == N and alt.diff_p50 < 0
    assert "of 500 simulations" in a.message


def test_indistinguishable_when_lower_in_only_85_percent(make_cs):
    S = np.vstack([np.full(N, 10.0), np.where(np.arange(N) < 425, 5.0, 10.0)])
    status, reason, idx, better = _decide(S, np.array([10, 11]), observed_total=50, n_alternatives=1, has_uncapped=False)
    assert (status, reason) == ("abstain", "indistinguishable") and better[1] == 425


def test_too_costly_when_only_the_uncapped_route_is_lower(make_cs):
    X = X_with([10, 10, 9.5, 9.5, 1, 1])
    cs = make_cs(alts=[("balanced", (2, 3), 11.0)], uncapped=((4, 5), 20.0))
    a = assess(cs, bundle(X), 100)
    assert (a.status, a.reason) == ("abstain", "too_costly")


def test_lower_route_above_time_cap_is_not_recommended(make_cs):
    X = X_with([10, 10, 1, 1])
    a = assess(make_cs(alts=[("lower_exposure", (2, 3), 13.0)]), bundle(X), 100)  # 13 > 1.25·10
    assert a.status == "abstain"


def test_thin_data(make_cs):
    X = X_with([10, 10, 1, 1])
    a = assess(make_cs(alts=[("lower_exposure", (2, 3), 11.0)]), bundle(X, observed=np.full(4, 0.5)), 100)
    assert (a.status, a.reason) == ("abstain", "thin_data")


def test_no_alternative(make_cs):
    a = assess(make_cs(), bundle(X_with([1, 1])), 100)
    assert (a.status, a.reason) == ("abstain", "no_alternative")
    assert a.message == "There is only one reasonable route for this trip."


def test_recommends_fewest_extra_minutes(make_cs):
    X = X_with([10, 10, 1, 1, 2, 2])
    cs = make_cs(alts=[("lower_exposure", (2, 3), 12.0), ("balanced", (4, 5), 10.5)])
    a = assess(cs, bundle(X), 100)
    assert a.recommended_route_id == cs.alternatives[1].route_id


def test_never_recommends_fastest(make_cs):
    for seed in range(5):
        X = X_with(np.random.default_rng(seed).uniform(0, 10, 6), spread=0.5, seed=seed)
        cs = make_cs(alts=[("balanced", (2, 3), 10.5), ("lower_exposure", (4, 5), 12.0)])
        assert assess(cs, bundle(X), 100).recommended_route_id != cs.fastest.route_id


def test_radius_sensitivity(make_cs):
    clear, unclear = X_with([10, 10, 1, 1]), X_with([10, 10, 9.5, 9.5])
    b = bundle(clear, radii=(50, 100))
    b.X[50] = unclear
    a = assess(make_cs(alts=[("lower_exposure", (2, 3), 11.0)]), b, 100)
    assert a.radius_sensitive is True
    assert a.radius_decisions[100].startswith("recommend") and a.radius_decisions[50] == "abstain:indistinguishable"


def test_single_radius_leaves_sensitivity_unset(make_cs):
    a = assess(make_cs(alts=[("lower_exposure", (2, 3), 11.0)]), bundle(X_with([10, 10, 1, 1])), 100)
    assert a.radius_decisions is None and a.radius_sensitive is None


@pytest.mark.timing
def test_assess_is_fast(make_cs):
    X = np.random.default_rng(0).random((25_000, N), dtype=np.float32)
    cs = make_cs(alts=[("balanced", range(100, 160), 10.5), ("lower_exposure", range(200, 270), 12.0)],
                 fastest=(range(0, 50), 10.0))
    b = bundle(X)
    assess(cs, b, 100)
    t = time.perf_counter()
    assess(cs, b, 100)
    assert (time.perf_counter() - t) * 1000 < 50
