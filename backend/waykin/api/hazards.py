from fastapi import APIRouter, Depends, Response, WebSocket

from waykin import schemas as S
from waykin.api.deps import api_error, get_state, require_admin

router = APIRouter()


@router.get("/hazards", response_model=S.HazardList)
def list_hazards(state=Depends(get_state)) -> S.HazardList:
    """Public: anyone may see current closures."""
    return S.HazardList(hazards=state.hazards.list(), blocked_edge_ids=state.hazards.blocked_ids())


@router.post("/hazards", response_model=S.Hazard, status_code=201, dependencies=[Depends(require_admin)])
def add_hazard(req: S.HazardCreate, state=Depends(get_state)) -> S.Hazard:
    return state.hazards.add(req, source="demo" if state.settings.DEMO_MODE else "manual")


@router.delete("/hazards/{hazard_id}", status_code=204, dependencies=[Depends(require_admin)])
def remove_hazard(hazard_id: str, state=Depends(get_state)) -> Response:
    if state.hazards.remove(hazard_id) is None:
        raise api_error(404, "not_found", "unknown hazard")
    return Response(status_code=204)


@router.websocket("/hazards/stream")
async def hazard_stream(ws: WebSocket) -> None:
    await ws.app.state.hazard_stream.handle(ws)
