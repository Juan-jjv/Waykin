"""Shared FastAPI dependencies."""

from __future__ import annotations

import hmac

from fastapi import Depends, Header, Request

from waykin.api.errors import ApiError
from waykin.state import AppState, get_state

StateDep = Depends(get_state)


def require_admin(request: Request, x_admin_token: str | None = Header(default=None)) -> None:
    state: AppState = get_state(request)
    if state.settings.DEMO_MODE:
        return
    expected = state.settings.ADMIN_TOKEN.encode()
    if not x_admin_token or not hmac.compare_digest(x_admin_token.encode(), expected):
        raise ApiError(401, "forbidden", "Admin token required.")


def require_demo(request: Request) -> None:
    if not get_state(request).settings.DEMO_MODE:
        raise ApiError(404, "not_found", "Demo mode is off.")
