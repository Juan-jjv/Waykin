from __future__ import annotations

import hmac
import json
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException, Request

MOCKS = Path(__file__).resolve().parent.parent / "mocks"
DEMO = Path(__file__).resolve().parent.parent / "demo"


def get_state(request: Request):
    return request.app.state.waykin


@lru_cache(maxsize=None)
def mock(name: str) -> dict:
    return json.loads((MOCKS / f"{name}.json").read_text())


def demo_presets() -> list[dict]:
    p = DEMO / "presets.json"
    return json.loads(p.read_text()) if p.exists() else []


def api_error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})


def require_admin(request: Request) -> None:
    s = request.app.state.waykin.settings
    if s.DEMO_MODE:
        return
    token = request.headers.get("X-Admin-Token", "")
    if not hmac.compare_digest(token.encode(), s.ADMIN_TOKEN.encode()):
        raise api_error(403, "forbidden", "admin token required")
