"""Demo mode (spec A4, H24-H29): the scripted presets and the closure each `reroute` preset triggers.

`demo/presets.json` (real mode) is a list of DemoPreset objects plus an optional `hazard` that is not part
of the API contract: /api/meta strips it. In mock mode the presets come from `mocks/meta.json`, and a
`reroute` preset's closure is the mock hazard fixture, so the closure -> reroute loop works with no data.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from waykin import schemas as S

PRESETS_PATH = Path(__file__).resolve().parent / "presets.json"
DEMO_HAZARD_TTL_MIN = 30


class PresetHazard(BaseModel):
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    radius_m: float = Field(default=40, ge=10, le=300)
    description: str = Field(default="Closure (demo)", max_length=140)


class PresetFile(S.DemoPreset):
    hazard: PresetHazard | None = None


def load_presets(path: Path = PRESETS_PATH) -> list[PresetFile]:
    if not path.exists():
        return []
    return [PresetFile.model_validate(p) for p in json.loads(path.read_text())]


def _mock_presets() -> list[PresetFile]:
    from waykin.api.deps import mock

    fx = mock("hazard_closure")
    out = []
    for p in mock("meta")["demo_presets"]:
        pf = PresetFile.model_validate(p)
        if pf.expected == "reroute":
            pf.hazard = PresetHazard(lat=fx["lat"], lon=fx["lon"], radius_m=fx["radius_m"],
                                     description=fx["description"])
        out.append(pf)
    return out


def presets_for(settings) -> list[PresetFile]:
    return _mock_presets() if settings.WAYKIN_MOCK else load_presets()


def get_preset(settings, preset_id: str) -> PresetFile | None:
    return next((p for p in presets_for(settings) if p.id == preset_id), None)


def hazard_request(p: PresetFile) -> S.HazardCreate | None:
    if p.hazard is None:
        return None
    return S.HazardCreate(kind="closure", lat=p.hazard.lat, lon=p.hazard.lon, radius_m=p.hazard.radius_m,
                          ttl_min=DEMO_HAZARD_TTL_MIN, description=p.hazard.description)
