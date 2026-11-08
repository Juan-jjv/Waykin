"""Internal route candidate types shared with data assessment."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b
from typing import Literal

import numpy as np

RouteLabel = Literal["fastest", "lower_exposure", "uncapped"]
TravelMode = Literal["walk", "drive"]


@dataclass(frozen=True)
class Candidate:
    label: RouteLabel
    route_id: str
    edge_ids: np.ndarray
    node_ids: np.ndarray
    minutes: float
    distance_m: float
    exposure_mean: float
    lam: float = 0.0
    avoid_m: float = 0.0          # metres inside no-go zones (see walk_pressure.avoid_zones)


@dataclass
class CandidateSet:
    fastest: Candidate
    alternatives: list[Candidate]
    uncapped: Candidate | None = None

    @property
    def lower_exposure(self) -> Candidate | None:
        return next((item for item in self.alternatives if item.label == "lower_exposure"), None)

    @property
    def candidates(self) -> tuple[Candidate, ...]:
        return (self.fastest, *self.alternatives, *((self.uncapped,) if self.uncapped is not None else ()))


class OutsideAreaError(ValueError):
    """A route endpoint is outside or too far from the demo graph."""


class NoPathError(ValueError):
    """No unblocked path for the travel mode connects the snapped nodes."""


class ModeUnavailableError(ValueError):
    """The graph has no edges for the requested travel mode (for example an older walk-only build)."""


def route_id_for(edge_ids: np.ndarray) -> str:
    return blake2b(np.asarray(edge_ids, dtype=np.int32).tobytes()).hexdigest()[:10]
