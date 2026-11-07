"""POST /api/routes and /api/routes/reroute: thin wrappers around routing.service.plan.

The reroute handler never touches state.journeys, cookies or the Authorization header:
the server cannot link a reroute to a person or a journey.
"""

from __future__ import annotations

from fastapi import APIRouter
from starlette.concurrency import run_in_threadpool

from waykin import mocks
from waykin.api.deps import StateDep
from waykin.api.errors import ApiError
from waykin.provenance import build_provenance
from waykin.schemas import Error, LatLon, RerouteRequest, RoutesRequest, RoutesResponse
from waykin.state import AppState

router = APIRouter(tags=["routes"])
_ERRORS = {422: {"model": Error}}


async def _plan(state: AppState, origin: LatLon, destination: LatLon, radius_m: int | None) -> RoutesResponse:
    r = int(radius_m or state.settings.DEFAULT_RADIUS_M)
    mask = state.hazards.blocked_mask()  # computed on the event loop, read-only afterwards

    if state.mock:
        blocked = set(state.hazards.blocked_edge_ids())
        fx = mocks.load(mocks.route_fixture_name(origin.lat, blocked))
        fx["provenance"] = build_provenance(state, r).model_dump(mode="json")
        fx["blocked_edge_count"] = int(mask.sum())
        return RoutesResponse.model_validate(fx)

    if r not in state.exposure.radii:
        raise ApiError(422, "validation", "That radius is not loaded on this server.")

    from waykin.routing import service
    from waykin.routing.types import NoPathError, OutsideAreaError

    try:
        return await run_in_threadpool(service.plan, state, origin, destination, r)
    except OutsideAreaError:
        raise ApiError(422, "outside_area", "A point is outside the mapped area.") from None
    except NoPathError:
        raise ApiError(422, "no_path", "No walking path connects these points.") from None


@router.post("/routes", response_model=RoutesResponse, responses=_ERRORS)
async def post_routes(req: RoutesRequest, state: AppState = StateDep) -> RoutesResponse:
    return await _plan(state, req.origin, req.destination, req.radius_m)


@router.post("/routes/reroute", response_model=RoutesResponse, responses=_ERRORS)
async def post_reroute(req: RerouteRequest, state: AppState = StateDep) -> RoutesResponse:
    return await _plan(state, req.position, req.destination, req.radius_m)
