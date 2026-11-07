"""Demo mode: three scripted trips (presets.json) and their closures."""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

from waykin.schemas import DemoPreset, DemoPresetFile

PRESETS_PATH = Path(__file__).resolve().parent / "presets.json"


@cache
def load_presets() -> tuple[DemoPresetFile, ...]:
    return tuple(DemoPresetFile.model_validate(p) for p in json.loads(PRESETS_PATH.read_text()))


def public_presets() -> list[DemoPreset]:
    return [DemoPreset.model_validate(p.model_dump(exclude={"hazard"})) for p in load_presets()]


def get_preset(preset_id: str) -> DemoPresetFile | None:
    return next((p for p in load_presets() if p.id == preset_id), None)
