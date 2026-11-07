"""Family stream: pushes journey and membership events to signed-in family members over WebSockets.

Holds active family journeys in memory only. Events carry ids, display names and opaque wrapped keys, never
a location. The relay still carries the encrypted location updates; this hub only tells members a walk exists.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from fastapi import WebSocket


@dataclass
class FamilyJourney:
    journey_id: str
    family_id: str
    walker_id: str
    walker_display_name: str
    viewer_token: str
    wrapped_journey_key: str
    key_version: int
    expires_at: str


class FamilyHub:
    def __init__(self):
        self.sockets: dict[str, set[WebSocket]] = {}       # account_id -> open streams
        self.journeys: dict[str, FamilyJourney] = {}        # journey_id -> family journey

    def add(self, aid: str, ws: WebSocket) -> None:
        self.sockets.setdefault(aid, set()).add(ws)

    def remove(self, aid: str, ws: WebSocket) -> None:
        s = self.sockets.get(aid)
        if s is not None:
            s.discard(ws)
            if not s:
                self.sockets.pop(aid, None)

    async def publish(self, account_ids, message: dict) -> None:
        text = json.dumps(message)
        for aid in set(account_ids):
            for ws in list(self.sockets.get(aid, ())):
                try:
                    await ws.send_text(text)
                except Exception:  # noqa: BLE001 - a dead socket must not stop the others
                    self.remove(aid, ws)

    def active_for(self, family_id: str) -> list[dict]:
        return [asdict(j) for j in self.journeys.values() if j.family_id == family_id]

    def start(self, j: FamilyJourney) -> dict:
        self.journeys[j.journey_id] = j
        return {"type": "journey.started", "journey": asdict(j)}

    def end(self, journey_id: str, reason: str) -> tuple[str | None, dict | None]:
        j = self.journeys.pop(journey_id, None)
        if j is None:
            return None, None
        return j.family_id, {"type": "journey.ended", "journey_id": journey_id, "family_id": j.family_id,
                             "reason": reason}

    def drop_walker(self, family_id: str, aid: str) -> list[str]:
        """Forget family journeys of a member who left; returns their ids."""
        ids = [jid for jid, j in self.journeys.items() if j.family_id == family_id and j.walker_id == aid]
        for jid in ids:
            self.journeys.pop(jid, None)
        return ids
