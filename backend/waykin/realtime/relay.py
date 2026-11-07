"""WebSocket relay hub (spec B5 relay protocol, A4.6).

In e2ee mode the server never parses `ct`: it checks only the envelope's shape, then stores and
forwards the raw text. Only the latest `loc` message is kept, in memory, and purged on end/DELETE/expiry.
Never logs coordinates or message contents.
"""
from __future__ import annotations

import asyncio
import json
import re
import time
from dataclasses import dataclass, field

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from waykin import constants as C
from waykin.realtime.journeys import JourneyError, JourneyStore
from waykin.schemas import WalkerUpdate

AUTH_TIMEOUT_S = 5.0
B64URL = re.compile(r"^[A-Za-z0-9_-]+$")

CLOSE_WRONG_KIND, CLOSE_BAD_TOKEN, CLOSE_UNKNOWN = 4400, 4401, 4404
CLOSE_ENDED, CLOSE_TOO_BIG, CLOSE_RATE = 4410, 4413, 4429


class _Close(Exception):
    def __init__(self, code: int):
        self.code = code


@dataclass
class _Bucket:
    rate: float = float(C.RELAY_MAX_MSGS_PER_SEC)
    tokens: float = float(C.RELAY_MAX_MSGS_PER_SEC)
    last: float = field(default_factory=time.monotonic)

    def take(self) -> bool:
        t = time.monotonic()
        self.tokens = min(self.rate, self.tokens + (t - self.last) * self.rate)
        self.last = t
        if self.tokens >= 1:
            self.tokens -= 1
            return True
        return False


@dataclass
class _Room:
    walker: WebSocket | None = None
    viewers: set = field(default_factory=set)


def valid_envelope(env) -> bool:
    if not isinstance(env, dict) or set(env) != {"v", "seq", "iv", "ct"}:
        return False
    if env["v"] != 1 or not isinstance(env["seq"], int) or isinstance(env["seq"], bool) or env["seq"] < 0:
        return False
    iv, ct = env["iv"], env["ct"]
    return (isinstance(iv, str) and len(iv) == 16 and bool(B64URL.match(iv))
            and isinstance(ct, str) and len(ct) >= 22 and bool(B64URL.match(ct)))


_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def clean_label(raw) -> str | None:
    """A viewer's self-chosen display name: short, printable, or nothing."""
    if not isinstance(raw, str):
        return None
    label = _CONTROL.sub("", raw).strip()[:40]
    return label or None


