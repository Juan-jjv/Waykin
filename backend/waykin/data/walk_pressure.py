"""Walking incident pressure: the exposure model for walking routes (driving keeps the allocation model).

For someone on foot, what matters is how close the route passes to recent reports. Each walkable edge gets a score:
the reports near it, weighted by

  * closeness: a Gaussian kernel, sigma = half the catchment radius, cut off at 3 sigma;
  * recency: half-life WALK_HALF_LIFE_DAYS over the WINDOW_DAYS the map shows, so routes and the map agree;
  * severity: the category weights in categories.yaml;

integrated along the edge and normalised so that walking straight past a report adds about its weight once. A route's
score is the sum over its edges, so splitting an edge never changes it. Unlike the allocation model, a report is not
divided among the streets around it, so dense downtown grids and road centrelines next to sidewalks don't dilute a
hotspot, and streets with no reports nearby score zero instead of carrying a uniform prior.

Uncertainty: each simulation redraws every location's weight as weight · Gamma(n + 0.5) / (n + 0.5), n = its report
count, so one report is far less certain than twenty. Route draws are S = (Σ_route M) @ Λ, so no (edges × draws)
matrix is ever built.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import date, timedelta

import numpy as np
import pandas as pd
import scipy.sparse as sp
import shapely
from scipy.spatial import cKDTree

from waykin import constants as C
from waykin.data.sources.base import category_config
from waykin.routing.graph import latlon_to_utm

log = logging.getLogger("waykin.data")


@dataclass
class WalkPressure:
    radii: list[int]
    as_of: date
    window_days: int
    M: dict[int, sp.csr_matrix]     # radius -> (E, L): pressure each location puts on each edge, per unit weight
    mean: dict[int, np.ndarray]     # radius -> (E,): M @ weights, the field routes are searched on
    draws: np.ndarray               # (L, N) float32: location weights per simulation
    avoid_m: np.ndarray | None = None   # (E,): metres of each edge inside a no-go zone (see avoid_zones)
    n_avoid: int = 0                    # spots that make a no-go zone

    @property
    def observed(self) -> dict[int, np.ndarray]:
        return self.mean

    def route_sums(self, routes, radius_m: int) -> np.ndarray:
        """(n_routes, N) pressure per simulation."""
        M = self.M[radius_m]
        rows = np.stack([np.asarray(M[np.asarray(r.edge_ids)].sum(axis=0)).ravel() for r in routes])
        return rows @ self.draws.astype(np.float64)

    def observed_total(self, edge_ids: np.ndarray, radius_m: int) -> float:
        return float(self.mean[radius_m][edge_ids].sum())


def sigma_for(radius_m: int) -> float:
    return float(radius_m) / 2.0


def location_weights(locations: pd.DataFrame, daily: pd.DataFrame | None, as_of: date,
                     window_days: int = C.WINDOW_DAYS, half_life_days: float = C.WALK_HALF_LIFE_DAYS,
                     severity: dict[str, float] | None = None) -> pd.DataFrame:
    """location_id, lat, lon, n (reports in the window) and weight (recency × severity), for locations with reports.

    Without a per-day table (an older build) every report counts as if made on as_of."""
    severity = category_config().severity if severity is None else severity
    if daily is not None:
        d = daily.copy()
        d["date"] = pd.to_datetime(d["date"])
        d = d[d["date"] > pd.Timestamp(as_of - timedelta(days=window_days))]
        age = (pd.Timestamp(as_of) - d["date"]).dt.days.to_numpy(float).clip(min=0)
        sev = d["category"].map(lambda c: severity.get(c, 1.0)).to_numpy(float)
        d = d.assign(w=d["count"].to_numpy(float) * 0.5 ** (age / half_life_days) * sev,
                     sev=np.where(d["count"].to_numpy() > 0, sev, 0.0))
        per = d.groupby("location_id").agg(n=("count", "sum"), weight=("w", "sum"), max_sev=("sev", "max")).reset_index()
    else:
        rows = []
        for loc in locations.itertuples(index=False):
            by = json.loads(loc.counts_by_category) if loc.counts_by_category else {}
            rows.append((loc.location_id, int(loc.count), sum(n * severity.get(c, 1.0) for c, n in by.items()),
                         max((severity.get(c, 1.0) for c, n in by.items() if n > 0), default=0.0)))
        per = pd.DataFrame(rows, columns=["location_id", "n", "weight", "max_sev"])
    per = per[(per["n"] > 0) & (per["weight"] > 0)]
    out = per.merge(locations[["location_id", "lat", "lon"]], on="location_id", how="inner")
    return out.sort_values("location_id").reset_index(drop=True)


def avoid_zones(graph, locs: pd.DataFrame, min_severity: float = C.AVOID_MIN_SEVERITY,
                radius_m: float = C.AVOID_RADIUS_M) -> tuple[np.ndarray, int]:
    """(metres of each edge inside a no-go circle, number of circles). A circle of `radius_m` goes around every spot
    whose most serious report in the window is at least `min_severity`; overlapping circles count once each, so an
    edge near several serious spots is avoided harder."""
    avoid = np.zeros(graph.n_edges)
    severe = locs[locs["max_sev"] >= min_severity]
    if severe.empty:
        return avoid, 0
    x, y = (np.asarray(v, float) for v in latlon_to_utm(severe["lat"].to_numpy(float), severe["lon"].to_numpy(float)))
    circles = shapely.buffer(shapely.points(x, y), radius_m, quad_segs=16)
    row, edge = graph.edge_tree.query(circles, predicate="intersects")
    inside = shapely.length(shapely.intersection(graph.edge_geom_utm[edge], circles[row]))
    np.add.at(avoid, edge, inside)
    return avoid, len(severe)


def _edge_samples(graph, step_m: float):
    """Points every ~step_m along each walkable edge: (edge id, x, y, length each point stands for)."""
    edges = np.flatnonzero(graph.edge_walk)
    length = graph.edge_length_m[edges]
    n = np.maximum(1, np.ceil(length / step_m).astype(np.int64))
    eid = np.repeat(edges, n)
    first = np.repeat(np.cumsum(n) - n, n)
    frac = (np.arange(n.sum()) - first + 0.5) / np.repeat(n, n)
    xy = shapely.get_coordinates(shapely.line_interpolate_point(graph.edge_geom_utm[eid], frac, normalized=True))
    return eid, xy, np.repeat(length / n, n)


def build_walk_pressure(graph, locations: pd.DataFrame, daily: pd.DataFrame | None, as_of: date, radii,
                        *, n_draws: int = C.N_DRAWS, seed: int = C.SEED, window_days: int = C.WINDOW_DAYS,
                        half_life_days: float = C.WALK_HALF_LIFE_DAYS,
                        step_m: float = C.WALK_SAMPLE_STEP_M) -> WalkPressure:
    """Build the walking field for each radius. A few seconds for the whole city; never logs coordinates."""
    t0 = time.time()
    radii = [int(r) for r in radii]
    locs = location_weights(locations, daily, as_of, window_days, half_life_days)
    weights = locs["weight"].to_numpy(float)
    counts = locs["n"].to_numpy(float)
    n_loc = len(locs)

    M: dict[int, sp.csr_matrix] = {}
    mean: dict[int, np.ndarray] = {}
    if n_loc:
        px, py = (np.asarray(v, float) for v in latlon_to_utm(locs["lat"].to_numpy(float), locs["lon"].to_numpy(float)))
        eid, xy, seg = _edge_samples(graph, step_m)
        cutoff = 3.0 * max(sigma_for(r) for r in radii)
        D = cKDTree(xy).sparse_distance_matrix(cKDTree(np.column_stack([px, py])), cutoff, output_type="coo_matrix")
        dist = np.asarray(D.data)
        for r in radii:
            sigma = sigma_for(r)
            keep = dist <= 3.0 * sigma
            k = np.exp(-dist[keep] ** 2 / (2.0 * sigma ** 2)) * seg[D.row[keep]] / (np.sqrt(2.0 * np.pi) * sigma)
            M[r] = sp.csr_matrix((k, (eid[D.row[keep]], D.col[keep])), shape=(graph.n_edges, n_loc))
            M[r].sum_duplicates()
            mean[r] = np.asarray(M[r] @ weights, dtype=np.float64).ravel()
    else:
        for r in radii:
            M[r] = sp.csr_matrix((graph.n_edges, 0))
            mean[r] = np.zeros(graph.n_edges)

    rng = np.random.default_rng([seed, 7])
    shape = counts + 0.5
    draws = (weights / shape)[:, None] * rng.gamma(shape=shape[:, None], size=(n_loc, n_draws))
    avoid, n_avoid = avoid_zones(graph, locs)
    log.info("walk pressure: %d locations, %d no-go zones, radii %s, %.1f s", n_loc, n_avoid, radii, time.time() - t0)
    return WalkPressure(radii=radii, as_of=as_of, window_days=window_days, M=M, mean=mean,
                        draws=draws.astype(np.float32), avoid_m=avoid, n_avoid=n_avoid)


def walk_pressure_for(state) -> WalkPressure:
    """The state's walking field, built on first use (the server builds it at startup)."""
    if getattr(state, "walk", None) is None:
        b = state.exposure
        state.walk = build_walk_pressure(state.graph, b.locations, b.daily, b.as_of, b.radii)
    return state.walk
