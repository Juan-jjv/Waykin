"""POST/DELETE /api/journeys and WS /api/relay/{journey_id}."""

from __future__ import annotations

from fastapi import APIRouter, Header, Response, WebSocket

from waykin.api.deps import StateDep
from waykin.api.errors import ApiError
from waykin.realtime.journeys import JourneyError, JourneyExpired
from waykin.schemas import Error, JourneyCreate, JourneyCreated
from waykin.state import AppState, get_state

router = APIRouter(tags=["journeys"])


@router.post("/journeys", response_model=JourneyCreated, status_code=201)
async def create_journey(body: JourneyCreate | None = None, state: AppState = StateDep) -> JourneyCreated:
    ttl = (body.expires_in_min if body and body.expires_in_min else None) or state.settings.JOURNEY_TTL_MIN
    j, walker_token, viewer_token = state.journeys.create(ttl)
    return JourneyCreated(journey_id=j.journey_id, walker_token=walker_token, viewer_token=viewer_token,
                          expires_at=j.expires_at, relay_mode=state.settings.relay_mode)


@router.delete("/journeys/{journey_id}", status_code=204,
               responses={401: {"model": Error}, 404: {"model": Error}, 410: {"model": Error}})
async def delete_journey(journey_id: str, authorization: str | None = Header(default=None),
                         state: AppState = StateDep) -> Response:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise ApiError(401, "invalid_token", "Walker token required.")
    try:
        state.journeys.verify(journey_id, "walker", token.strip())
    except JourneyExpired:
        await state.relay.end_journey(journey_id, "expired")
        raise ApiError(410, "expired", "Journey ended or expired.") from None
    except JourneyError as e:
        raise ApiError(e.http_status, e.code, e.message) from None
    await state.relay.end_journey(journey_id, "stopped")
    return Response(status_code=204)


@router.websocket("/relay/{journey_id}")
async def relay(ws: WebSocket, journey_id: str) -> None:
    await get_state(ws).relay.handle(ws, journey_id)
