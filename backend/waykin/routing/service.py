"""Orchestration boundary used by both route and reroute endpoints.

The graph search is independent of HTTP schemas. This module adapts its result
to the shared response models when they are present, while remaining importable
before the backend skeleton and Agent A2's assessment package land.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np

from .explain import explanation_text, route_geometry, top_segments
from .router import candidate_set
from .types import Graph

try:
    from waykin.constants import DEFAULT_RADIUS_M
except ImportError:
    DEFAULT_RADIUS_M = 100


def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "dict"):
        return value.dict()
    if hasattr(value, "__dataclass_fields__"):
        from dataclasses import asdict
        return asdict(value)
    return value


def _model_or_dict(model_name: str, payload: dict[str, Any]) -> Any:
    try:
        from waykin import schemas
        model = getattr(schemas, model_name, None)
    except ImportError:
        model = None
    if model is None:
        return payload
    fields = getattr(model, "model_fields", None)
    if fields is not None:
        payload = {key: value for key, value in payload.items() if key in fields}
    return model(**payload)


def _stat(stats: Any, key: str, default: Any = None) -> Any:
    if isinstance(stats, Mapping):
        return stats.get(key, default)
    return getattr(stats, key, default)


def _decision(assessment: Any) -> Any:
    decision = getattr(assessment, "decision", None)
    if decision is not None:
        return decision
    payload = _plain(assessment)
    if not isinstance(payload, dict):
        payload = {}
    return _model_or_dict("Decision", payload)


def plan(state: Any, origin: Any, destination: Any, radius_m: int | None = None) -> Any:
    """Snap endpoints, plan around hazards, assess stability, and format output.

    ``origin`` and ``destination`` accept API point models or ``(lat, lon)``
    pairs. Coordinate data is never logged or retained in state.
    """
    from waykin.data.stability import assess
    from waykin.provenance import build_provenance

    graph: Graph = state.graph
    bundle = state.exposure
    default_radius = int(getattr(getattr(state, "settings", None), "DEFAULT_RADIUS_M", DEFAULT_RADIUS_M))
    if radius_m is None:
        radius_m = default_radius
    if radius_m not in bundle.mean:
        radius_m = default_radius
    if radius_m not in bundle.mean:
        raise ValueError("default exposure radius is not loaded")
    edge_exposure = np.asarray(bundle.mean[radius_m], dtype=np.float64)

    def coordinates(point: Any) -> tuple[float, float]:
        if hasattr(point, "lat") and hasattr(point, "lon"):
            return float(point.lat), float(point.lon)
        if isinstance(point, Mapping):
            return float(point["lat"]), float(point["lon"])
        lat, lon = point
        return float(lat), float(lon)

    origin_lat, origin_lon = coordinates(origin)
    destination_lat, destination_lon = coordinates(destination)
    source = graph.snap(origin_lat, origin_lon)
    target = graph.snap(destination_lat, destination_lon)
    if source == target:
        from .types import NoPathError
        raise NoPathError("same_point")

    blocked = np.asarray(state.hazards.blocked_mask(), dtype=bool)
    candidates = candidate_set(graph, edge_exposure, source, target, blocked)
    assessment = assess(candidates, bundle, radius_m)
    stats_by_id = getattr(assessment, "stats", {})

    chosen = [("fastest", candidates.fastest)]
    if candidates.lower_exposure is not None:
        chosen.append(("lower_exposure", candidates.lower_exposure))
    if candidates.balanced is not None:
        chosen.append(("balanced", candidates.balanced))
    options: list[Any] = []
    for label, route in chosen:
        stats = stats_by_id.get(route.route_id, {}) if isinstance(stats_by_id, Mapping) else {}
        extra_minutes = max(0.0, route.minutes - candidates.fastest.minutes)
        stats_for_text = _plain(stats)
        if isinstance(stats_for_text, Mapping):
            stats_for_text = {**stats_for_text, "minutes": route.minutes}
        else:
            stats_for_text = {"minutes": route.minutes, "p50": _stat(stats, "p50", 0.0), "diff_p50": _stat(stats, "diff_p50", 0.0)}
        payload = {
            "id": route.route_id,
            "route_id": route.route_id,
            "label": label,
            "edge_ids": route.edge_ids.tolist(),
            "geometry": route_geometry(graph, route.node_ids, route.edge_ids),
            "minutes": route.minutes,
            "distance_m": route.distance_m,
            "exposure": route.exposure_mean,
            "exposure_mean": route.exposure_mean,
            "stats": _plain(stats),
            "stability": _stat(stats, "stability"),
            "top_segments": top_segments(graph, route.edge_ids, edge_exposure, k=3),
            "extra_minutes": extra_minutes,
            "explanation": explanation_text(label, extra_minutes, stats_for_text),
        }
        options.append(_model_or_dict("RouteOption", payload))

    response = {
        "provenance": _plain(build_provenance(state, radius_m)),
        "origin_snapped": {"lat": float(graph.node_latlon[source, 0]), "lon": float(graph.node_latlon[source, 1])},
        "destination_snapped": {"lat": float(graph.node_latlon[target, 0]), "lon": float(graph.node_latlon[target, 1])},
        "routes": options,
        "decision": _decision(assessment),
        "blocked_edge_count": int(blocked.sum()),
    }
    return _model_or_dict("RoutesResponse", response)
