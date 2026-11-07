"""Fixtures for the privacy suite (A4.11). Mock mode needs no data; real mode uses the grid graph."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from waykin.config import Settings
from waykin.main import create_app

ADMIN = "test-admin-token"


def settings(**over) -> Settings:
    base = dict(WAYKIN_MOCK=True, ADMIN_TOKEN=ADMIN, DEMO_MODE=False, RELAY_PLAINTEXT=False)
    base.update(over)
    return Settings(**base)


@pytest.fixture
def make_client():
    clients = []

    def _make(state=None, **over) -> TestClient:
        c = TestClient(create_app(settings(**over), state=state))
        c.__enter__()
        clients.append(c)
        return c

    yield _make
    for c in clients:
        c.__exit__(None, None, None)


@pytest.fixture
def client(make_client) -> TestClient:
    """Mock mode, e2ee relay: the configuration the pitch's privacy claims are about."""
    return make_client()


@pytest.fixture
def real_state():
    from waykin.data.bundle import make_synthetic_bundle_for_tests
    from waykin.realtime.hazard_store import HazardStore
    from waykin.realtime.journeys import JourneyStore
    from waykin.realtime.relay import RelayHub
    from waykin.routing.testing import make_grid_graph
    from waykin.state import AppState

    g = make_grid_graph()
    s = settings(WAYKIN_MOCK=False)
    j = JourneyStore()
    return AppState(settings=s, graph=g, exposure=make_synthetic_bundle_for_tests(g),
                    hazards=HazardStore(g.n_edges, edge_mapper=lambda req: []), journeys=j,
                    relay=RelayHub(j, s.relay_mode))
