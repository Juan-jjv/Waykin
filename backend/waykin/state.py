"""The single in-memory application state (B4). One uvicorn worker, so one AppState."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from starlette.requests import HTTPConnection

if TYPE_CHECKING:  # never import routing/data at module load: mock mode must survive half-built folders
    from waykin.config import Settings
    from waykin.data.bundle import ExposureBundle
    from waykin.realtime.hazard_store import HazardStore
    from waykin.realtime.journeys import JourneyStore
    from waykin.realtime.relay import RelayHub
    from waykin.routing.graph import Graph


@dataclass
class AppState:
    settings: Settings
    graph: Graph            # None in mock mode
    exposure: ExposureBundle  # None in mock mode
    hazards: HazardStore    # .blocked_mask() -> np.ndarray[bool] (E,); .list(); .add(); .remove()
    journeys: JourneyStore
    relay: RelayHub

    @property
    def mock(self) -> bool:
        return self.graph is None or self.exposure is None


def get_state(request: HTTPConnection) -> AppState:
    """FastAPI dependency: works for both Request and WebSocket."""
    return request.app.state.waykin
