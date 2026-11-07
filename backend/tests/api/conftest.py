"""Fixtures for A4's API tests. Mock mode needs no data; real-mode tests skip until A2/A3 helpers exist."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from waykin.config import Settings
from waykin.main import create_app, make_state

ADMIN = "test-admin-token"
os.environ.setdefault("ADMIN_TOKEN", ADMIN)  # keeps startup from printing a generated token


def settings(**over) -> Settings:
    base = dict(WAYKIN_MOCK=True, ADMIN_TOKEN=ADMIN, MOCK_HAZARD_DELAY_S=0.2, SWEEP_INTERVAL_S=3600,
                DEMO_MODE=False, RELAY_PLAINTEXT=False, SERVE_FRONTEND=False)
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
    return make_client()


@pytest.fixture
def real_state():
    testing = pytest.importorskip("waykin.routing.testing")
    bundle_mod = pytest.importorskip("waykin.data.bundle")
    try:
        g = testing.make_grid_graph()
        b = bundle_mod.make_synthetic_bundle_for_tests(g)
    except NotImplementedError:
        pytest.skip("A2/A3 test helpers are still stubs")
    return make_state(settings(WAYKIN_MOCK=False), g, b)
