"""In-memory journey sessions (spec A4.6). Raw tokens are never stored, only their sha256."""
from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone


class JourneyError(Exception):
    """Carries the relay close code and the API error code."""

    def __init__(self, close_code: int, code: str, message: str):
        super().__init__(message)
        self.close_code, self.code = close_code, code


def _h(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Journey:
    journey_id: str
    walker_token_hash: bytes
    viewer_token_hash: bytes
    expires_at: datetime
    latest: str | None = None      # the latest raw "loc" JSON text, relayed byte for byte
    last_seq: int = -1
    ended: bool = False


class JourneyStore:
    def __init__(self):
        self._j: dict[str, Journey] = {}

    def __contains__(self, jid: str) -> bool:
        return jid in self._j

    def __len__(self) -> int:
        return len(self._j)

    def get(self, jid: str) -> Journey | None:
        return self._j.get(jid)

    def create(self, ttl_min: int) -> tuple[Journey, str, str]:
        jid = secrets.token_urlsafe(9)
        walker, viewer = secrets.token_urlsafe(24), secrets.token_urlsafe(24)
        j = Journey(jid, _h(walker), _h(viewer), now() + timedelta(minutes=ttl_min))
        self._j[jid] = j
        return j, walker, viewer

    def verify(self, jid: str, role: str, token: str) -> Journey:
        j = self._j.get(jid)
        if j is None:
            raise JourneyError(4404, "not_found", "unknown journey")
        if j.ended or j.expires_at <= now():
            raise JourneyError(4410, "expired", "journey has ended")
        expected = j.walker_token_hash if role == "walker" else j.viewer_token_hash if role == "viewer" else None
        if expected is None or not hmac.compare_digest(_h(token or ""), expected):
            raise JourneyError(4401, "invalid_token", "invalid token for this role")
        return j

    def purge(self, jid: str, reason: str) -> None:
        """Remove the entry entirely, including the latest message."""
        j = self._j.pop(jid, None)
        if j is not None:
            j.latest, j.ended = None, True

    def sweep_expired(self) -> list[str]:
        t = now()
        return [jid for jid, j in self._j.items() if j.expires_at <= t]

    def clear(self) -> list[str]:
        ids = list(self._j)
        for jid in ids:
            self.purge(jid, "stopped")
        return ids
