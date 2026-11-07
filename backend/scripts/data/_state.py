"""Shared helpers for the offline measurement scripts."""
from __future__ import annotations

import inspect
import os
from pathlib import Path

ROUTER_NOT_READY = "A3's real router is not in place yet, so this measurement would be meaningless. Nothing was written."


def load_state(data_dir: str | None = None, radii: str | None = None):
    """The real AppState (graph + exposure), loaded exactly as the server loads it."""
    from waykin.config import Settings
    from waykin.main import build_state

    settings = Settings(WAYKIN_MOCK=False, DATA_DIR=Path(data_dir or os.getenv("DATA_DIR", "../data")),
                        LOAD_RADII=radii or os.getenv("LOAD_RADII", "100"), ADMIN_TOKEN="offline")
    return build_state(settings)[0]


def require_real_router() -> None:
    """The stub planner answers no_alternative for every trip, which would look like a 100% abstention result."""
    from waykin.routing import service

    if "stub-route" in inspect.getsource(service):
        raise SystemExit(ROUTER_NOT_READY)


def results_dir(path: str | None = None) -> Path:
    d = Path(path or os.getenv("RESULTS_DIR", "../results")) / "data"
    d.mkdir(parents=True, exist_ok=True)
    return d
