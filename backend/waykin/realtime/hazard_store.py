"""In-memory hazards (spec A4.8). Phase 1: storage, expiry and the blocked mask; edge mapping comes from
A3's `hazard_edges` (Phase 3). In mock mode, hazards carry fixture edge ids."""
from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import timedelta

import numpy as np

from waykin.realtime.journeys import now
from waykin.schemas import Hazard, HazardCreate


class HazardStore:
    def __init__(self, n_edges: int, edge_mapper: Callable[[HazardCreate], list[int]],
                 on_change: Callable[[str, Hazard], None] | None = None):
        self.n_edges = n_edges
        self._map = edge_mapper
        self._h: dict[str, Hazard] = {}
        self._mask: np.ndarray | None = None
        self.on_change = on_change

    def add(self, req: HazardCreate, source: str) -> Hazard:
        t = now()
        h = Hazard(hazard_id=secrets.token_urlsafe(6), kind=req.kind, lat=req.lat, lon=req.lon,
                   radius_m=req.radius_m, description=req.description, source=source, created_at=t,
                   expires_at=t + timedelta(minutes=req.ttl_min), edge_ids=[int(e) for e in self._map(req)])
        self._h[h.hazard_id] = h
        self._changed("added", h)
        return h

    def remove(self, hazard_id: str) -> Hazard | None:
        h = self._h.pop(hazard_id, None)
        if h is not None:
            self._changed("removed", h)
        return h

    def list(self) -> list[Hazard]:
        return list(self._h.values())

    def blocked_ids(self) -> list[int]:
        return sorted({e for h in self._h.values() for e in h.edge_ids})

    def blocked_mask(self) -> np.ndarray:
        if self._mask is None:
            m = np.zeros(self.n_edges, dtype=bool)
            ids = [e for e in self.blocked_ids() if 0 <= e < self.n_edges]
            m[ids] = True
            self._mask = m
        return self._mask

    def sweep_expired(self) -> list[Hazard]:
        t = now()
        gone = [h for h in self._h.values() if h.expires_at <= t]
        for h in gone:
            self.remove(h.hazard_id)
        return gone

    def clear(self) -> None:
        for hid in list(self._h):
            self.remove(hid)

    def _changed(self, kind: str, h: Hazard) -> None:
        self._mask = None
        if self.on_change is not None:
            self.on_change(kind, h)
