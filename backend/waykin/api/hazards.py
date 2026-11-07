"""Hazard admin endpoints and the public read-only hazard stream."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Response, WebSocket

from waykin import mocks
from waykin.api.deps import StateDep, require_admin
from waykin.api.errors import ApiError
from waykin.schemas import Error, Hazard, HazardCreate, HazardList
from waykin.state import AppState, get_state

router = APIRouter(tags=["hazards"])
_AUTH = {401: {"model": Error}}


@router.get("/hazards", response_model=HazardList, dependencies=[Depends(require_admin)], responses=_AUTH)
async def list_hazards(state: AppState = StateDep) -> HazardList:
    return HazardList(hazards=state.hazards.list(), blocked_edge_ids=state.hazards.blocked_edge_ids())


@router.post("/hazards", response_model=Hazard, status_code=201, dependencies=[Depends(require_admin)],
             responses=_AUTH)
async def create_hazard(req: HazardCreate, state: AppState = StateDep) -> Hazard:
    return state.hazards.add(req, source="manual")


@router.delete("/hazards/{hazard_id}", status_code=204, dependencies=[Depends(require_admin)],
               responses={**_AUTH, 404: {"model": Error}})
async def delete_hazard(hazard_id: str, state: AppState = StateDep) -> Response:
    if not state.hazards.remove(hazard_id):
        raise ApiError(404, "not_found", "Unknown hazard.")
    return Response(status_code=204)


def add_mock_closure(state: AppState) -> Hazard | None:
    fx = mocks.load("hazard_closure")
    if state.hazards.get(fx["hazard_id"]) is not None:
        return None
    req = HazardCreate(kind=fx["kind"], lat=fx["lat"], lon=fx["lon"], radius_m=fx["radius_m"],
                       ttl_min=fx["ttl_min"], description=fx["description"])
    return state.hazards.add(req, source="demo", edge_ids=fx["edge_ids"], hazard_id=fx["hazard_id"])


async def _mock_closure_later(state: AppState, delay_s: float) -> None:
    await asyncio.sleep(delay_s)
    add_mock_closure(state)


@router.websocket("/hazards/stream")
async def hazard_stream(ws: WebSocket) -> None:
    state = get_state(ws)
    if state.mock:
        tasks: set = ws.app.state.background
        t = asyncio.create_task(_mock_closure_later(state, state.settings.MOCK_HAZARD_DELAY_S))
        tasks.add(t)
        t.add_done_callback(tasks.discard)
    await state.hazards.stream.handle(ws, state.hazards.snapshot)
