from dataclasses import dataclass
from typing import Literal

import numpy as np

RouteLabel = Literal["fastest", "balanced", "lower_exposure", "uncapped"]


@dataclass(frozen=True)
class Candidate:
    label: RouteLabel
    route_id: str            # first 10 hex chars of blake2b(edge_ids.tobytes())
    edge_ids: np.ndarray     # int32, in order from origin to destination
    node_ids: np.ndarray     # int32
    minutes: float
    distance_m: float
    exposure_mean: float     # sum of bundle.mean[radius][edge_ids]
    lam: float               # λ that produced it


@dataclass
class CandidateSet:
    fastest: Candidate
    alternatives: list[Candidate]   # "balanced" and/or "lower_exposure", each ≤ (1+MAX_EXTRA_TIME)·fastest.minutes
    uncapped: Candidate | None      # lowest-exposure Pareto route ABOVE the time cap. Internal only.


class OutsideAreaError(Exception):
    ...


class NoPathError(Exception):
    ...


def route_id_for(edge_ids: np.ndarray) -> str:
    import hashlib
    return hashlib.blake2b(np.asarray(edge_ids, dtype=np.int32).tobytes()).hexdigest()[:10]
