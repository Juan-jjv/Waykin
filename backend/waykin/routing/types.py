"""Internal route candidate types shared with data assessment."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import blake2b
from typing import Literal

import numpy as np

RouteLabel = Literal["fastest", "balanced", "lower_exposure", "uncapped"]


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


@dataclass
class CandidateSet:
    fastest: Candidate
    alternatives: list[Candidate]
    uncapped: Candidate | None = None

    @property
    def lower_exposure(self) -> Candidate | None:
        return next((item for item in self.alternatives if item.label == "lower_exposure"), None)

    @property
    def balanced(self) -> Candidate | None:
        return next((item for item in self.alternatives if item.label == "balanced"), None)

    @property
    def candidates(self) -> tuple[Candidate, ...]:
        return (self.fastest, *self.alternatives, *((self.uncapped,) if self.uncapped is not None else ()))


class OutsideAreaError(ValueError):
    """A route endpoint is outside or too far from the demo graph."""


class NoPathError(ValueError):
    """No unblocked walking path connects the snapped nodes."""


def route_id_for(edge_ids: np.ndarray) -> str:
    return blake2b(np.asarray(edge_ids, dtype=np.int32).tobytes()).hexdigest()[:10]
