import numpy as np
import pytest

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