class RelayHub:
    def __init__(self, journeys: JourneyStore, relay_mode: str):
        self.journeys = journeys
        self.relay_mode = relay_mode
        self.rooms: dict[str, _Room] = {}
        self.on_end = None   # optional async callback(journey_id, reason), used by the family hub

    # ------------------------------------------------------------ lifecycle
    async def end(self, jid: str, reason: str) -> None:
        """Tell viewers, close every socket with 4410, purge the journey."""
        room = self.rooms.pop(jid, None)
        self.journeys.purge(jid, reason)
        if self.on_end is not None:
            await self.on_end(jid, reason)
        if room is None:
            return
        msg = json.dumps({"type": "ended", "reason": reason})
        for ws in list(room.viewers):
            await _safe_send(ws, msg)
            await _safe_close(ws, CLOSE_ENDED)
        if room.walker is not None:
            await _safe_close(room.walker, CLOSE_ENDED)

    async def sweep(self) -> None:
        for jid in self.journeys.sweep_expired():
            await self.end(jid, "expired")
        await self.check_silence()

    async def check_silence(self, silent_after_s: float = C.WALKER_SILENT_S) -> None:
        """Tell viewers when the walker's phone has gone quiet. Uses only message timing, never location."""
        t = time.monotonic()
        for jid, room in list(self.rooms.items()):
            j = self.journeys.get(jid)
            if j is None or not room.viewers or not j.last_walker_at or j.silent_sent:
                continue
            quiet = t - j.last_walker_at
            if quiet >= silent_after_s:
                j.silent_sent = True
                msg = json.dumps({"type": "walker_silent", "silent_s": int(quiet)})
                for v in list(room.viewers):
                    await _safe_send(v, msg)

    async def _tell_walker(self, room: "_Room", message: dict) -> None:
        if room.walker is not None:
            await _safe_send(room.walker, json.dumps(message))

    async def end_all(self) -> None:
        for jid in list(self.rooms) + [j for j in self.journeys.clear()]:
            await self.end(jid, "stopped")

    # ------------------------------------------------------------ connection
    async def handle(self, ws: WebSocket, jid: str) -> None:
        await ws.accept()
        try:
            role, journey, label = await self._auth(ws, jid)
        except _Close as c:
            await _safe_close(ws, c.code)
            return
        room = self.rooms.setdefault(jid, _Room())
        if role == "walker":
            if room.walker is not None:
                await _safe_close(room.walker, 1000)  # a new walker connection replaces the old one
            room.walker = ws
            journey.last_walker_at, journey.silent_sent = time.monotonic(), False
        else:
            if len(room.viewers) >= C.RELAY_MAX_VIEWERS:
                await _safe_close(ws, CLOSE_RATE)
                return
            room.viewers.add(ws)
        await ws.send_text(json.dumps({"type": "ready", "relay_mode": self.relay_mode,
                                       "expires_at": journey.expires_at.isoformat()}))
        if role == "walker":
            await self._tell_walker(room, {"type": "viewers", "count": len(room.viewers)})
        else:
            await self._tell_walker(room, {"type": "viewer_joined", "count": len(room.viewers), "label": label})
            if journey.latest is not None:
                await ws.send_text(journey.latest)
        try:
            if role == "walker":
                await self._walker_loop(ws, jid)
            else:
                await self._viewer_loop(ws)
        except _Close as c:
            await _safe_close(ws, c.code)
        except WebSocketDisconnect:
            pass
        finally:
            room = self.rooms.get(jid)
            if room is not None:
                if ws in room.viewers:
                    room.viewers.discard(ws)
                    await self._tell_walker(room, {"type": "viewer_left", "count": len(room.viewers)})
                if room.walker is ws:
                    room.walker = None

    async def _auth(self, ws: WebSocket, jid: str):
        try:
            text = await asyncio.wait_for(ws.receive_text(), timeout=AUTH_TIMEOUT_S)
            msg = json.loads(text)
        except (asyncio.TimeoutError, ValueError, WebSocketDisconnect, KeyError):
            raise _Close(CLOSE_BAD_TOKEN) from None
        if not isinstance(msg, dict) or msg.get("type") != "auth" or msg.get("role") not in ("walker", "viewer"):
            raise _Close(CLOSE_BAD_TOKEN)
        try:
            j = self.journeys.verify(jid, msg["role"], str(msg.get("token", "")))
        except JourneyError as e:
            raise _Close(e.close_code) from None
        return msg["role"], j, clean_label(msg.get("label")) if msg["role"] == "viewer" else None

    async def _viewer_loop(self, ws: WebSocket) -> None:
        while True:  # viewers only listen; anything they send is ignored
            await ws.receive_text()

    async def _walker_loop(self, ws: WebSocket, jid: str) -> None:
        bucket = _Bucket()
        while True:
            text = await ws.receive_text()
            if len(text.encode()) > C.RELAY_MAX_MSG_BYTES:
                raise _Close(CLOSE_TOO_BIG)
            if not bucket.take():
                raise _Close(CLOSE_RATE)
            try:
                msg = json.loads(text)
            except ValueError:
                raise _Close(CLOSE_WRONG_KIND) from None
            kind = msg.get("type") if isinstance(msg, dict) else None
            journey = self.journeys.get(jid)
            if journey is None:
                raise _Close(CLOSE_ENDED)
            journey.last_walker_at, journey.silent_sent = time.monotonic(), False
            if kind == "end":
                reason = msg.get("reason")
                if reason not in ("arrived", "stopped"):
                    raise _Close(CLOSE_WRONG_KIND)
                await self.end(jid, reason)
                return
            if kind != "loc":
                raise _Close(CLOSE_WRONG_KIND)
            if self.relay_mode == "e2ee":
                if "plain" in msg or not valid_envelope(msg.get("env")):
                    raise _Close(CLOSE_WRONG_KIND)
                if msg["env"]["seq"] <= journey.last_seq:
                    raise _Close(CLOSE_WRONG_KIND)
                journey.last_seq = msg["env"]["seq"]
            else:
                if "env" in msg or "plain" not in msg:
                    raise _Close(CLOSE_WRONG_KIND)
                try:
                    WalkerUpdate.model_validate(msg["plain"])
                except ValidationError:
                    raise _Close(CLOSE_WRONG_KIND) from None
            journey.latest = text
            room = self.rooms.get(jid)
            for v in list(room.viewers if room else []):
                await _safe_send(v, text)


async def _safe_send(ws: WebSocket, text: str) -> None:
    try:
        await ws.send_text(text)
    except Exception:  # noqa: BLE001 - a dead socket must never break the relay
        pass


async def _safe_close(ws: WebSocket, code: int) -> None:
    try:
        await ws.close(code=code)
    except Exception:  # noqa: BLE001
        pass
