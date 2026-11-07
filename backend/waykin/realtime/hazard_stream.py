"""Public, read-only hazard stream (spec B5): snapshot on connect, then added/removed events, ping every 20 s.

The server never learns which walker a hazard affects: clients compare edge ids themselves.
"""
from __future__ import annotations

import asyncio
import json

from fastapi import WebSocket, WebSocketDisconnect

from waykin.schemas import Hazard

PING_S = 20.0


class HazardStreamHub:
    def __init__(self, store_getter, mock_fixture: Hazard | None = None, mock_delay_s: float = 15.0):
        self._store = store_getter
        self.clients: set[WebSocket] = set()
        self.mock_fixture = mock_fixture
        self.mock_delay_s = mock_delay_s
        self._loop: asyncio.AbstractEventLoop | None = None

    def publish(self, kind: str, h: Hazard) -> None:
        """Called synchronously by HazardStore on every change."""
        if kind == "added":
            msg = {"type": "hazard.added", "hazard": h.model_dump(mode="json")}
        else:
            msg = {"type": "hazard.removed", "hazard_id": h.hazard_id, "edge_ids": h.edge_ids}
        text = json.dumps(msg)
        loop = self._loop
        for ws in list(self.clients):
            if loop is not None:
                loop.create_task(self._send(ws, text))

    async def handle(self, ws: WebSocket) -> None:
        await ws.accept()
        self._loop = asyncio.get_running_loop()
        store = self._store()
        await ws.send_text(json.dumps({
            "type": "snapshot",
            "hazards": [h.model_dump(mode="json") for h in store.list()],
            "blocked_edge_ids": store.blocked_ids(),
        }))
        self.clients.add(ws)
        tasks = [asyncio.create_task(self._pinger(ws))]
        if self.mock_fixture is not None:
            tasks.append(asyncio.create_task(self._mock_emit(ws)))
        try:
            while True:
                await ws.receive_text()  # read-only stream: ignore anything sent
        except WebSocketDisconnect:
            pass
        finally:
            self.clients.discard(ws)
            for t in tasks:
                t.cancel()

    async def _pinger(self, ws: WebSocket) -> None:
        while True:
            await asyncio.sleep(PING_S)
            await self._send(ws, json.dumps({"type": "ping"}))

    async def _mock_emit(self, ws: WebSocket) -> None:
        await asyncio.sleep(self.mock_delay_s)
        await self._send(ws, json.dumps({"type": "hazard.added", "hazard": self.mock_fixture.model_dump(mode="json")}))

    async def _send(self, ws: WebSocket, text: str) -> None:
        try:
            await ws.send_text(text)
        except Exception:  # noqa: BLE001 - drop dead sockets quietly
            self.clients.discard(ws)
