"""In-memory hazards (closures, incidents, reports) and the blocked-edge mask used by routing."""

from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import datetime, timedelta

import numpy as np

from waykin.realtime.hazard_stream import HazardStreamHub
from waykin.realtime.journeys import utcnow
from waykin.schemas import Hazard, HazardCreate, HazardSource

EdgeResolver = Callable[[float, float, float], np.ndarray]  # (lat, lon, radius_m) -> int32 edge_ids


class HazardStore:
    def __init__(
        self,
        n_edges: int,
        edge_resolver: EdgeResolver,
        stream: HazardStreamHub | None = None,
        now: Callable[[], datetime] = utcnow,
    ) -> None:
        self.n_edges = int(n_edges)
        self._resolve = edge_resolver
        self.stream = stream if stream is not None else HazardStreamHub()
        self._now = now
        self._hazards: dict[str, Hazard] = {}
        self._mask: np.ndarray | None = None

    # ------------------------------------------------------------ queries
    def list(self) -> list[Hazard]:
        return sorted(self._hazards.values(), key=lambda h: (h.created_at, h.hazard_id))

    def get(self, hazard_id: str) -> Hazard | None:
        return self._hazards.get(hazard_id)

    def blocked_mask(self) -> np.ndarray:
        if self._mask is None:
            m = np.zeros(self.n_edges, dtype=bool)
            for h in self._hazards.values():  # every active hazard blocks its edges (clients reroute on any)
                ids = np.asarray(h.edge_ids, dtype=np.int64)
                ids = ids[(ids >= 0) & (ids < self.n_edges)]
                m[ids] = True
            m.setflags(write=False)
            self._mask = m
        return self._mask

    def blocked_edge_ids(self) -> list[int]:
        return [int(i) for i in np.flatnonzero(self.blocked_mask())]

    def snapshot(self) -> dict:
        return {
            "type": "snapshot",
            "hazards": [h.model_dump(mode="json") for h in self.list()],
            "blocked_edge_ids": self.blocked_edge_ids(),
        }

    # ------------------------------------------------------------ changes
    def add(self, req: HazardCreate, source: HazardSource, *, edge_ids: list[int] | None = None,
            hazard_id: str | None = None) -> Hazard:
        if edge_ids is None:
            edge_ids = [int(e) for e in np.asarray(self._resolve(req.lat, req.lon, req.radius_m)).ravel()]
        now = self._now()
        h = Hazard(
            hazard_id=hazard_id or "hz_" + secrets.token_urlsafe(6),
            kind=req.kind,
            lat=req.lat,
            lon=req.lon,
            radius_m=req.radius_m,
            description=req.description,
            source=source,
            created_at=now,
            expires_at=now + timedelta(minutes=req.ttl_min),
            edge_ids=sorted(set(edge_ids)),
        )
        self._hazards[h.hazard_id] = h
        self._mask = None
        self.stream.publish({"type": "hazard.added", "hazard": h.model_dump(mode="json")})
        return h

    def remove(self, hazard_id: str) -> bool:
        h = self._hazards.pop(hazard_id, None)
        if h is None:
            return False
        self._mask = None
        self.stream.publish({"type": "hazard.removed", "hazard_id": h.hazard_id, "edge_ids": h.edge_ids})
        return True

    def sweep_expired(self) -> list[str]:
        now = self._now()
        ids = [hid for hid, h in self._hazards.items() if now >= h.expires_at]
        for hid in ids:
            self.remove(hid)
        return ids

    def clear(self) -> list[str]:
        ids = list(self._hazards)
        for hid in ids:
            self.remove(hid)
        return ids
