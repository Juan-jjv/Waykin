from fastapi import APIRouter, Depends, Request, Response, WebSocket

from waykin import schemas as S
from waykin.api.deps import api_error, get_state
from waykin.realtime.journeys import JourneyError

router = APIRouter()


@router.post("/journeys", response_model=S.JourneyCreated, status_code=201)
def create_journey(req: S.JourneyCreate | None = None, state=Depends(get_state)) -> S.JourneyCreated:
    ttl = (req.expires_in_min if req and "expires_in_min" in req.model_fields_set else state.settings.JOURNEY_TTL_MIN)
    j, walker, viewer = state.journeys.create(ttl)
    return S.JourneyCreated(journey_id=j.journey_id, walker_token=walker, viewer_token=viewer,
                            expires_at=j.expires_at, relay_mode=state.settings.relay_mode)


@router.delete("/journeys/{journey_id}", status_code=204)
async def delete_journey(journey_id: str, request: Request, state=Depends(get_state)) -> Response:
    auth = request.headers.get("Authorization", "")
    token = auth[7:] if auth.startswith("Bearer ") else ""
    try:
        state.journeys.verify(journey_id, "walker", token)
    except JourneyError as e:
        if e.code == "not_found":
            raise api_error(404, "not_found", "unknown journey") from None
        if e.code == "expired":
            raise api_error(410, "expired", "journey has ended") from None
        raise api_error(401, "forbidden", "walker token required") from None
    await state.relay.end(journey_id, "stopped")
    return Response(status_code=204)


@router.websocket("/relay/{journey_id}")
async def relay(ws: WebSocket, journey_id: str) -> None:
    await ws.app.state.waykin.relay.handle(ws, journey_id)
