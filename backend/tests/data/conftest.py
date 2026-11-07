import numpy as np
import pytest

from waykin.data.bundle import ExposureBundle
from waykin.routing.testing import make_grid_graph
from waykin.routing.types import Candidate, CandidateSet, route_id_for


@pytest.fixture(scope="session")
def grid():
    return make_grid_graph()


def cand(label, edge_ids, minutes, lam=0.0):
    e = np.asarray(edge_ids, dtype=np.int32)
    return Candidate(label=label, route_id=route_id_for(e), edge_ids=e, node_ids=np.zeros(len(e) + 1, np.int32),
                     minutes=float(minutes), distance_m=float(minutes) * 80, exposure_mean=0.0, lam=lam)


@pytest.fixture
def make_cs():
    def _make(alts=(), uncapped=None, fastest=((0, 1), 10.0)):
        f = cand("fastest", fastest[0], fastest[1])
        a = [cand(lbl, e, m) for lbl, e, m in alts]
        u = cand("uncapped", uncapped[0], uncapped[1]) if uncapped else None
        return CandidateSet(fastest=f, alternatives=a, uncapped=u)
    return _make


FASTEST_EDGES, CLEAR_ALT_EDGES, CLOSE_ALT_EDGES = range(0, 10), range(100, 110), range(150, 160)


@pytest.fixture
def route_sets():
    """Keyed by origin node. Trip 0 has a clearly lower alternative; trip 1 has one that matches fastest."""
    fastest = cand("fastest", FASTEST_EDGES, 10)
    return {0: CandidateSet(fastest, [cand("balanced", CLEAR_ALT_EDGES, 11)], None),
            1: CandidateSet(fastest, [cand("balanced", CLOSE_ALT_EDGES, 11)], None)}


@pytest.fixture
def route_bundle(grid):
    """Exposure that matches route_sets: fastest and the close alternative are busy, the clear alternative is quiet."""
    X = np.full((grid.n_edges, 50), 0.1, dtype=np.float32)
    X[list(FASTEST_EDGES)] = 2.0
    X[list(CLOSE_ALT_EDGES)] = 2.0
    return ExposureBundle(source="synthetic", source_label="t", as_of=None, window_days=90, category_preset="all",
                          categories=[], radii=[100], X={100: X}, mean={100: X.mean(1)},
                          observed={100: np.full(grid.n_edges, 5.0)}, locations=None)
