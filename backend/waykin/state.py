from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from waykin.config import Settings
    from waykin.realtime.hazard_store import HazardStore
    from waykin.realtime.journeys import JourneyStore
    from waykin.realtime.relay import RelayHub


@dataclass
class AppState:
    """Everything the app holds in memory (spec B4). graph/exposure are None in mock mode."""
    settings: "Settings"
    graph: Any            # waykin.routing.graph.Graph | None
    exposure: Any         # waykin.data.bundle.ExposureBundle | None
    hazards: "HazardStore"
    journeys: "JourneyStore"
    relay: "RelayHub"
    accounts: Any = None  # waykin.accounts.store.AccountStore; created on first use if a test leaves it unset
    family_hub: Any = None  # waykin.accounts.hub.FamilyHub
