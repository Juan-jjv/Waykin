from __future__ import annotations

from datetime import date

from waykin import constants as C
from waykin.schemas import Provenance

MOCK_AS_OF = date(2026, 10, 31)


def build_provenance(state, radius_m: int) -> Provenance:
    """Provenance for every meta, incidents, routes and reroute response."""
    b = state.exposure
    if b is None:  # mock mode
        return Provenance(source="synthetic", source_label="Synthetic data (mock mode)", as_of=MOCK_AS_OF,
                          window_days=C.ROUTE_WINDOW_DAYS, radius_m=radius_m, units=C.UNITS, disclaimer=C.DISCLAIMER)
    return Provenance(source=b.source, source_label=b.source_label, as_of=b.as_of, window_days=b.window_days,
                      radius_m=radius_m, units=C.UNITS, disclaimer=C.DISCLAIMER)
