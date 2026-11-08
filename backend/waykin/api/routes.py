"""POST /routes and /routes/reroute: thin wrappers around A3's service.plan (spec A4.5).

Reroute never touches journeys, cookies or the Authorization header, and nothing here logs coordinates.
"""
from fastapi import APIRouter, Depends
from starlette.concurrency import run_in_threadpool

from waykin import schemas as S
from waykin.api.deps import get_state, mock

router = APIRouter()


def _mock_routes(lat: float) -> S.RoutesResponse:
    # Fixture chosen by origin latitude parity (4th decimal), so the UI can see both outcomes.
    name = "routes_recommend" if int(round(lat * 1e4)) % 2 == 0 else "routes_abstain"
    return S.RoutesResponse.model_validate(mock(name))


@router.post("/routes", response_model=S.RoutesResponse)
async def routes(req: S.RoutesRequest, state=Depends(get_state)) -> S.RoutesResponse:
    if state.settings.WAYKIN_MOCK:
        return _mock_routes(req.origin.lat)
    from waykin.routing import service
    radius = req.radius_m or state.settings.DEFAULT_RADIUS_M
    return await run_in_threadpool(service.plan, state, req.origin, req.destination, radius, req.mode)


@router.post("/routes/reroute", response_model=S.RoutesResponse)
async def reroute(req: S.RerouteRequest, state=Depends(get_state)) -> S.RoutesResponse:
    if state.settings.WAYKIN_MOCK:
        return S.RoutesResponse.model_validate(mock("routes_reroute"))
    from waykin.routing import service
    radius = req.radius_m or state.settings.DEFAULT_RADIUS_M
    return await run_in_threadpool(service.plan, state, req.position, req.destination, radius, req.mode)
