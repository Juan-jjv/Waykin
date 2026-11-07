"""In-memory journey store. Only token hashes are kept; nothing survives a journey's end."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from waykin import constants as C


def utcnow() -> datetime:
    return datetime.now(UTC)


def _hash(token: str) -> bytes:
    return hashlib.sha256(token.encode("utf-8")).digest()


class JourneyError(Exception):
    """Base error. `close_code` is used by the relay, `http_status`/`code` by HTTP handlers."""

    close_code = 4401
    http_status = 401
    code = "invalid_token"
    message = "Invalid token."

    def __init__(self) -> None:
        super().__init__(self.message)


class UnknownJourney(JourneyError):
    close_code, http_status, code, message = 4404, 404, "not_found", "Unknown journey."


class JourneyExpired(JourneyError):
    close_code, http_status, code, message = 4410, 410, "expired", "Journey ended or expired."


class BadToken(JourneyError):
    close_code, http_status, code, message = 4401, 401, "invalid_token", "Invalid token."


class WrongRole(JourneyError):
    close_code, http_status, code, message = 4401, 401, "forbidden", "Token does not grant this role."


@dataclass
class Journey:
    journey_id: str            # secrets.token_urlsafe(9)
    walker_token_hash: bytes   # sha256(token). Never store the raw token.
    viewer_token_hash: bytes
    expires_at: datetime
    latest: str | None = None  # the latest raw "loc" JSON text, relayed byte for byte
    last_seq: int = -1
    ended: bool = False


class JourneyStore:
    def __init__(self, now: Callable[[], datetime] = utcnow) -> None:
        self._now = now
        self._journeys: dict[str, Journey] = {}

    # -- read helpers
    def __contains__(self, jid: object) -> bool:
        return jid in self._journeys

    def __len__(self) -> int:
        return len(self._journeys)

    def get(self, jid: str) -> Journey | None:
        return self._journeys.get(jid)

    def ids(self) -> list[str]:
        return list(self._journeys)

    def is_expired(self, j: Journey) -> bool:
        return j.ended or self._now() >= j.expires_at

    # -- contract
    def create(self, ttl_min: int) -> tuple[Journey, str, str]:
        ttl = max(1, min(int(ttl_min), C.JOURNEY_TTL_MIN_MAX))
        jid = secrets.token_urlsafe(9)
        while jid in self._journeys:
            jid = secrets.token_urlsafe(9)
        walker_token = secrets.token_urlsafe(24)
        viewer_token = secrets.token_urlsafe(24)
        j = Journey(
            journey_id=jid,
            walker_token_hash=_hash(walker_token),
            viewer_token_hash=_hash(viewer_token),
            expires_at=self._now() + timedelta(minutes=ttl),
        )
        self._journeys[jid] = j
        return j, walker_token, viewer_token

    def verify(self, jid: str, role: str, token: str) -> Journey:
        j = self._journeys.get(jid)
        if j is None:
            raise UnknownJourney()
        if self.is_expired(j):
            raise JourneyExpired()
        if not isinstance(token, str) or not token:
            raise BadToken()
        h = _hash(token)
        want, other = (
            (j.walker_token_hash, j.viewer_token_hash) if role == "walker"
            else (j.viewer_token_hash, j.walker_token_hash) if role == "viewer"
            else (None, None)
        )
        if want is None:
            raise BadToken()
        ok = hmac.compare_digest(h, want)
        if not ok:
            if hmac.compare_digest(h, other):
                raise WrongRole()
            raise BadToken()
        return j

    def purge(self, jid: str, reason: str) -> None:
        j = self._journeys.pop(jid, None)
        if j is not None:  # drop references eagerly
            j.latest = None
            j.ended = True

    def sweep_expired(self) -> list[str]:
        now = self._now()
        return [jid for jid, j in self._journeys.items() if j.ended or now >= j.expires_at]

    def clear(self) -> list[str]:
        ids = list(self._journeys)
        for jid in ids:
            self.purge(jid, "reset")
        return ids
