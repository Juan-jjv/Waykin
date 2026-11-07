"""Demo mode endpoints (DEMO_MODE=1 only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from waykin.api.deps import StateDep, require_demo
from waykin.api.errors import ApiError
from waykin.demo import get_preset
from waykin.schemas import Error, Hazard, HazardCreate
from waykin.state import AppState

router = APIRouter(prefix="/demo", tags=["demo"], dependencies=[Depends(require_demo)],
                   responses={404: {"model": Error}})

DEMO_HAZARD_TTL_MIN = 10


@router.post("/reset", status_code=204)
async def reset(state: AppState = StateDep) -> Response:
    state.hazards.clear()
    await state.relay.reset()
    state.journeys.clear()
    return Response(status_code=204)


@router.post("/trigger/{preset_id}", response_model=Hazard)
async def trigger(preset_id: str, state: AppState = StateDep) -> Hazard:
    p = get_preset(preset_id)
    if p is None or p.hazard is None:
        raise ApiError(404, "not_found", "No scripted closure for that preset.")
    hid = f"hz_demo_{p.id}"
    state.hazards.remove(hid)  # re-triggering replaces it: same id, same edges, deterministic
    req = HazardCreate(kind="closure", lat=p.hazard.lat, lon=p.hazard.lon, radius_m=p.hazard.radius_m,
                       ttl_min=DEMO_HAZARD_TTL_MIN, description=p.hazard.description)
    return state.hazards.add(req, source="demo", hazard_id=hid)
