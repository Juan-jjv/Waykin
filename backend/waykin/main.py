"""FastAPI app factory. Run with: uvicorn waykin.main:app --workers 1 --no-access-log

waykin.routing and waykin.data are imported only inside build_state(), and only when
WAYKIN_MOCK=0, so mock mode works while those folders are still half-built.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections.abc import Awaitable, Callable
from contextlib import asynccontextmanager, suppress
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from waykin import __version__
from waykin.api import demo, hazards, incidents, journeys, meta, routes
from waykin.api.errors import error_response, install_error_handlers
from waykin.config import Settings, get_settings
from waykin.realtime.hazard_store import EdgeResolver, HazardStore
from waykin.realtime.hazard_stream import HazardStreamHub
from waykin.realtime.journeys import JourneyStore
from waykin.realtime.relay import RelayHub
from waykin.state import AppState

log = logging.getLogger("waykin")
access_log = logging.getLogger("waykin.access")

CSP = "default-src 'self'; img-src 'self' data: https://*.tile.openstreetmap.org; connect-src 'self' wss: ws:"


# ---------------------------------------------------------------- state
def make_state(settings: Settings, graph: Any = None, exposure: Any = None,
               edge_resolver: EdgeResolver | None = None, n_edges: int | None = None) -> AppState:
    """Wire the in-memory stores. graph/exposure None means mock mode."""
    if graph is None or exposure is None:
        from waykin import mocks

        graph = exposure = None
        n_edges = n_edges or mocks.MOCK_N_EDGES
        edge_resolver = edge_resolver or mocks.mock_hazard_edges
    else:
        n_edges = n_edges or int(graph.n_edges)
        if edge_resolver is None:
            from waykin.routing.hazards import hazard_edges

            def edge_resolver(lat: float, lon: float, radius_m: float, _g=graph):
                return hazard_edges(_g, lat, lon, radius_m)

    journeys_store = JourneyStore()
    return AppState(
        settings=settings,
        graph=graph,
        exposure=exposure,
        hazards=HazardStore(n_edges, edge_resolver, HazardStreamHub()),
        journeys=journeys_store,
        relay=RelayHub(journeys_store, plaintext=settings.RELAY_PLAINTEXT),
    )


def build_state(settings: Settings) -> AppState:
    if settings.WAYKIN_MOCK:
        log.info("mock mode: serving fixtures, no graph or exposure loaded")
        return make_state(settings)
    from waykin.data.bundle import load_exposure
    from waykin.routing.graph import load_graph

    graph = load_graph(settings.build_dir / "graph")
    exposure = load_exposure(settings.build_dir, settings.EXPOSURE_SOURCE, settings.load_radii, graph.graph_hash)
    log.info("loaded graph (%d edges) and %s exposure", graph.n_edges, settings.EXPOSURE_SOURCE)
    return make_state(settings, graph, exposure)


# ---------------------------------------------------------------- middleware
class AccessLogAndHeaders:
    """Logs only method, route template, status and latency. Never query strings, bodies or path params."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        t0 = time.perf_counter()
        is_api = scope["path"].startswith("/api")
        status: int | str = 500 if scope["type"] == "http" else "-"

        async def send_wrapper(msg: Message) -> None:
            nonlocal status
            if msg["type"] == "http.response.start":
                status = msg["status"]
                h = MutableHeaders(scope=msg)
                h["Referrer-Policy"] = "no-referrer"
                h["Content-Security-Policy"] = CSP
                h["X-Content-Type-Options"] = "nosniff"
                if is_api:
                    h["Cache-Control"] = "no-store"
            elif msg["type"] == "websocket.close":
                status = msg.get("code", 1000)
            elif msg["type"] == "websocket.accept" and status == "-":
                status = 101
            await send(msg)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            route = scope.get("route")
            template = getattr(route, "path", None)
            if template is None:
                template = "/api/<unmatched>" if is_api else "<static>"
            elif is_api and not template.startswith("/api"):
                template = "/api" + template  # included routers report their path without the prefix
            method = scope.get("method", "WS")
            access_log.info("%s %s %s %.1fms", method, template, status, (time.perf_counter() - t0) * 1000)


# ---------------------------------------------------------------- background tasks
async def _every(interval_s: float, fn: Callable[[], Awaitable[Any] | Any], name: str) -> None:
    while True:
        await asyncio.sleep(interval_s)
        try:
            r = fn()
            if asyncio.iscoroutine(r):
                await r
        except Exception as e:  # never let a sweep die; never log values
            log.warning("%s failed: %s", name, type(e).__name__)


def _start_city_feed(state: AppState) -> asyncio.Task | None:
    try:
        from waykin.routing import city_feed
    except ImportError:
        log.warning("CITY_FEED=1 but waykin.routing.city_feed is not available")
        return None
    run = getattr(city_feed, "run", None)
    if run is None:
        log.warning("CITY_FEED=1 but city_feed.run(state) is not defined")
        return None
    return asyncio.create_task(run(state))


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings
    tasks: set[asyncio.Task] = app.state.background
    if app.state.waykin is None:
        app.state.waykin = build_state(settings)
    state: AppState = app.state.waykin

    tasks.add(asyncio.create_task(_every(settings.SWEEP_INTERVAL_S, state.relay.sweep_expired, "journey sweep")))
    tasks.add(asyncio.create_task(_every(settings.SWEEP_INTERVAL_S, state.hazards.sweep_expired, "hazard sweep")))
    if settings.CITY_FEED and not state.mock:
        t = _start_city_feed(state)
        if t is not None:
            tasks.add(t)
    if "ADMIN_TOKEN" not in os.environ:
        print(f"[waykin] ADMIN_TOKEN for this run: {settings.ADMIN_TOKEN}", flush=True)
    try:
        yield
    finally:
        for t in list(tasks):
            t.cancel()
        for t in list(tasks):
            with suppress(asyncio.CancelledError, Exception):
                await t
        tasks.clear()


# ---------------------------------------------------------------- factory
def create_app(settings: Settings | None = None, state: AppState | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="WayKin API",
        version=__version__,
        lifespan=lifespan,
        separate_input_output_schemas=False,
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url=None,
    )
    app.state.settings = settings
    app.state.waykin = state
    app.state.background = set()
    install_error_handlers(app)

    for r in (meta.router, incidents.router, routes.router, journeys.router, hazards.router, demo.router):
        app.include_router(r, prefix="/api")

    @app.get("/openapi.json", include_in_schema=False)
    async def openapi_root() -> dict:
        return app.openapi()

    if settings.serve_frontend:
        _mount_spa(app, settings)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Admin-Token"],
    )
    app.add_middleware(AccessLogAndHeaders)
    return app


def _mount_spa(app: FastAPI, settings: Settings) -> None:
    dist = settings.FRONTEND_DIST.resolve()
    index = dist / "index.html"

    @app.get("/{full_path:path}", include_in_schema=False)
    async def spa(full_path: str):
        if full_path == "api" or full_path.startswith("api/"):
            return error_response(404, "not_found", "Unknown API path.")
        if full_path:
            candidate = (dist / full_path).resolve()
            if candidate.is_file() and candidate.is_relative_to(dist):
                return FileResponse(candidate)
        return FileResponse(index)


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
app = create_app()
