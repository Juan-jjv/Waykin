import pytest
from fastapi.testclient import TestClient

from waykin.config import Settings
from waykin.main import create_app


@pytest.fixture
def mock_client():
    app = create_app(Settings(WAYKIN_MOCK=True, RELAY_PLAINTEXT=True, ADMIN_TOKEN="admin", DEMO_MODE=False))
    with TestClient(app) as c:
        yield c


@pytest.fixture
def e2ee_client():
    app = create_app(Settings(WAYKIN_MOCK=True, RELAY_PLAINTEXT=False, ADMIN_TOKEN="admin", DEMO_MODE=False))
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def real_state():
    """A real-mode AppState on the grid graph and the synthetic test bundle (no files)."""
    from waykin.data.bundle import make_synthetic_bundle_for_tests
    from waykin.realtime.hazard_store import HazardStore
    from waykin.realtime.journeys import JourneyStore
    from waykin.realtime.relay import RelayHub
    from waykin.routing.testing import make_grid_graph
    from waykin.state import AppState

    g = make_grid_graph(drive_kmh=40.0)
    s = Settings(WAYKIN_MOCK=False, RELAY_PLAINTEXT=True, ADMIN_TOKEN="admin", DEMO_MODE=False)
    j = JourneyStore()
    return AppState(settings=s, graph=g, exposure=make_synthetic_bundle_for_tests(g),
                    hazards=HazardStore(g.n_edges, edge_mapper=lambda req: []), journeys=j,
                    relay=RelayHub(j, s.relay_mode))


@pytest.fixture
def real_client(real_state):
    with TestClient(create_app(state=real_state)) as c:
        yield c
