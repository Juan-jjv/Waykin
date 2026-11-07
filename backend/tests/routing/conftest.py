"""Reusable offline graph fixture for backend agents' tests."""

import pytest

from waykin.routing.testing import make_grid_graph


@pytest.fixture
def grid_graph():
    return make_grid_graph(n=6, spacing_m=100.0)
