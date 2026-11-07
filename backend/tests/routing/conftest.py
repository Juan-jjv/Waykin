import pytest

from waykin.routing.testing import make_grid_graph


@pytest.fixture(scope="session")
def grid():
    return make_grid_graph()
