"""WebSocket relay between one walker and up to RELAY_MAX_VIEWERS viewers (B5 relay protocol).

In e2ee mode the server never parses `ct`: it checks only the envelope's shape, then stores
and forwards the raw text. Only the latest `loc` message is held, in memory, until the journey ends.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from contextlib import suppress
from typing import Any

from pydantic import ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from waykin import constants as C
from waykin.realtime.journeys import JourneyError, JourneyExpired, JourneyStore
from waykin.schemas import WalkerUpdate

log = logging.getLogger("waykin.relay")

CLOSE_WRONG_KIND = 4400
CLOSE_BAD_TOKEN = 4401
CLOSE_UNKNOWN = 4404
CLOSE_REPLACED = 4409
CLOSE_ENDED = 4410
CLOSE_TOO_BIG = 4413
CLOSE_RATE = 4429

AUTH_TIMEOUT_S = 5.0
_B64URL = re.compile(r"^[A-Za-z0-9_-]+$")
IV_B64_LEN = 16          # 12 bytes -> 16 base64url chars, no padding
CT_B64_MIN = 22          # at least the 16-byte GCM tag


class _Reject(Exception):
    def __init__(self, code: int) -> None:
        super().__init__(code)
        self.code = code


class TokenBucket:
    def __init__(self, rate: float, capacity: float | None = None) -> None:
        self.rate = float(rate)
        self.capacity = float(capacity if capacity is not None else rate)
        self.tokens = self.capacity
        self.t = time.monotonic()

    def take(self) -> bool:
        now = time.monotonic()
        self.tokens = min(self.capacity, self.tokens + (now - self.t) * self.rate)
        self.t = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


def _is_int(x: Any) -> bool:
    return isinstance(x, int) and not isinstance(x, bool)


def validate_envelope(env: Any) -> int:
    """Shape-only check of an Envelope. Returns seq. Never decodes or inspects ct."""
    if not isinstance(env, dict) or set(env) != {"v", "seq", "iv", "ct"}:
        raise _Reject(CLOSE_WRONG_KIND)
    v, seq, iv, ct = env["v"], env["seq"], env["iv"], env["ct"]
    if not (_is_int(v) and v == 1 and _is_int(seq) and seq >= 0):
        raise _Reject(CLOSE_WRONG_KIND)
    if not (isinstance(iv, str) and len(iv) == IV_B64_LEN and _B64URL.match(iv)):
        raise _Reject(CLOSE_WRONG_KIND)
    if not (isinstance(ct, str) and CT_B64_MIN <= len(ct) <= C.RELAY_MAX_MSG_BYTES and _B64URL.match(ct)):
        raise _Reject(CLOSE_WRONG_KIND)
    return seq


async def safe_close(ws: WebSocket, code: int) -> None:
    with suppress(Exception):
        if ws.application_state != WebSocketState.DISCONNECTED:
            await ws.close(code=code)


async def safe_send(ws: WebSocket, text: str) -> bool:
    try:
        await ws.send_text(text)
        return True
    except Exception:
        return False


class RelayHub:
    def __init__(
        self,
        journeys: JourneyStore,
        *,
        plaintext: bool = False,
        max_viewers: int = C.RELAY_MAX_VIEWERS,
        max_bytes: int = C.RELAY_MAX_MSG_BYTES,
        max_msgs_per_sec: int = C.RELAY_MAX_MSGS_PER_SEC,
    ) -> None:
        self.journeys = journeys
        self.plaintext = plaintext
        self.max_viewers = max_viewers
        self.max_bytes = max_bytes
        self.rate = max_msgs_per_sec
        self.walkers: dict[str, WebSocket] = {}
        self.viewers: dict[str, set[WebSocket]] = {}

    @property
    def relay_mode(self) -> str:
        return "plaintext" if self.plaintext else "e2ee"

    def socket_count(self, jid: str | None = None) -> int:
        if jid is not None:
            return int(jid in self.walkers) + len(self.viewers.get(jid, ()))
        return len(self.walkers) + sum(len(v) for v in self.viewers.values())

    # ------------------------------------------------------------ lifecycle
    async def end_journey(self, jid: str, reason: str) -> None:
        """Send `ended` to viewers, close every socket with 4410, purge the journey."""
        walker = self.walkers.pop(jid, None)
        viewers = self.viewers.pop(jid, set())
        self.journeys.purge(jid, reason)
        msg = json.dumps({"type": "ended", "reason": reason})
        for v in viewers:
            await safe_send(v, msg)
            await safe_close(v, CLOSE_ENDED)
        if walker is not None:
            await safe_close(walker, CLOSE_ENDED)

    async def sweep_expired(self) -> list[str]:
        ids = self.journeys.sweep_expired()
        for jid in ids:
            await self.end_journey(jid, "expired")
        return ids

    async def reset(self) -> None:
        for jid in set(self.journeys.ids()) | set(self.walkers) | set(self.viewers):
            await self.end_journey(jid, "stopped")

    # ------------------------------------------------------------ connection
    async def handle(self, ws: WebSocket, jid: str) -> None:
        await ws.accept()
        try:
            raw = await asyncio.wait_for(ws.receive_text(), timeout=AUTH_TIMEOUT_S)
        except TimeoutError:
            await safe_close(ws, CLOSE_BAD_TOKEN)
            return
        except (WebSocketDisconnect, RuntimeError, KeyError):
            return

        role = await self._authenticate(ws, jid, raw)
        if role is None:
            return
        if role == "walker":
            await self._walker_loop(ws, jid)
        else:
            await self._viewer_loop(ws, jid)

    async def _authenticate(self, ws: WebSocket, jid: str, raw: str) -> str | None:
        try:
            if len(raw.encode("utf-8")) > self.max_bytes:
                raise _Reject(CLOSE_TOO_BIG)
            try:
                msg = json.loads(raw)
            except ValueError as e:
                raise _Reject(CLOSE_WRONG_KIND) from e
            if not isinstance(msg, dict) or msg.get("type") != "auth":
                raise _Reject(CLOSE_WRONG_KIND)
            role, token = msg.get("role"), msg.get("token")
            if role not in ("walker", "viewer") or not isinstance(token, str):
                raise _Reject(CLOSE_BAD_TOKEN)
            try:
                journey = self.journeys.verify(jid, role, token)
            except JourneyExpired:
                await self.end_journey(jid, "expired")
                raise _Reject(CLOSE_ENDED) from None
            except JourneyError as e:
                raise _Reject(e.close_code) from None
            if role == "viewer" and len(self.viewers.get(jid, ())) >= self.max_viewers:
                raise _Reject(CLOSE_RATE)
        except _Reject as r:
            await safe_close(ws, r.code)
            return None

        ready = {"type": "ready", "relay_mode": self.relay_mode, "expires_at": journey.expires_at.isoformat()}
        if role == "walker":
            old = self.walkers.get(jid)
            self.walkers[jid] = ws
            if old is not None and old is not ws:
                await safe_close(old, CLOSE_REPLACED)
            if not await safe_send(ws, json.dumps(ready)):
                self._drop(jid, ws)
                return None
        else:
            self.viewers.setdefault(jid, set()).add(ws)
            ok = await safe_send(ws, json.dumps(ready))
            if ok and journey.latest is not None:
                ok = await safe_send(ws, journey.latest)
            if not ok:
                self._drop(jid, ws)
                return None
        return role

    def _drop(self, jid: str, ws: WebSocket) -> None:
        if self.walkers.get(jid) is ws:
            del self.walkers[jid]
        vs = self.viewers.get(jid)
        if vs is not None:
            vs.discard(ws)
            if not vs:
                self.viewers.pop(jid, None)

    async def _receive(self, ws: WebSocket) -> str | None:
        try:
            return await ws.receive_text()
        except (WebSocketDisconnect, RuntimeError, KeyError):
            return None

    async def _walker_loop(self, ws: WebSocket, jid: str) -> None:
        bucket = TokenBucket(self.rate)
        try:
            while True:
                raw = await self._receive(ws)
                if raw is None:
                    return
                if self.walkers.get(jid) is not ws:  # replaced or journey ended
                    return
                journey = self.journeys.get(jid)
                if journey is None:
                    await safe_close(ws, CLOSE_ENDED)
                    return
                if self.journeys.is_expired(journey):
                    await self.end_journey(jid, "expired")
                    return
                try:
                    await self._on_walker_message(jid, journey, raw, bucket)
                except _Reject as r:
                    await safe_close(ws, r.code)
                    return
                if jid not in self.journeys:  # ended by this message
                    return
        finally:
            self._drop(jid, ws)

    async def _on_walker_message(self, jid: str, journey: Any, raw: str, bucket: TokenBucket) -> None:
        if len(raw.encode("utf-8")) > self.max_bytes:
            raise _Reject(CLOSE_TOO_BIG)
        if not bucket.take():
            raise _Reject(CLOSE_RATE)
        try:
            msg = json.loads(raw)
        except ValueError as e:
            raise _Reject(CLOSE_WRONG_KIND) from e
        if not isinstance(msg, dict):
            raise _Reject(CLOSE_WRONG_KIND)
        kind = msg.get("type")

        if kind == "end":
            reason = msg.get("reason")
            if reason not in ("arrived", "stopped") or set(msg) != {"type", "reason"}:
                raise _Reject(CLOSE_WRONG_KIND)
            await self.end_journey(jid, reason)
            return

        if kind != "loc":
            raise _Reject(CLOSE_WRONG_KIND)

        if self.plaintext:
            if set(msg) != {"type", "plain"}:
                raise _Reject(CLOSE_WRONG_KIND)
            try:
                WalkerUpdate.model_validate(msg["plain"])
            except ValidationError as e:
                raise _Reject(CLOSE_WRONG_KIND) from e
        else:
            if set(msg) != {"type", "env"}:
                raise _Reject(CLOSE_WRONG_KIND)
            seq = validate_envelope(msg["env"])
            if seq <= journey.last_seq:
                return  # stale or replayed: drop quietly
            journey.last_seq = seq

        journey.latest = raw
        dead = []
        for v in list(self.viewers.get(jid, ())):
            if not await safe_send(v, raw):
                dead.append(v)
        for v in dead:
            self._drop(jid, v)

    async def _viewer_loop(self, ws: WebSocket, jid: str) -> None:
        """Viewers only listen. Anything they send is size/rate checked and otherwise ignored."""
        bucket = TokenBucket(self.rate)
        try:
            while True:
                raw = await self._receive(ws)
                if raw is None:
                    return
                if len(raw.encode("utf-8")) > self.max_bytes:
                    await safe_close(ws, CLOSE_TOO_BIG)
                    return
                if not bucket.take():
                    await safe_close(ws, CLOSE_RATE)
                    return
        finally:
            self._drop(jid, ws)
