"""Public, read-only hazard stream: snapshot on connect, then added/removed events and a ping every 20 s."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from contextlib import suppress
from typing import Any

from starlette.websockets import WebSocket, WebSocketDisconnect

log = logging.getLogger("waykin.hazard_stream")

PING_INTERVAL_S = 20.0
QUEUE_MAX = 256


class HazardStreamHub:
    def __init__(self, ping_interval_s: float = PING_INTERVAL_S) -> None:
        self.ping_interval_s = ping_interval_s
        self._clients: set[asyncio.Queue[str]] = set()

    def __len__(self) -> int:
        return len(self._clients)

    def publish(self, message: dict[str, Any]) -> None:
        """Called synchronously from the event loop thread (HazardStore changes)."""
        text = json.dumps(message, default=str)
        for q in list(self._clients):
            try:
                q.put_nowait(text)
            except asyncio.QueueFull:
                self._clients.discard(q)  # too slow: drop it, its sender will notice

    async def handle(self, ws: WebSocket, snapshot: Callable[[], dict[str, Any]]) -> None:
        await ws.accept()
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=QUEUE_MAX)
        first = json.dumps(snapshot(), default=str)
        self._clients.add(q)  # registered in the same tick as the snapshot: no event is missed
        try:
            await ws.send_text(first)
            sender = asyncio.create_task(self._sender(ws, q))
            receiver = asyncio.create_task(self._drain(ws))
            _, pending = await asyncio.wait({sender, receiver}, return_when=asyncio.FIRST_COMPLETED)
            for t in pending:
                t.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await t
        except Exception:
            pass  # dead sockets are dropped quietly
        finally:
            self._clients.discard(q)

    async def _sender(self, ws: WebSocket, q: asyncio.Queue[str]) -> None:
        while q in self._clients or not q.empty():
            try:
                text = await asyncio.wait_for(q.get(), timeout=self.ping_interval_s)
            except TimeoutError:
                text = '{"type": "ping"}'
            await ws.send_text(text)

    async def _drain(self, ws: WebSocket) -> None:
        try:
            while True:
                await ws.receive_text()
        except (WebSocketDisconnect, RuntimeError, KeyError):
            return
