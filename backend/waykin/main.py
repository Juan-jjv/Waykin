"""FastAPI app factory (spec A4.4). Run with: uvicorn waykin.main:app --workers 1 --no-access-log

Mock mode (WAYKIN_MOCK=1) loads no data and never imports waykin.routing or waykin.data, so it works
even while those folders are half-built. Journeys and the relay run for real in both modes.
"""
from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from waykin.api import demo, hazards, journeys, meta, routes
from waykin.api.deps import mock
from waykin.config import Settings
from waykin.realtime.hazard_store import HazardStore
from waykin.realtime.hazard_stream import HazardStreamHub
from waykin.realtime.journeys import JourneyStore
from waykin.realtime.relay import RelayHub
from waykin.schemas import Hazard
from waykin.state import AppState

log = logging.getLogger("waykin")
access = logging.getLogger("waykin.access")
DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"
SWEEP_S = 15.0
NO_STORE = ("/api/routes", "/api/journeys", "/api/relay")
CSP = ("default-src 'self'; img-src 'self' data: blob: https://tiles.openfreemap.org; "
       "worker-src 'self' blob:; "   # MapLibre runs its tile workers from blob: URLs
       "connect-src 'self' wss: ws: https://tiles.openfreemap.org https://photon.komoot.io")


def build_state(settings: Settings) -> tuple[AppState, HazardStreamHub]:
    """Create the in-memory state. Real mode loads the graph and exposure artifacts."""
    jstore = JourneyStore()
    relay = RelayHub(jstore, settings.relay_mode)
    if settings.WAYKIN_MOCK:
        fixture = Hazard.model_validate(mock("hazard_closure"))
        hub = HazardStreamHub(lambda: state.hazards, mock_fixture=fixture)
        hstore = HazardStore(n_edges=0, edge_mapper=lambda req: fixture.edge_ids, on_change=hub.publish)
        state = AppState(settings=settings, graph=None, exposure=None, hazards=hstore, journeys=jstore, relay=relay)
        return state, hub
    from waykin.data.bundle import load_exposure
    from waykin.routing.graph import load_graph
    from waykin.routing.hazards import hazard_edges

    graph = load_graph(settings.build_dir / "graph")
    bundle = load_exposure(settings.build_dir / "exposure", settings.EXPOSURE_SOURCE, settings.load_radii,
                           graph.graph_hash)
    hub = HazardStreamHub(lambda: state.hazards)
    hstore = HazardStore(n_edges=graph.n_edges,
                         edge_mapper=lambda req: hazard_edges(graph, req.lat, req.lon, req.radius_m).tolist(),
                         on_change=hub.publish)
    state = AppState(settings=settings, graph=graph, exposure=bundle, hazards=hstore, journeys=jstore, relay=relay)
    return state, hub


def create_app(settings: Settings | None = None, state: AppState | None = None) -> FastAPI:
    settings = settings or (state.settings if state else Settings())

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if state is None:
            app.state.waykin, app.state.hazard_stream = build_state(settings)
        else:
            app.state.waykin = state
            app.state.hazard_stream = HazardStreamHub(lambda: state.hazards)
            state.hazards.on_change = app.state.hazard_stream.publish
        if not settings.DEMO_MODE and not settings.WAYKIN_MOCK:
            log.warning("admin token for hazard posting: %s", settings.ADMIN_TOKEN)
        sweeper = asyncio.create_task(_sweep(app))
        yield
        sweeper.cancel()

    app = FastAPI(title="WayKin API", version="1", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["*"],
                       allow_headers=["*"])

    @app.middleware("http")
    async def hygiene(request: Request, call_next):
        t = time.perf_counter()
        response = await call_next(request)
        route = request.scope.get("route")
        template = getattr(route, "path", "static")
        # Only method, route template, status and latency: never query strings, bodies or path values.
        access.info("%s %s %s %.0fms", request.method, template, response.status_code, (time.perf_counter() - t) * 1000)
        if request.url.path.startswith(NO_STORE):
            response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = CSP
        return response

    _install_error_handlers(app)
    for r in (meta.router, routes.router, journeys.router, hazards.router, demo.router):
        app.include_router(r, prefix="/api")

    if DIST.is_dir():
        @app.get("/{path:path}", include_in_schema=False)
        def spa(path: str):
            if path.startswith("api/"):
                return JSONResponse({"error": {"code": "not_found", "message": "not found"}}, status_code=404)
            f = (DIST / path).resolve()
            if path and f.is_file() and DIST in f.parents:
                return FileResponse(f)
            return FileResponse(DIST / "index.html")

    return app


async def _sweep(app: FastAPI) -> None:
    while True:
        await asyncio.sleep(SWEEP_S)
        st = app.state.waykin
        await st.relay.sweep()
        st.hazards.sweep_expired()


def _err(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse({"error": {"code": code, "message": message}}, status_code=status)


def _install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        fields = sorted({".".join(str(p) for p in e.get("loc", ()) if p != "body") for e in exc.errors()})
        return _err(422, "validation", "invalid request: " + ", ".join(f for f in fields if f))

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        if isinstance(exc.detail, dict) and "code" in exc.detail:
            return _err(exc.status_code, exc.detail["code"], exc.detail["message"])
        code = {404: "not_found", 401: "forbidden", 403: "forbidden", 429: "rate_limited"}.get(exc.status_code,
                                                                                               "validation")
        return _err(exc.status_code, code, str(exc.detail))

    try:
        from waykin.routing.types import NoPathError, OutsideAreaError
    except ImportError:  # routing folder not created yet
        return

    @app.exception_handler(OutsideAreaError)
    async def _outside(request: Request, exc: OutsideAreaError):
        return _err(422, "outside_area", "Pick points inside the demo area.")

    @app.exception_handler(NoPathError)
    async def _nopath(request: Request, exc: NoPathError):
        return _err(422, "no_path", "No walking route found between these points.")


app = create_app()
