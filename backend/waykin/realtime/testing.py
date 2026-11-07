"""Test helpers for the relay and journeys (no pytest dependency; used by tests/api and tests/privacy)."""

from __future__ import annotations

import base64
import json
from typing import Any

from starlette.websockets import WebSocketDisconnect


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def fake_env(seq: int, ct_len: int = 64) -> dict[str, Any]:
    """A shape-valid Envelope. The server never looks inside ct, so the bytes don't matter."""
    return {"v": 1, "seq": seq, "iv": b64u(bytes(12)), "ct": b64u(bytes(ct_len))}


def aes_env(key: bytes, journey_id: str, seq: int, upd: dict[str, Any], iv: bytes | None = None) -> dict[str, Any]:
    """A real AES-GCM envelope, byte-compatible with frontend/src/lib/crypto.ts (needs `cryptography`)."""
    import os

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    iv = iv if iv is not None else os.urandom(12)
    aad = f"waykin:v1:{journey_id}:{seq}".encode()
    ct = AESGCM(key).encrypt(iv, json.dumps(upd).encode(), aad)
    return {"v": 1, "seq": seq, "iv": b64u(iv), "ct": b64u(ct)}


def aes_open(key: bytes, journey_id: str, env: dict[str, Any]) -> dict[str, Any]:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    def dec(s: str) -> bytes:
        return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))

    aad = f"waykin:v1:{journey_id}:{env['seq']}".encode()
    return json.loads(AESGCM(key).decrypt(dec(env["iv"]), dec(env["ct"]), aad))


def walker_update(lat: float = 53.52013, lon: float = -113.51234, **kw: Any) -> dict[str, Any]:
    u = {"lat": lat, "lon": lon, "accuracy_m": 5.0, "ts": 1_762_480_000_000, "status": "walking", "eta_min": 9.5}
    u.update(kw)
    return u


def new_journey(client: Any, **body: Any) -> dict[str, Any]:
    r = client.post("/api/journeys", json=body or None)
    assert r.status_code == 201, r.text
    return r.json()


def auth(ws: Any, role: str, token: str) -> dict[str, Any]:
    ws.send_text(json.dumps({"type": "auth", "role": role, "token": token}))
    return ws.receive_json()


def send(ws: Any, msg: dict[str, Any]) -> None:
    ws.send_text(json.dumps(msg))


def close_code(ws: Any) -> int:
    """Read until the server closes the socket; return the close code."""
    try:
        while True:
            ws.receive_text()
    except WebSocketDisconnect as e:
        return e.code
