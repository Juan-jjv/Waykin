"""Provenance block attached to every meta, incidents, routes and reroute response."""

from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from waykin import constants as C
from waykin.schemas import Provenance

if TYPE_CHECKING:
    from waykin.state import AppState

MOCK_AS_OF = date(2026, 10, 31)
MOCK_SOURCE_LABEL = "Mock fixtures (synthetic, for development only)"


def build_provenance(state: AppState, radius_m: int) -> Provenance:
    b = state.exposure
    if b is None:  # mock mode
        return Provenance(
            source="synthetic",
            source_label=MOCK_SOURCE_LABEL,
            as_of=MOCK_AS_OF,
            window_days=C.WINDOW_DAYS,
            radius_m=int(radius_m),
            units=C.UNITS,
            disclaimer=C.DISCLAIMER,
        )
    return Provenance(
        source=b.source,
        source_label=b.source_label,
        as_of=b.as_of,
        window_days=int(b.window_days),
        radius_m=int(radius_m),
        units=C.UNITS,
        disclaimer=C.DISCLAIMER,
    )
