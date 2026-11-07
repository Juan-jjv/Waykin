"""GET /api/meta and GET /api/_ws_schemas."""

from __future__ import annotations

from fastapi import APIRouter

from waykin import constants as C
from waykin import mocks
from waykin.api.deps import StateDep
from waykin.demo import public_presets
from waykin.provenance import build_provenance
from waykin.schemas import Meta, Thresholds, WsSchemas
from waykin.state import AppState

router = APIRouter(tags=["meta"])


@router.get("/meta", response_model=Meta)
async def get_meta(state: AppState = StateDep) -> Meta:
    s = state.settings
    presets = public_presets() if s.DEMO_MODE else []
    if state.mock:
        m = mocks.load("meta")
        m.update(
            provenance=build_provenance(state, s.DEFAULT_RADIUS_M).model_dump(mode="json"),
            default_radius_m=s.DEFAULT_RADIUS_M,
            relay_mode=s.relay_mode,
            demo_mode=s.DEMO_MODE,
            demo_presets=[p.model_dump(mode="json") for p in presets],
        )
        return Meta.model_validate(m)
    b = state.exposure
    return Meta(
        provenance=build_provenance(state, s.DEFAULT_RADIUS_M),
        radii=[int(r) for r in b.radii],
        default_radius_m=s.DEFAULT_RADIUS_M,
        bbox=list(C.DEMO_BBOX),
        categories=list(b.categories),
        category_preset=b.category_preset,
        relay_mode=s.relay_mode,
        n_draws=C.N_DRAWS,
        thresholds=Thresholds(),
        demo_mode=s.DEMO_MODE,
        demo_presets=presets,
    )


@router.get("/_ws_schemas", response_model=WsSchemas)
async def ws_schemas() -> WsSchemas:
    """Exists only so the WebSocket message models are part of OpenAPI."""
    return WsSchemas()
