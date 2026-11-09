"""Demo controls (DEMO_MODE=1 only; 404 otherwise). Used by the presenter key and demo/smoke.py.

POST /api/demo/trigger/{preset_id}  adds the preset's scripted closure (replacing any earlier demo closure)
POST /api/demo/reset                clears hazards, ends every journey, closes every relay socket
"""
from fastapi import APIRouter, Depends, Request, Response

from waykin import schemas as S
from waykin.api.deps import api_error, get_state
from waykin.demo import get_preset, hazard_request


def require_demo(request: Request) -> None:
    if not request.app.state.waykin.settings.DEMO_MODE:
        raise api_error(404, "not_found", "not found")


router = APIRouter(prefix="/demo", dependencies=[Depends(require_demo)])


@router.post("/trigger/{preset_id}", response_model=S.Hazard, status_code=201)
def trigger(preset_id: str, state=Depends(get_state)) -> S.Hazard:
    p = get_preset(state.settings, preset_id)
    if p is None:
        raise api_error(404, "not_found", "unknown preset")
    req = hazard_request(p)
    if req is None:
        raise api_error(422, "validation", "this preset has no scripted closure")
    for h in state.hazards.list():
        if h.source == "demo":
            state.hazards.remove(h.hazard_id)
    return state.hazards.add(req, source="demo")


@router.post("/reset", status_code=204)
async def reset(state=Depends(get_state)) -> Response:
    state.hazards.clear()
    await state.relay.end_all()
    return Response(status_code=204)
